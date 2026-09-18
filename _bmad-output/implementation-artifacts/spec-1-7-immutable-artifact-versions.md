---
title: 'Story 1.7: Immutable Artifact Versions'
type: 'feature'
created: '2026-09-17'
status: 'done'
baseline_commit: '8a1b90664d9f79af99ed5e3d12ba45610b666793'
route: 'dispatch'
review_loop_iteration: 0
context:
  - '_bmad-output/specs/spec-opendiscourse/schema-invariants.md'
  - 'docs/adr/0002-schema-invariants.md'
  - '_bmad-output/planning-artifacts/architecture/architecture-opendiscourse-2026-09-14/ARCHITECTURE-SPINE.md'
  - '_bmad-output/planning-artifacts/epics.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** `ingest.artifact` currently enforces uniqueness on `(dataset_id, artifact_key)` and updates `checksum_sha256` in-place on conflict, mutating existing evidence rows referenced by `core` and `fact` records whenever an upstream bulk file is refreshed with new bytes.

**Approach:** Introduce an Alembic migration adding `artifact_version` (integer, default 1) to `ingest.artifact`, replace the unique constraint with `(dataset_id, artifact_key, artifact_version)`, and update `register_artifact()` so that matching checksums perform idempotent updates on the current version while changed checksums create new immutable artifact versions with distinct IDs.

## Boundaries & Constraints

**Always:**
- Use Alembic for the schema migration chained off current head `b1e5c8a3d942`.
- Keep the baseline DDL fingerprint (`migrations/baseline/d207df35ca10.sql`) intact and unmodified.
- Preserve existing foreign keys from `core` and `fact` pointing to `ingest.artifact.artifact_id` (UUID PK).
- Maintain backward compatibility of `register_artifact()` and `get_artifact()` function signatures and return dict schemas.
- Ensure `get_artifact()` defaults to returning the latest canonical version (`ORDER BY artifact_version DESC LIMIT 1`) while supporting explicit `version` selection.
- Update `bulk.py`'s `_upsert()` to use version-aware registration instead of conflicting on the dropped constraint.
- Test against real PostgreSQL / PostGIS without pytest-xdist (`-n` forbidden for DB tests).

**Never:**
- Do not mutate or overwrite `checksum_sha256` on an existing artifact row when incoming checksum differs.
- Do not drop or recreate `ingest.artifact.artifact_id` (must remain UUID PK).
- Do not break existing loaders (`legload.py`, `acs_load.py`, `cbp_load.py`, `dhc_load.py`).
- Do not mix work into other feature branches or epics.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Initial Registration | `register_artifact(dataset, url, path, key, checksum="hash1")` | Creates version 1 with new UUID `artifact_id`, returns row dict with `artifact_version=1` | N/A |
| Unchanged Retry (Same Hash) | Call `register_artifact(dataset, url, path, key, checksum="hash1", status="loaded")` on existing v1 | Returns existing v1 `artifact_id` and `artifact_version=1`; updates status/metadata; does not create a new row | N/A |
| Lifecycle Transition (Planned -> Downloaded) | Initial row has `checksum_sha256=None, status="planned"`; register with `checksum="hash1", status="downloaded"` | Updates v1 with the checksum and status; does not create v2 | N/A |
| Changed-Content Refresh | Existing v1 has `checksum="hash1"`; call `register_artifact` with `checksum="hash2"` | Inserts version 2 with new UUID `artifact_id`, `artifact_version=2`, `checksum="hash2"`; v1 remains unchanged with `checksum="hash1"` | N/A |
| Historical Queryability | Artifact has v1 (`hash1`) and v2 (`hash2`) | `get_artifact(dataset, key, version=1)` returns v1; `get_artifact(dataset, key)` returns latest v2 | Returns `None` if version does not exist |
| Existing Core References Intact | `core.document` references v1 `artifact_id`; v2 is registered | `core.document.artifact_id` still references v1; checksum on v1 row is still `hash1` | Foreign key remains valid |
| Canonical State Re-pointer | Loader processes v2 content and updates `core.document` | `core.document.artifact_id` is updated to v2 `artifact_id` | Foreign key remains valid |
| Rollback / Replay | Existing v1 (`hash1`) and v2 (`hash2`); upstream restores `hash1` | `register_artifact` with `hash1` creates v3 with `artifact_version=3, checksum="hash1"`; all versions remain distinct and queryable | N/A |
| Duplicate Explicit Version Violation | Direct SQL insert of duplicate `(dataset_id, artifact_key, artifact_version)` | Insert fails | `IntegrityError` / UniqueViolation (`artifact_dataset_id_artifact_key_version_key`) |

</frozen-after-approval>

## Code Map

- `migrations/versions/c5e2d1a4f783_immutable_artifact_versions.py` -- New Alembic revision: add `artifact_version` column, drop `artifact_dataset_id_artifact_key_key`, create `artifact_dataset_id_artifact_key_version_key` and index
- `src/opendiscourse_research/models/catalog.py` -- Update `_artifact` Table definition: add `artifact_version`, update `UniqueConstraint` and `Index`
- `src/opendiscourse_research/repositories/legislation.py` -- Update `register_artifact()` with version-aware creation/update logic, and update `get_artifact()` with version ordering
- `sql/query/legislation/register_artifact.sql` -- Update SQL query for register_artifact
- `sql/query/legislation/get_artifact.sql` -- Update to order by `artifact_version DESC LIMIT 1`
- `src/opendiscourse_research/ingestion/bulk.py` -- Update `_upsert()` to use version-aware registration
- `tests/test_artifact_versioning.py` -- New comprehensive test suite covering unchanged retry, changed-content refresh, historical queryability, rollback/replay, and loader compatibility
- `tests/test_provenance_identity_contracts.py` -- Update `test_duplicate_artifact_key_rejected` to assert on `artifact_dataset_id_artifact_key_version_key`
- `tests/test_persistence_foundation.py` -- Update migration chain tests to include new revision `c5e2d1a4f783`

## Tasks & Acceptance

**Execution:**
- [x] `migrations/versions/c5e2d1a4f783_immutable_artifact_versions.py` -- create reversible Alembic migration for `artifact_version` and revised unique constraint -- establishes schema substrate
- [x] `src/opendiscourse_research/models/catalog.py` -- update SQLAlchemy/SQLModel metadata for `ingest.artifact` -- synchronizes application models with schema
- [x] `sql/query/legislation/get_artifact.sql` & `sql/query/legislation/register_artifact.sql` -- update SQL queries -- ensures raw psycopg callers use versioned semantics
- [x] `src/opendiscourse_research/repositories/legislation.py` -- update `register_artifact` and `get_artifact` -- implements immutable versioning logic
- [x] `src/opendiscourse_research/ingestion/bulk.py` -- update `_upsert` -- ensures bulk pipelines adhere to versioned artifacts
- [x] `tests/test_provenance_identity_contracts.py` & `tests/test_persistence_foundation.py` -- update existing migration/constraint tests -- verifies schema continuity
- [x] `tests/test_artifact_versioning.py` -- implement full test suite for Story 1.7 -- verifies unchanged retry, changed-content refresh, rollback/replay, and loader compatibility

**Acceptance Criteria:**
- Given an existing artifact for `(dataset_id, artifact_key)` with checksum A, when `register_artifact()` is called with checksum A, then the existing artifact row is returned without creating a new version.
- Given an existing artifact for `(dataset_id, artifact_key)` with checksum A referenced by a `core` record, when `register_artifact()` is called with checksum B, then a new artifact row with `artifact_version=2` and checksum B is created, and the existing `core` record continues to reference the version 1 artifact with checksum A.
- Given multiple versions of an artifact, when `get_artifact(dataset_id, artifact_key)` is called, then the latest version is returned; when `get_artifact(dataset_id, artifact_key, version=1)` is called, version 1 is returned.
- Given an upstream file rollback from checksum B back to checksum A, when `register_artifact()` is called with checksum A, then a new immutable artifact version is created and canonical rows can be updated to point to the supporting evidence.

## Implementation Notes

- Added Alembic revision `c5e2d1a4f783` adding `artifact_version` (integer, default 1), dropping `artifact_dataset_id_artifact_key_key`, and adding `artifact_dataset_id_artifact_key_version_key` unique constraint over `(dataset_id, artifact_key, artifact_version)`. Fully reversible via `downgrade()`.
- Synchronized `src/opendiscourse_research/models/catalog.py` `_artifact` table metadata with the schema.
- Updated `register_artifact` in `legislation.py` and `sql/query/legislation/register_artifact.sql` to implement version-aware logic: locking latest row `FOR UPDATE`, updating in-place on matching checksums or null-checksum lifecycle transitions, and inserting a new version on differing checksums.
- Updated `get_artifact` in `legislation.py` and `sql/query/legislation/get_artifact.sql` to support optional explicit `version` while defaulting to the latest canonical version (`ORDER BY artifact_version DESC LIMIT 1`).
- Updated `bulk._upsert()` to use version-aware registration instead of conflicting on the dropped constraint.
- Updated `acs_load.py`, `cbp_load.py`, `dhc_load.py`, `pep_load.py`, and `tiger_load.py` `_artifact` queries to order by `artifact_version.desc()`.
- Added `tests/test_artifact_versioning.py` covering unchanged retry, changed-content refresh, historical queryability, rollback/replay, loader compatibility, duplicate version rejection, and raw psycopg callers via `conn`.
- Added `test_artifact_versioning.py` to `tests/conftest.py` `_DB_FILES`.
- Verified all fast checks (`just check-fast`) and all 82 DB/integration tests (`just check-db`) pass cleanly.

## Review Triage Log

- `high`: Pre-download calls with null checksum in `bulk._upsert()` and `legislation.register_artifact()` mutate prior completed version rows to `downloading`/`failed`. Guard so pre-download unchecksummed calls do not mutate existing completed versions. (Route: patch)
- `medium`: `browser.py:sync_acs` queries `ingest.artifact` without `.order_by(artifact_version.desc())`, risking picking up an older version when multiple versions exist. (Route: patch)
- `medium`: Missing explicit multi-version loader resolution tests in `tests/test_artifact_versioning.py`. (Route: patch)
- `low`: `register_artifact.sql` metadata concatenation should use `COALESCE(%(metadata)s::jsonb, '{}'::jsonb)` to prevent setting NULL on nullable JSONB. (Route: patch)
- `low`: Migration `downgrade()` in `c5e2d1a4f783` should deduplicate multi-version rows to latest version before restoring unique constraint `(dataset_id, artifact_key)`. (Route: patch)

## Design Notes

Version determination in `register_artifact`:
```python
latest = get_latest_artifact(dataset_id, artifact_key, for_update=True)
if latest is None:
    insert_version(version=1, checksum=checksum)
elif checksum is not None and latest["checksum_sha256"] is not None and checksum != latest["checksum_sha256"]:
    insert_version(version=latest["artifact_version"] + 1, checksum=checksum)
else:
    update_version(artifact_id=latest["artifact_id"], status=status, ...)
```
