---
title: 'Story 1.6: Provenance & Identity Contract Tests'
type: 'feature'
created: '2026-09-17'
status: 'done'
baseline_commit: '337531bd8431266aa69cbe59c1a7a6b1dffb2086'
route: 'dispatch'
review_loop_iteration: 0
context:
  - '_bmad-output/specs/spec-opendiscourse/schema-invariants.md'
  - 'docs/adr/0002-schema-invariants.md'
  - '_bmad-output/planning-artifacts/epics.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Class-A source-derived tables must reject source-less rows, and duplicate identity keys or artifacts must fail at the database boundary to enforce provenance and identity invariants established in ADR-0002. Currently, `core.geography_boundary` and `core.document` lack evidence CHECK constraints, and contract tests for the required invariants are uncommitted.

**Approach:** Add Alembic migration to apply the missing CHECK constraints on `core.geography_boundary` and `core.document`, synchronize SQLModel metadata, update any test fixtures inserting source-less boundaries, and add contract test cases in `tests/test_provenance_identity_contracts.py` covering all six invariant specifications from `schema-invariants.md`.

## Boundaries & Constraints

**Always:**
- Use Alembic for schema changes on `core` (reversible revision chained off current head `a4f8c2e9b176`).
- Keep baseline DDL (`migrations/baseline/d207df35ca10.sql`) intact and unaltered.
- Enforce evidence constraint: `source_artifact_id IS NOT NULL OR source_payload_id IS NOT NULL` (for `core.geography_boundary`) and `artifact_id IS NOT NULL OR source_payload_id IS NOT NULL` (for `core.document`).
- Retain UUID primary keys, typed grains, and unique constraints.
- Test against real PostgreSQL / PostGIS using `catalog_database` fixture pattern without xdist (`-n` forbidden for DB tests).

**Never:**
- Do not mix work into the FRED branch or retroactively edit Story 8.1.
- Do not require evidence on Class-B identity/reference tables (`core.person`, `core.geography`, `core.bill`, etc.).
- Do not promote pgvector or modify `core.embedding.vector_values` column type without an ADR.
- Do not modify or drop columns without migration.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Missing evidence on `core.membership` | Insert row with `source_artifact_id=None, source_payload_id=None` | Insert fails | `IntegrityError` / CheckViolation (`membership_check`) |
| Missing evidence on `fact.member_vote` | Insert row with `source_artifact_id=None, source_payload_id=None` | Insert fails | `IntegrityError` / CheckViolation (`member_vote_source_evidence`) |
| Missing evidence on `core.geography_boundary` | Insert row with `source_artifact_id=None, source_payload_id=None` | Insert fails | `IntegrityError` / CheckViolation (`geography_boundary_check`) |
| Missing evidence on `core.document` | Insert row with `artifact_id=None, source_payload_id=None` | Insert fails | `IntegrityError` / CheckViolation (`document_check`) |
| Duplicate person external ID | Insert two `core.person_identifier` with same `(namespace, external_id)` | Second insert fails | `IntegrityError` / UniqueViolation |
| Duplicate artifact key | Insert two `ingest.artifact` with same `(dataset_id, artifact_key)` | Second insert fails | `IntegrityError` / UniqueViolation |
| Vector dimensions mismatch | Insert `core.embedding` where cardinality of `vector_values` != `dimensions` | Insert fails | `IntegrityError` / CheckViolation (`embedding_check`) |
| Vector dimensions match | Insert `core.embedding` where cardinality of `vector_values` == `dimensions` | Insert succeeds | N/A |
| Multi-vintage TIGER boundary | Insert boundaries for same `geography_id` with different `boundary_vintage` (e.g. 2020 and 2024) | Both boundaries stored and queryable | N/A |
| Duplicate TIGER boundary vintage | Insert second boundary with same `(geography_id, boundary_vintage)` | Insert fails | `IntegrityError` / UniqueViolation |

</frozen-after-approval>

## Code Map

- `migrations/versions/b1e5c8a3d942_audit_class_a_evidence_checks.py` -- New Alembic migration adding `geography_boundary_check` and `document_check`
- `src/opendiscourse_research/models/core.py` -- Add `CheckConstraint` to `core_geography_boundary` and `core_document`
- `tests/conftest.py` -- Register `test_provenance_identity_contracts.py` in `_DB_FILES`
- `tests/test_persistence_foundation.py` -- Update `test_typed_postgis_boundary_mapping_round_trips_geometry` to include valid evidence foreign key
- `tests/test_provenance_identity_contracts.py` -- Dedicated contract test suite validating all invariants and CHECK constraints

## Tasks & Acceptance

**Execution:**
- [x] `migrations/versions/b1e5c8a3d942_audit_class_a_evidence_checks.py` -- Create migration to add `geography_boundary_check` and `document_check` constraints with reversible downgrade.
- [x] `src/opendiscourse_research/models/core.py` -- Add `CheckConstraint` definitions on `core_geography_boundary` and `core_document` matching the migration.
- [x] `tests/test_persistence_foundation.py` -- Update `test_typed_postgis_boundary_mapping_round_trips_geometry` to associate with a valid `ingest.raw_payload` or `ingest.artifact` row.
- [x] `tests/conftest.py` -- Include `test_provenance_identity_contracts.py` in `_DB_FILES` so it is appropriately marked as `db` and `integration`.
- [x] `tests/test_provenance_identity_contracts.py` -- Implement pytest DB contract tests for source-less rejection, duplicate rejection, embedding dimension check, and TIGER multi-vintage preservation.

**Acceptance Criteria:**
- Given a PostgreSQL database with all migrations applied up to head, when attempting to insert source-less rows into class-A tables (`core.membership`, `fact.member_vote`, `core.geography_boundary`, `core.document`), then the database rejects them with check constraint integrity errors.
- Given existing external person identifiers and ingest artifacts, when duplicate rows with identical uniqueness keys are inserted, then the database rejects them with unique constraint integrity errors.
- Given `core.embedding`, when inserting vectors whose cardinality differs from `dimensions`, the database rejects the row; when cardinality equals `dimensions`, the insert succeeds.
- Given historical TIGER vintages for the same geographic entity, when multiple vintages are inserted, all are preserved without overwriting.
- Given `just check-fast` and `just check-db`, all linters and tests pass without regression.

## Implementation Notes

## Spec Change Log

## Review Triage Log

| Layer | Finding | Verdict | Evidence | Route |
|---|---|---|---|---|
| Edge Case / Blind | `tests/test_provenance_identity_contracts.py:280`: `_contract_payload` returns string instead of UUID | low | `IngestionRun.store_payload` returns string representation of payload UUID; cast to `uuid.UUID` avoids type contract mismatch | patch |
| Blind | `tests/test_provenance_identity_contracts.py:248`: `catalog_database` external_url cleanup omits `_engine.cache_clear()` | low | Adding cache clear in finally block ensures connection pool does not retain stale URL | patch |
| Blind | `tests/test_provenance_identity_contracts.py:381`: Missing `source_payload_id` branch in membership and vote acceptance | low | Adding payload acceptance assertions ensures full check constraint coverage | patch |
| Blind | `tests/test_provenance_identity_contracts.py`: Missing `core.document` natural key uniqueness test | false | Document uniqueness is not part of Story 1.6 contract test scope | reject |
| Blind | `tests/test_persistence_foundation.py:457`: Downgrade check does not assert constraints are absent at base | low | Asserting constraints dropped on downgrade confirms reversible migration behavior | patch |
| Blind | `tests/test_provenance_identity_contracts.py`: Missing embedding boundary tests (`dimensions <= 0`) | false | Story 1.6 explicitly specifies `cardinality(vector_values) = dimensions` contract test | reject |
| Blind | `tests/test_provenance_identity_contracts.py`: Missing fact table non-null tests | false | Class-A fact tables already enforce NOT NULL columns tested in foundation suite | reject |
| Blind | `tests/test_provenance_identity_contracts.py:548`: Unanchored `IntegrityError` assertions in uniqueness tests | low | Anchoring error pattern verifies specific unique constraint failure | patch |
| Blind | `docs/schema-snapshot`: Schema snapshots not updated with new check constraints | defer | Snapshots are exported via `just export-schema` against live cluster | defer |
| Blind | `tests/test_provenance_identity_contracts.py:650`: Plain insert used instead of upsert for TIGER vintage test | false | Database contract test verifies storage coexistence across vintages without overwriting | reject |
| Verification Gap | No verification gaps found | false | Layer confirmed complete test coverage | reject |

## Design Notes

The check constraint for `core.geography_boundary` uses:
`source_artifact_id IS NOT NULL OR source_payload_id IS NOT NULL`
named `geography_boundary_check`.

The check constraint for `core.document` uses:
`artifact_id IS NOT NULL OR source_payload_id IS NOT NULL`
named `document_check`.

Downgrade drops both constraints cleanly.

## Verification

**Commands:**
- `uv run ruff check src tests` -- expected: All checks passed
- `uv run pytest -m "not db and not slow and not live and not e2e" -n auto` -- expected: 111+ passed
- `uv run --extra ingest --extra spatial pytest tests/test_provenance_identity_contracts.py` -- expected: all contract tests pass
- `uv run --extra ingest --extra spatial pytest tests/test_persistence_foundation.py -k "test_alembic_check_detects_no_unmigrated_model_changes or test_alembic_adoptions_can_downgrade_and_reupgrade"` -- expected: migrations cleanly upgrade, downgrade, and sync with models
