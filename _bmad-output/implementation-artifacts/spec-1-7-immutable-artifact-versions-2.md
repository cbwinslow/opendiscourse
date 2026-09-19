---
title: 'Story 1.7 repair: Immutable artifact evidence'
type: 'feature'
created: '2026-09-18'
status: 'in-review'
route: 'dispatch'
review_loop_iteration: 1
baseline_commit: '910823b55968438091aad8f2fe94b8e26f83c228'
context:
  - '_bmad-output/implementation-artifacts/epic-1-context.md'
  - '_bmad-output/specs/spec-opendiscourse/SPEC.md'
  - 'docs/adr/0002-schema-invariants.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** A refresh of a logical bulk artifact currently updates its sole `ingest.artifact` row and replaces its file in place. Existing `core` and `fact` references can therefore appear to cite different bytes, violating the provenance contract. The earlier repair was reverted because its downgrade deleted evidence, its storage path remained mutable, and registration was race-prone.

**Approach:** Rebuild artifact versioning as an append-only evidence contract: a changed checksum creates a new row and a checksum-specific retained file; retries reuse the matching immutable row. Preserve existing UUID foreign keys and compatibility for repository callers.

**Decision — legacy artifacts:** Preserve pre-repair catalog rows without asserting that their current local paths still contain the recorded bytes. New completed registrations must use verified checksum-specific retained paths. A later operator audit may validate and recover legacy files; mismatches remain unverified rather than being silently repaired.

**Decision — registration boundary:** `register_artifact` itself enforces the retained-path invariant for real, checksummed byte artifacts. Virtual or no-checksum source references remain valid compatibility records and are exempt from byte-retention checks.

**Decision — failed attempts:** Retain failure provenance as an immutable provisional artifact version. A later successful retry may promote that same failed, checksum-less version to verified retained bytes; it must never change an earlier completed version.

## Boundaries & Constraints

**Always:** Use one Alembic revision after `b1e5c8a3d942`; retain `artifact_id` and all existing foreign keys; use bound SQL parameters; retain bytes at a version-specific path before registering a completed artifact; make first registration safe under concurrent workers; keep `register_artifact(..., conn)` and `get_artifact(..., conn)` positional compatibility; provide explicit-version lookup only as a keyword argument; test with real Postgres without xdist.

**Never:** Delete, deduplicate, repoint, or overwrite an artifact row or retained bytes during downgrade; mutate an existing non-null checksum or completed artifact path when new bytes differ; change the frozen baseline DDL; redesign Connector or OpenStates behavior; claim historical local bytes are valid without verification.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|---------------|----------------------------|----------------|
| First registration | No logical artifact exists | Create v1 and return its UUID/version | Concurrent calls resolve to one v1 without a uniqueness leak |
| Same-content retry | Latest retained checksum equals incoming checksum | Reuse the existing UUID and immutable path | No second version |
| Changed refresh | Incoming checksum differs | Retain bytes at a new checksum-specific path and create v2 | v1 row, checksum, and file remain unchanged |
| Bulk overwrite | Remote filename is reused with new bytes | Download staging file is promoted to a version-specific destination | Existing path is never replaced |
| Failed refresh | Download or verification fails | Persist a failed provisional attempt without changing an existing completed version | A successful retry may promote the provisional version only after verified retention |
| Virtual source | No local bytes or checksum (for example an FDW reference) | Preserve a compatibility catalog record | Exempt from retained-file validation |
| Legacy positional call | `get_artifact(dataset, key, conn)` | Continues to use the supplied connection | Explicit version is keyword-only |
| Downgrade with history | Any logical key has more than one version | Refuse downgrade without changing rows | Actionable migration error |

</frozen-after-approval>

## Code Map

- `migrations/versions/` -- add the Alembic-owned `ingest.artifact` version column, unique key, and non-destructive downgrade guard; do not alter the baseline.
- `src/opendiscourse_research/models/catalog.py` -- mirror the new artifact contract in SQLAlchemy metadata.
- `src/opendiscourse_research/repositories/legislation.py` -- preserve caller signatures while making repository and supplied-connection registration/lookup version-aware and concurrency-safe.
- `sql/query/legislation/{register_artifact,get_artifact}.sql` -- keep raw psycopg registration and lookup semantically identical to the repository path.
- `src/opendiscourse_research/ingestion/bulk.py` -- stage downloads, hash them, and retain them at immutable version-specific paths before completed registration.
- `src/opendiscourse_research/{browser.py,legload.py,ingestion/*_load.py}` -- select the intended latest version and route real byte artifacts through verified retention without changing Connector/OpenStates scope.
- `tests/test_artifact_versioning.py` -- new DB coverage for retained bytes, versions, failure attempts, raw and bulk concurrency, and downgrade refusal.
- `tests/{conftest.py,test_persistence_foundation.py,test_provenance_identity_contracts.py}` -- collect DB coverage and update the migration/unique-key contract assertions.

## Tasks & Acceptance

**Execution:**
- [x] Add the artifact-version migration and model metadata, including a downgrade preflight that fails rather than loses evidence.
- [x] Implement shared version-aware registration and lookup semantics for SQLAlchemy and raw psycopg callers, including retention validation, provisional failures, and autocommit-safe locking.
- [x] Change bulk/local artifact admission to retain checksum-specific bytes, serialize staging, and register only immutable locations on completion.
- [x] Route direct real-byte callers through verified retention; preserve virtual/no-checksum records; select latest versions intentionally in loaders and ACS snapshots.
- [x] Add database and focused download tests for every matrix scenario, including historical references, raw and bulk concurrency, failure promotion, and two-version lookup consumers.

**Acceptance Criteria:**
- Given a referenced v1 artifact, when changed v2 bytes are registered, then v1's UUID, checksum, and retained bytes remain unchanged and the new row has a distinct UUID/version.
- Given two registrations of the same new logical key, when they overlap, then callers receive one v1 without an exposed unique-constraint failure.
- Given a database with multiple artifact versions, when downgrade is attempted, then it fails without deleting, merging, or repointing evidence.
- Given a real checksummed direct registration, when its supplied path is not the verified retained location, then it is rejected; virtual/no-checksum references remain registrable.
- Given a failed refresh after v1 completes, when the failure is recorded, then v1 remains unchanged and a later verified retry can promote only the provisional failure version.
- Given the repaired branch, when `just check-fast` and `just check-db` run, then both pass.

## Implementation Notes

- Added revision `d9e4f1a7b632`, with an append-only version key and a downgrade preflight that restores the parent schema only when no artifact history exists.
- Bulk downloads and local registration retain verified bytes at checksum-specific paths before a completed artifact is registered. Legacy paths are intentionally not treated as retained evidence.
- Repository and supplied-connection registration share advisory-lock protected version allocation; explicit artifact lookup is keyword-only to preserve positional connection callers.
- The previous implementation was deliberately reverted after review; the preceding notes describe discarded work and do not represent the current tree.

## Spec Change Log

- Resumed after the independent reviewers stopped at a usage limit without findings. The first rebuild passed 111 fast and 79 DB tests, but acceptance audit found missing local-file validation, legacy-path supersession, resumable serialized staging, atomic retention, and actual download/ACS snapshot coverage. Reopened those tasks; the approved frozen policy is unchanged. Preserve versioned UUIDs, non-destructive downgrade, positional connection compatibility, and passing migration-adoption coverage.

## Review Triage Log

| Review finding | Verdict | Route | Evidence |
|---|---|---|---|
| Blind Hunter: an `A → B → A` checksum sequence reuses v1 | medium | patch | The repository and raw SQL search all historical checksums; the matrix defines retry relative to the latest retained version, so a changed refresh back to A must create v3. |
| Blind Hunter: raw advisory lock fails under autocommit | medium | patch | `pg_advisory_xact_lock` is issued in a statement before the registration statement; an autocommit supplied connection releases it between statements. |
| Blind Hunter: direct completed registration can name arbitrary, unverified bytes | high | resolved: frozen Decision | The frozen universal retained-path promise conflicts with the explicitly preserved low-level repository API and real callers that register virtual or preexisting paths; the intended trusted boundary is not defined. |
| Blind Hunter: registering verified bytes cannot supersede a matching legacy row | medium | patch | The checksum-only reuse path preserves the legacy `local_path`, so the canonical retained copy is not the current catalog evidence. |
| Blind Hunter: failed download state is no longer recorded | medium | resolved: frozen Decision | The prior mutable failed-row behavior conflicts with the frozen prohibition on changing completed evidence. The spec does not choose between an immutable failure-attempt model and deliberately removing failure provenance. |
| Blind Hunter: range-ignored resume corrupts a partial file | false | rejected | `bulk.download` resets `existing` and opens the partial file with `wb` when a range request receives a non-206 response before writing bytes. |
| Blind Hunter: no referenced-v1 acceptance test | medium | patch | Existing changed-content coverage proves rows/files but does not create and resolve an artifact foreign-key reference after v2 admission. |
| Blind Hunter: concurrent `bulk.download` shares mutable staging | medium | patch | Two workers can concurrently write, promote, or unlink the same `.part` path before database locking occurs. |
| Edge Case Hunter: range-ignored stale partial | false | rejected | The same `response.status_code != 206` guard truncates and restarts the partial file before output. |
| Edge Case Hunter: simultaneous staging writers | medium | patch | The unchanged shared partial pathname has no file-level serialization; the bad outcome is independent of registration serialization. |
| Edge Case Hunter: failed acquisition loses catalog failure evidence | medium | resolved: frozen Decision | Same unresolved failure-attempt model choice as the Blind Hunter finding; completed evidence must not be repointed or mutated. |
| Edge Case Hunter: repository route accepts unverified completed paths | high | resolved: frozen Decision | Same missing trusted-boundary decision as the Blind Hunter finding; a universal enforcement change affects preserved compatibility and non-file sources. |
| Verification Gap: ACS snapshots select artifact without version ordering | medium | patch | `browser.sync_acs` can select any historical `tables-<year>` row, so a refreshed manifest may produce a snapshot linked to stale bytes. |
| Verification Gap: loaders have no two-version selection tests | medium | patch | The new descending ordering is only exercised with one row, so omission/regression would remain undetected. |
| Verification Gap: raw explicit-version lookup has no history test | medium | patch | Explicit raw lookup is tested only where v1 is the sole row; it does not prove the SQL respects the requested version. |
| Verification Gap: supplied-connection concurrency has no coverage | medium | patch | The session branch is concurrent-tested, but separate raw connections are not, leaving the compatibility branch's locking promise unproved. |

## Design Notes

Use the content checksum as part of the retained filename or directory, but retain the logical `artifact_key` as the grouping key. A `.part` file is only staging; it must not replace a retained version.

## Verification

**Commands:**
- `just check-fast` -- expected: Ruff and all non-DB tests pass.
- `uv run --extra ingest --extra spatial pytest tests/test_artifact_versioning.py` -- expected: immutable versioning and migration cases pass serially.
- `just check-db` -- expected: all DB/integration tests pass serially.
