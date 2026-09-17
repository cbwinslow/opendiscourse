# Schema invariants

Companion to `SPEC.md`. Binding short form: `docs/adr/0002-schema-invariants.md`
(AD-10). Verified against `docs/schema-snapshot/` captured 2026-09-17.

## Keep

```text
INVENTORY / CONTRACTS
        │
SOURCE ─► CONNECTOR ─► EVIDENCE ─► STAGE ─► reviewed transform
                                              ├─► CORE
                                              └─► FACT
                                                    │
                                                   MART
                                              ┌──────┴──────┐
                                             API     DuckDB/Parquet

OpenStates DB ─ read-only FDW ─► openstates_source
                    ├─► promote/reconcile ─► core/fact
                    └─► leg compatibility views
```

Bounded schemas (do not add a generic EAV facts table; do not copy each
provider's database): `catalog`, `ingest`, `stage`, `core`, `fact`, `mart`,
`leg`, `api` (views later), `openstates_source` (FDW).

OpenStates stays a separate DB, read-only FDW, OCD language in owned
tables. Internal UUIDs plus identifier tables. Do not add a second SDD
framework. Do not redesign the Connector on the FRED branch.

**Prove one vertical slice before horizontal expansion:**

```text
Connector (FRED e2e) and/or
Congress/GovInfo/OpenStates → bill/person/session/roll-call
  → legislator_vote mart → researcher query
```

Existing ACS/TIGER/bill rows loaded on pre-Connector paths do **not** count
as that slice. Do not open Epic 7 to "use" `stage.fec_row`.

## Ownership

| Surface | Owner | Notes |
|---|---|---|
| `catalog`, `ingest`, `stage`, `core`, `fact` | Alembic | Contracts; baseline `d207df35ca10` onward |
| `mart` | dbt | Researcher models; do not dual-own in Alembic |
| `api` | Epic 6.1 | Schema exists; reviewed PostgREST views are still future |
| `leg` | compatibility views | Stable legislative read over owned + FDW data |
| `openstates_source` | FDW | Not the researcher contract |

## Schema support is not ingest scope

| Object | Why it exists | Authorized now? |
|---|---|---|
| `stage.fec_row` (~102M rows, 74 GiB on the operator cluster) | Legacy/provider-shaped staging | No promote to `core`/`fact`; no Epic 7; no politician joins |
| `core.instrument`, `core.instrument_symbol`, `fact.market_bar` (empty) | Compatibility primitives | No market-bar ingest; stocks are not a v1 domain. A later disclosure may *reference* an instrument without loading prices |
| `api` schema | Target access layer | Empty HTTP surface until Epic 6.1 |

## Dual legislative identity (compatibility)

`core.bill` and `core.roll_call` currently store both:

- text `jurisdiction` + `legislative_session` (unique keys still use these)
- `legislative_session_id` (canonical FK)

Treat the text columns as **legacy compatibility**. New loaders and 8.1+
code must prefer the FK. Do not rip the text columns until unique keys and
`sql/query/legislation/upsert_bill.sql` move. Jurisdiction of a bill is
`bill → legislative_session → jurisdiction`.

## Provenance classes (2026-09-17 snapshot)

**A — source-derived, evidence CHECK present**

`core.legislative_session`, `core.membership`, `core.bill_action`,
`core.bill_identifier`, `core.bill_sponsorship`, `core.bill_committee`,
`core.bill_subject`, `fact.member_vote`.

**A — source-derived, evidence columns present, CHECK missing**

`core.geography_boundary` (`source_artifact_id` / `source_payload_id`, no
CHECK). `core.document` (`source_payload_id` / `artifact_id` — name
mismatch, no CHECK).

**A — source-derived facts with NOT NULL artifact (no OR-CHECK needed)**

`fact.acs_bulk_estimate`, `fact.business_pattern`,
`fact.decennial_dhc_value` (`source_artifact_id` NOT NULL).
`fact.measurement` (`source_payload_id` NOT NULL).

**B — identity/reference; evidence not on the row**

`core.person`, `core.person_identifier`, `core.organization`,
`core.organization_identifier`, `core.geography`, `core.jurisdiction`,
`core.bill` (identity row; evidence lives on identifier/action/sponsorship
children), `core.roll_call` (identity row; evidence on `fact.member_vote`).

**C — system / out of v1 product**

`core.embedding` (derived from chunks; dimension CHECK only),
`core.document_chunk` (checksum, no ingest FK), market tables.

Rule: **A for source-derived entities**, with B/C documented. Follow-on
story: add CHECKs where class A is missing them; do not silently require
evidence on class B overnight.

## Idempotency

Same artifact + source member/ordinal, or the same external identifier in a
namespace, must not insert a second canonical row. Follow existing unique /
NULLS NOT DISTINCT keys on bill children, `ingest.artifact (dataset_id,
artifact_key)`, and `core.person_identifier (namespace, external_id)`.

## Geography

`core.geography.parent_geoid` remains a loose string in v1. Congressional
districts, tracts, and ZCTAs do not form a single parent tree.
Story 8.1 stores division **identifiers only**; no `geography_id` on
`core.division`.

Deferred grain (not v1, not 8.1): wrap Census relationship files when
Epic 5 needs vintage comparability (`resolved-questions.md` §6).

```text
core.geography_relationship
  source_geography_id
  target_geography_id
  relationship_type
  valid_from / valid_to
  weight_population / weight_area
  source_artifact_id
```

## Contract tests to add later (not 8.1)

- source-less membership → rejected
- source-less member vote → rejected
- duplicate external person id → rejected
- duplicate artifact `(dataset_id, artifact_key)` → rejected
- embedding `cardinality(vector_values) = dimensions`
- historical TIGER vintage preserved (no overwrite)

## Review claim → contract (2026-09-17)

| Review § | Contract |
|---|---|
| 1 Bounded schemas, typed middle | Keep + ownership (this file); SPEC typed-grains constraint |
| 2 OpenStates FDW / `leg` | SPEC AD-8; CAP-8 |
| 3 UUID + identifier tables; identity before money | SPEC UUID-PK constraint; CAP-4; AD-5 |
| 4 Provenance invariant | CAP-1; AD-3; classes A/B/C here |
| 5 Typed fact tables; keep `fact.measurement` for series | SPEC typed-grains constraint |
| 6 Dual bill/roll_call session identity | SPEC compatibility constraint; Story 8.3 deferred |
| 7 Provenance CHECK gaps | Classes A missing CHECK; Story 1.6 |
| 8 Crime/FBI ordering | `v1-scope.md`; blueprint aligned |
| 9 Market tables retained, no price ingest | SPEC non-goal; table in this file |
| 10 `stage.fec_row` ≠ Epic 7 | SPEC schema≠ingest; `v1-scope.md` |
| 11 `api` target / Epic 6 | CAP-6 success; ownership |
| 12 `mart` dbt-owned | SPEC ownership constraint |
| 13 `geography_relationship` later | Deferred grain above; SPEC non-goal for v1 |
| 14 No second SDD | SPEC non-goal; CAP-7 |
| 15 PRD persona | PRD UJ-1 “the operator” |
| 16 Persistence date | `docs/persistence-migration-status.md` 2026-09-17 |

Wrapper-only (not in kernel): review praise of “architecture strong”;
recommendation to “approve.” Keep-and-refine is the decision that remains.
