---
title: OpenDiscourse epics and stories
status: final
created: 2026-09-14
updated: 2026-09-17
inputDocuments:
  - planning-artifacts/prds/prd-opendiscourse-2026-09-14/prd.md
  - planning-artifacts/architecture/architecture-opendiscourse-2026-09-14/ARCHITECTURE-SPINE.md
  - specs/spec-opendiscourse/SPEC.md
  - specs/spec-opendiscourse/reuse.md
  - specs/spec-opendiscourse/v1-scope.md
  - specs/spec-opendiscourse/schema-invariants.md
  - specs/spec-opendiscourse/resolved-questions.md
---

# OpenDiscourse — epics and stories

Fast-path decomposition. No UX spine (CLI/TUI already exist; no new UI epic).

## Extracted requirements

**FR-1..FR-20** as in the PRD. **NFR:** provenance, capacity fail-closed,
parameterized SQL, pytest+PostGIS, BMAD change-sizing, database name
`opendiscourse`. **Architecture extras:** AD-1..AD-10, FRED as first Connector,
no Playwright-first TEA, OpenStates dump is a source snapshot (AD-8), not a
physical merge. Schema support is not ingest (AD-10).

## Epic 1 — Development substrate

*Mostly landed on `main` (BMAD/TEA, CI fast lane, extras, Serena, postgres
skills, upstream bootstrap). Remaining stories still matter.*

### Story 1.1 — AGENTS.md constitution — done
As an agent, I follow a short constitution (hierarchy of truth, reuse-first,
Connector vs inventory, definition of done) instead of a creed-only AGENTS.md.
Acceptance: `bmad-project-context` adopts existing AGENTS.md; CLAUDE.md is a
stub; no GROK.md fork. Landed: managed `<!-- bmad:context -->` block in
`AGENTS.md`; `CLAUDE.md` is `@AGENTS.md`.

### Story 1.2 — ADR-0001 Postgres system of record — done
As an operator, I have ADR-0001 in `docs/adr/` matching AD-1.
Acceptance: file exists; AGENTS.md points at it.
Landed: `docs/adr/0001-postgres-system-of-record.md`; `AGENTS.md` Where things
are lists `docs/adr/`.

### Story 1.3 — OpenDiscourse skills — done
As an agent, I have project skills for connector, schema-change, provenance,
testing.
Acceptance: four skills under `.agents/skills/` (or `_bmad/custom`) with
when-to-use; Grok discovers them.
Landed: `.agents/skills/opendiscourse-{connector,schema-change,provenance,testing}`.

### Story 1.4 — GitHub ruleset (optional solo)
As an operator, `main` requires PR + CI, no force-push, squash; no extra
human approver.
Acceptance: documented; applied if GitHub permissions allow.

### Story 1.5 — Schema invariants ADR — done (this absorb)
As an agent, I follow AD-10 / ADR-0002 instead of inferring schema rules
from ChatGPT essays.
Acceptance: ADR file; spec companion `schema-invariants.md`; blueprint/PRD
persona/persistence date aligned; dual session columns marked compatibility;
`stage.fec_row` and market tables documented as not ingest-authorized.
Landed with the 2026-09-17 schema-review absorb.

### Story 1.6 — Provenance and identity contract tests
As an operator, class-A source-derived tables reject source-less rows, and
duplicate external person IDs / duplicate artifacts fail.
Acceptance: audit remaining CHECK gaps (`geography_boundary`, `document`);
pytest db cases listed in `schema-invariants.md`. Not on the FRED branch;
not mixed into 8.1 unless a CHECK is required for new 8.1 tables.

### Story 1.7 — Immutable artifact versions
As a researcher, an evidence identifier always means the same bytes even after
a remote bulk file is refreshed in place.
Acceptance: changing `checksum_sha256` for the same logical
`(dataset_id, artifact_key)` creates a new immutable artifact/version rather
than mutating the evidence row referenced by existing `core`/`fact` records;
old artifact ids/checksums remain queryable; canonical current-state rows point
to evidence that supports their current values; tests cover unchanged retry,
changed-content refresh, and rollback/replay. Do not implement as a silent
`register_artifact()` behavior change without an Alembic migration and loader
compatibility tests.

## Epic 2 — Connector protocol + FRED reference

### Story 2.1 — Connector Protocol — done
As a developer, I have a typed Connector interface covering the 10-stage
lifecycle.
Acceptance: Protocol in code; tests for the interface; no schema change.
Landed: `ingestion/connector.py` (`Connector`, `STAGES`, `run_connector`);
`tests/test_connector.py`.

### Story 2.2 — Registry without HANDLERS if/elif — done
As a developer, I register FRED without adding to a hardcoded handler set.
Acceptance: FRED path does not need a new `plans.py` elif.
Landed: `ingestion/connectors.py`; `FredCoreConnector`; `fred_core` not in
`HANDLERS` or `run_plan()` elif.

### Story 2.3 — Migrate FRED end-to-end — done
As an operator, FRED discover/index vs observations still split; observations
still contract-gated.
Acceptance: Existing FRED tests pass; provenance unchanged.
Landed: `FredCoreConnector.discover` for catalog/index/full; `registry.sync`
FRED path uses `run_connector`; observations stay `fredcore` +
`ingest_manifest`.

## Epic 3 — Identity crosswalk

### Story 3.1 — Load congress-legislators
As a researcher, BioGuide IDs land in `core.person` / `person_identifier`
from `vendor/congress-legislators`.
Acceptance: Idempotent load; provenance artifact; no name matching.

### Story 3.2 — Gate politician-join sources
As an operator, FEC/disclosure/elections-as-member *joins* stay disabled
until Story 3.1 is green.
Acceptance: Inventory/progress states say identity-blocked for those joins.
Crime-native and FEC-native staging are not identity-blocked; they stay
v1.1 (Epic 7) and must not start here.

## Epic 8 — Legislative primitives (blocks Epic 4)

Additive `core` model before loading more votes/members. Do not run on the
FRED branch. Do not copy OpenStates Django tables.

### Story 8.1 — Post, division, membership — done
As a researcher, a person occupies a seat/post representing a political
division for a time range, not only a chamber.
Acceptance: Alembic adds `core.post` (or equivalent) and `core.division` (or
equivalent, distinct from Census geography); `core.membership` can reference
a post; existing membership rows remain valid; no OpenStates dump writes.
Do not treat `bill.jurisdiction` / `bill.legislative_session` text as
canonical; prefer `legislative_session_id`. Do not add
`core.geography_relationship` here.
Landed on `main` via PR #21.

### Story 8.2 — OpenStates promote, not public FDW — in review
As a researcher, I query `core`/`fact`/`mart` for OCD-aligned state rows,
not `openstates_source.opencivicdata_*`.
Acceptance: Documented; at least one promote path from FDW to `core` for a
bounded grain (jurisdiction/session or membership); dump remains replace-only.
Current implementation is PR #22; do not merge while required CI/review checks
are unresolved.

### Story 8.3 — Session identity on FKs (deferred)
As a developer, `core.bill` and `core.roll_call` unique keys use
`legislative_session_id`, not text `jurisdiction` + `legislative_session`.
Acceptance: Gate in `resolved-questions.md` §5 (every bill/roll_call has
non-null session FK; new unique keys; upsert SQL moved). Text columns may
remain as cache. Do not start until 8.2/backfill prerequisites are green.

## Epic 4 — Wrap unitedstates/congress

### Story 4.1 — Senate + House votes producer
As a researcher, both chambers' roll calls ingest via wrapped
`vendor/unitedstates-congress`, with chamber-native source evidence retained.
Acceptance: No new first-party scraper module duplicating acquisition logic;
checksummed raw; maps to `core.roll_call` / `fact.member_vote`; House evidence
is traceable to House Clerk data and Senate evidence to Senate LIS data.
Congress.gov House-vote endpoints may be used for reconciliation only after a
coverage gate proves the required scope; a partial/beta endpoint is not the
sole vote corpus.

## Epic 5 — Research packs and marts

### Story 5.1 — Pack docs
As a researcher, I have named packs: place-year social, policy/representation,
macro/financial.
Acceptance: Documented in `docs/` and status/browse copy; no new schema.

### Story 5.2 — dbt marts
As a researcher, `district_year` and `legislator_vote` (or equivalent) build
from `core`/`fact`.
Acceptance: dbt tests; mart schema already exists.

## Epic 6 — Access

### Story 6.1 — PostgREST views
As a researcher, reviewed read-only views exist in `api` for v1 spine tables
that are already loaded.
Acceptance: No `ingest`/`stage` exposure; Compose profile still works.

### Story 6.2 — DuckDB/Parquet export
As a researcher, exports do not `fetchall()` unbounded sets.
Acceptance: Streaming/chunked path; analytics extra.

## Epic 7 — v1.1 money, elections, crime

Do not start in v1. Politician *joins* still need Epic 3 / CAP-4. FEC-native
and crime-native staging are not blocked on BioGuide; open this epic only
when v1 spine + Epic 8 are in place. Existing `stage.fec_row` (~102M rows)
is leftover staging, not a story in this epic. When opened, grains are
`resolved-questions.md` §1 (masters by cycle; itemized `sub_id`; no jsonb
promote). Stories TBD.

## Coverage

| FR | Epic |
|---|---|
| FR-1..3 | 2, existing ingest |
| FR-4..5 | 2 |
| FR-6 | existing + 4 |
| FR-7 | 4 |
| FR-8 | 3 |
| FR-9 | 8, OpenStates FDW |
| CAP-8 | 8 |
| FR-10..12 | existing bulk |
| FR-13 | 5 |
| FR-14..16 | 6 |
| FR-17..19 | 1 |
| AD-10 | 1.5, 1.6, 8.3 |
| FR-20 | 1.5, 1.6, 8.3 |
| AD-3 immutable evidence | 1.7 |

## Suggested next build

Keep-and-refine. Do not start Epic 7 and do not redesign the Connector while
its reference migration is still in flight.

Independent tracks (do not mix on one branch):

1. **Connector vertical slice:** finish/rebase PR #18 (Story 2.2), then PR #20
   (Story 2.3 FRED e2e, stacked on 2.2). Resolve the duplicate-registration
   invariant before merge.
2. **Legislative ownership:** finish PR #22 (Story 8.2), then execute the 8.3
   session-FK backfill gate. After that, Epic 4 moves federal roll-call
   acquisition to wrapped chamber-native evidence.
3. **Evidence hardening:** Story 1.6 provenance/identity contract tests, then
   Story 1.7 immutable artifact versioning. These are cross-cutting integrity
   changes and should not be hidden inside the FRED or OpenStates branches.
4. **Identity spine:** Story 3.1 loads `congress-legislators` before any
   politician-to-money/disclosure joins.

The next political-data work should improve evidence, identity, temporal
membership, and vote completeness before broadening the source catalog.
