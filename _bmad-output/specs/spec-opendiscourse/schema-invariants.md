# Schema invariants

Companion to `SPEC.md`. Binding short form: `docs/adr/0002-schema-invariants.md`
(AD-10). Verified against `docs/schema-snapshot/` captured 2026-09-17.

## Keep

Source → immutable evidence → `stage` → typed `core`/`fact` → `mart` →
access. OpenStates stays a separate DB, read-only FDW, OCD language in
owned tables. Internal UUIDs plus identifier tables. Do not add a second
SDD framework. Do not redesign the Connector on the FRED branch.

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

## Geography

`core.geography.parent_geoid` remains a loose string in v1. Congressional
districts, tracts, and ZCTAs do not form a single parent tree.
`core.geography_relationship` (typed, dated, optional weights) is deferred
until TIGER vintages need longitudinal overlap. Story 8.1 stores division
**identifiers only**; no `geography_id` on `core.division`.

## Contract tests to add later (not 8.1)

- source-less membership → rejected
- source-less member vote → rejected
- duplicate external person id → rejected
- duplicate artifact `(dataset_id, artifact_key)` → rejected
- embedding `cardinality(vector_values) = dimensions`
- historical TIGER vintage preserved (no overwrite)
