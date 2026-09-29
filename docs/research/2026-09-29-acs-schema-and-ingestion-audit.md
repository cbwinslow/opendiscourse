# ACS/AHS schema and ingestion audit

- **Date:** 2026-09-29
- **Scope:** The active `census.acs_housing_archive` Connector; its migration,
  source-shaped staging tables, planned projection, provenance ledger, database
  constraints/indexes, and automated tests. This is not a claim that every
  historic or future source in the warehouse has received this same depth of
  review.
- **Safety decision:** Do not alter or restart the active managed archive job.
  Apply the changes below only after its post-load validation has recorded its
  outcome. Raw retained artifacts and stage rows are evidence and are never
  overwritten or deleted to repair a derived projection.

## What is presently sound

The current database check found no invalid indexes, no unvalidated constraints,
no duplicate ACS stage identities, no stage rows lacking `raw`, and no current
archive artifacts lacking a checksum or retained path. The 3,762 current archive
artifacts are all usable; none is currently failed.

The stage primary keys are correctly source-shaped:

- `stage.acs_pums_record`: `(artifact_id, source_member, source_ordinal)`
- `stage.ahs_record`: `(artifact_id, source_member, source_ordinal)`

Both link to immutable `ingest.artifact` evidence. `raw JSONB` retains every
CSV column, so a variable is not discarded merely because it has not yet been
given a convenient analytical column. This is the important protection against
field loss.

## Gaps to repair before calling the archive production-ready

### 1. The run ledger does not cover this Connector end to end

`run_connector()` supplies a `run_id` slot but does not create or finalize an
`ingest.run` row. The active ACS dataset therefore has no run-ledger row even
though its artifacts and stage rows exist. This prevents a reviewer from
proving one run's selected artifacts, parsed rows, duplicates, publication
result, error, and code version together.

**Required repair:** wrap the Connector invocation in `IngestionRun` (or an
equivalent connector-run owner), create `ingest.run_target` records for every
artifact/member and final target, and persist the checkpoint cursor. Mark a run
partial or failed explicitly; never infer success from nonzero stage rows.

### 2. The loader is intentionally safe but currently inefficient

`stage_artifact()` issues one `INSERT ... ON CONFLICT DO NOTHING` per CSV row,
inside one transaction per artifact. `publish_policy_projection()` repeats that
pattern one staged row at a time. This explains the long run time: parsing and
round-tripping millions of individual database statements cannot use the
server's available parallel capacity effectively.

**Required repair:** benchmark representative PUMS and AHS artifacts, then use
bounded batches or PostgreSQL `COPY` into a run-scoped staging relation followed
by a set-based idempotent merge. Preserve the existing composite source key and
record parsed/inserted/already-present counts. Do not add unconstrained parallel
workers before this is proven; that could duplicate work or overwhelm storage.

### 3. Completeness is not yet proven per source member

The present `validate()` check only rejects a data artifact with zero iterated
rows. It does not prove that every expected CSV member was present, that headers
were unique, that the file was not truncated, or that parsed and inserted counts
match. The returned staging count currently means rows encountered, not rows
newly stored.

**Required repair:** create an artifact/member manifest ledger with header
checksum, row count, parsed count, inserted count, duplicate count, and any
rejected-row count. Require it to reconcile before a release can be published.
Reject duplicate/empty headers, unexpected members, malformed rows, unsafe ZIP
members, and files whose decompressed size exceeds the approved budget.

### 4. All raw fields are retained, but field semantics are not catalogued yet

The database currently has zero `catalog.dataset_field` definitions for
`census.acs_housing_archive`. The code can save parsed dictionary rows, but the
active Connector does not invoke that path. Retaining raw fields prevents data
loss; it does not tell a researcher what a field means, its type, value labels,
or valid period.

**Required repair:** parse each retained official dictionary/codebook and load
versioned field definitions linked to its artifact. Treat the dictionary as a
first-class completion requirement. Add a field-accounting report: retained raw,
official definition loaded, typed projection, intentionally not projected, and
reason.

### 5. The analytical projection needs stricter geography, types, and joins

`core.housing_microdata_projection` has a correct source identity key and
artifact foreign key, but it does not currently point directly to the exact
stage record or release. Its ACS component is hard-coded as `pums`, and PUMA is
stored without a state/geography vintage. PUMA codes are not nationally unique.

The projection's `weight` is floating point and its money/ratio fields are
unbounded `numeric`; `_number()` quietly changes a malformed scalar to null.
These choices are tolerable for a first projection but not sufficient for an
authoritative analytical layer.

**Required repair:** retain actual component and geography context (state and
PUMA vintage) in the staged/projection contract; add an enforced relationship
from the projection to its source stage/release identity; choose exact types
from the official dictionaries; and record conversion failures rather than
silently creating nulls. Coded missing values must remain distinguishable from
invalid data and ordinary nulls.

### 6. Add indexes from reviewed researcher queries, not by habit

The stage tables need only their identity indexes while this bulk load is
running. The planned projection currently has only its primary-key index, so a
future filter by period, product, record type, geography, or release would scan
the whole table. Several warehouse foreign keys also have no supporting child
index; that is not automatically a defect, because unused indexes slow massive
loads and consume storage.

**Required repair:** first write the research/API query contracts and capture
`EXPLAIN (ANALYZE, BUFFERS)` on a representative database. Then add only the
indexes justified by those paths, initially likely release provenance and
projection `(product, period, component, record_type)` plus a documented
geography key. Audit high-volume existing foreign-key joins separately, with
the same usage evidence.

### 7. Publication must have one authoritative current release

`housing_archive_release` can retain multiple evidence-backed rows for one
logical product/period/component when bytes are refreshed. That is useful for
history, but it lacks a defined current/superseded relationship. A consumer
could see two releases without knowing which to use.

**Required repair:** model currentness/supersession explicitly, retain all
evidence versions, and provide one reviewed reader boundary for the current
release—following the existing `ingest.current_artifact` pattern.

### 8. Test coverage is strong for PUMS but incomplete for AHS and failure paths

The fast suite passed 638 tests in this audit. The database persistence test
stages and publishes a PUMS person row, but no database-backed test runs an AHS
CSV through stage, validation, and publication. There are also no tests that
require per-member reconciliation, malformed-header handling, conversion-error
reporting, or a partial-run ledger.

**Required repair:** add those tests before changing the loader. Include
idempotent re-run, resume after interruption, partial artifact failure,
provenance linkage, current-artifact selection, and no direct source-data loss.

## Sequenced implementation plan

1. Let the managed archive stage its current run unchanged and validate its
   retained evidence and source-shaped rows after completion.
2. Build a bounded ingestion-hardening change: run ledger, member reconciliation,
   dictionary import, AHS integration coverage, and failure accounting.
3. Build a separate performance change with benchmarks and a reversible
   batch/COPY implementation. Compare counts/checksums against the existing
   source-shaped stage contract.
4. Only after real query contracts exist, add reviewed projection fields,
   geography joins, exact types, and query-driven indexes through Alembic.
5. Repeat the same audit template for each other high-volume source, beginning
   with the existing largest tables and researcher-facing joins.

## Verification performed

- `just check-fast`: 638 passed.
- Live database: zero invalid indexes; zero unvalidated constraints; zero
  duplicate ACS stage keys; zero ACS/AHS rows without raw records; zero missing
  checksums or paths among 3,762 current artifacts.
- Managed service: active/running, `Result=success`, `ExecMainCode=0`, and no
  matching error/exception/fatal messages in the current service journal.

