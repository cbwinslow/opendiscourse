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

### Story 1.6 — Provenance and identity contract tests — done
As an operator, class-A source-derived tables reject source-less rows, and
duplicate external person IDs / duplicate artifacts fail.
Acceptance: audit remaining CHECK gaps (`geography_boundary`, `document`);
pytest db cases listed in `schema-invariants.md`. Not on the FRED branch;
not mixed into 8.1 unless a CHECK is required for new 8.1 tables.
Landed on `main` via PR #24.

### Story 1.7 — Immutable artifact versions — in review
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
PR #25 was reverted (#26). Rebuilt on `fix/1-7-immutable-artifacts`, reviewed twice,
not yet merged; see `implementation-artifacts/spec-1-7-immutable-artifact-versions-2.md`.

## Epic 2 — Connector protocol + FRED reference

### Story 2.1 — Connector Protocol — done
As a developer, I have a typed Connector interface covering the 10-stage
lifecycle.
Acceptance: Protocol in code; tests for the interface; no schema change.
Landed: `ingestion/connector.py` (`Connector`, `STAGES`, `run_connector`);
`tests/test_connector.py`.

### Story 2.2 — Registry without HANDLERS if/elif — reverted, redo
AGY's PR #18 was reverted in #26 (FRED-specific branch left in `registry.sync`).
Redo through the Connector with no central dispatcher edit; do not revive #18.
As a developer, I register FRED without adding to a hardcoded handler set.
Acceptance: FRED path does not need a new `plans.py` elif.

### Story 2.3 — Migrate FRED end-to-end — reverted, redo
AGY's PR #20 was reverted in #26 (discovery failures left leases/runs stuck).
Redo after 2.2; failures must checkpoint with an actionable error.
As an operator, FRED discover/index vs observations still split; observations
still contract-gated.
Acceptance: Existing FRED tests pass; provenance unchanged.

## Epic 3 — Identity crosswalk

### Story 3.1 — Load congress-legislators
As a researcher, BioGuide IDs land in `core.person` / `person_identifier`
from `vendor/congress-legislators`.
Acceptance: Idempotent load; provenance artifact; no name matching.
Built on `feat/3-1-bioguide-identity` (Connector `congress.legislators`,
`core.person_identifier.source_artifact_id`); pending review and live apply.

### Story 3.2 — Gate politician-join sources
As an operator, FEC/disclosure/elections-as-member *joins* stay disabled
until a reviewed contract opens them (Story 3.1, the identity prerequisite, is
done; that alone does not open a join).
Acceptance: each source declares `person_join` (state, key=bioguide, via,
blocked_by) in `inventory/sources.yaml`; `init-db` validation and
`identitygate.require_person_join` enforce it; `research-db person-join-status`
reports it. Crime-native and FEC-native staging are not identity-blocked; they
stay v1.1 (Epic 7) and must not start here.
Built on `feat/3-2-gate-politician-joins`; pending review.

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

### Story 8.2 — OpenStates promote, not public FDW — reverted, redo
AGY's PR #22 was reverted in #26: it accepted a manifest without validating the
snapshot's file/bytes/checksum and keyed membership without role/end date.
Rows it already wrote to `core` are suspect; re-promote after the redo.
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

## Epic 9 — Ingestion contract, run ledger, coverage (v1 completeness)

Goal (operator, 2026-09-19): complete, trustworthy datasets, ingested by
idempotent and fast workflows, with an exact record of what went where.
Federal legislation scope is **Congresses 108-119**. Details and rationale:
`docs/PROJECT-STATE.md`.

### Story 9.1 — Load contract ADR-0003 and idempotency harness
As an operator, every source loads by the strategy that fits its grain, and a
shared test proves it: bulk facts/stage reload by partition (COPY to temp,
validate, delete-and-insert the slice in one transaction); FK-referenced entities
set-based upsert from a temp table touching only changed rows (keeps UUIDs); raw
bytes never wiped and reused unless the remote checksum changed.
Acceptance: benchmark reload vs upsert on one real dataset first; ADR-0003
records the numbers; harness asserts run-twice = same counts, kill-and-resume =
same result, wipe-and-reload = same result. Check whether the big tables are
partitioned before choosing.
Built on `feat/9-1-load-contract`: ADR-0003 (`docs/adr/0003-load-strategy.md`), benchmark
`scripts/bench/benchmark_load_strategies.py`, harness `tests/idempotency_harness.py` (first user:
legislators Connector). Benchmark to be rerun after the 17 cluster is restarted with tuned memory.

### Story 9.2 — Ingest run ledger
As an operator, I can see exactly what each run wrote: target table, coverage
key (e.g. congress/cycle/year), rows inserted/updated/skipped, status.
Acceptance: Alembic `ingest.run_target`; `IngestionRun` writes it; `code_version`
= git SHA on every run; a query answers "what is loaded for dataset X, by
period". Foundation for 9.3.
Built on `feat/9-2-run-ledger` (`ingest.run_target`, `ingest.loaded_coverage`,
`research-db loaded`); loaders adopt `record_target` as they are touched.

### Story 9.3 — Coverage comparator (Congresses 108-119)
As an operator, "complete" is a number: official manifests vs loaded rows per
source and Congress.
Acceptance: report of expected/loaded/missing per Congress for bills, actions,
votes, members; the 108th start is confirmed against GovInfo manifests.
Built on `feat/9-3-coverage-comparator` (`research-db coverage`, `coverage.py`,
`providers/official_counts.py`); first measurement in `docs/PROJECT-STATE.md`.

## Later (not started; do not begin without a spec)

- **Scorecards** (CAP-9, needs its own spec): derived `mart` outputs over
  evidence-backed rows; transparent indicators; no opaque corruption score.
- **Text/NLP/vectors:** keep bill text as immutable artifacts and `core.document`
  now; embeddings, summaries, and kNN only after chunks exist (ADR first).
- Crime data (Epic 7), FRED depth, ACS/housing marts.

## Suggested next build (updated 2026-09-19)

Keep-and-refine. Do not start Epic 7. Order:

1. **Merge Story 1.7** (`fix/1-7-immutable-artifacts`) after the operator sees the
   review. Evidence must be immutable before any re-ingest.
2. **Story 9.1** (benchmark, ADR-0003, harness), then **9.2** (run ledger).
3. **Story 3.1** BioGuide identity (`congress-legislators`), idempotent.
4. **Story 9.3** coverage comparator, then backfill Congresses 108-119 through
   Connectors (bills/actions/members via GovInfo BILLSTATUS; votes via
   `unitedstates/congress`, Story 4.1). Each source must pass the 9.1 harness.
5. Redo **2.2 -> 2.3** (FRED) and **8.2** (OpenStates promote); fix the failed
   Treasury (24 runs) and FRED (6 runs) ingests.
6. Promote FEC only after 3.1 (cycles 2004+, v1.1).

Independent tracks stay on separate branches. Improve evidence, identity,
temporal membership, and vote completeness before broadening sources.
