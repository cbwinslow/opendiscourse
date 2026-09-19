# Epic 1 Context: Development substrate

<!-- Compiled from planning artifacts. Edit freely. Regenerate with compile-epic-context if planning docs change. -->

## Goal

Provide the operating foundation that lets OpenDiscourse evolve safely as a reproducible, provenance-aware research warehouse. This epic establishes the agent and delivery rules, durable schema/provenance invariants, fast verification, and repository governance needed to ensure that evidence remains defensible as sources and their remote files change over time. Most foundation stories are already landed; the remaining integrity work is immutable artifact versioning, with the optional solo GitHub ruleset handled only if repository permissions permit.

## Stories

- Story 1.1: AGENTS.md constitution
- Story 1.2: ADR-0001 Postgres system of record
- Story 1.3: OpenDiscourse skills
- Story 1.4: GitHub ruleset (optional solo)
- Story 1.5: Schema invariants ADR
- Story 1.6: Provenance and identity contract tests
- Story 1.7: Immutable artifact versions

## Requirements & Constraints

- Use BMAD Method plus TEA as the sole software specification process. Route XS/S changes through build, M changes through a spec then build, and L/XL changes through the established planning path. Keep `inventory` contracts and plans as the authority for data specification; do not create a competing planning system.
- Treat current code and tests as the highest authority, followed by schema/migrations, adopted architecture decisions, and active story specifications. Lower-priority discussions and agent memory must not override them.
- Maintain a fast CI lane consisting of source linting and non-database pytest coverage. Database tests require PostGIS and must remain serial; use the warehouse testing approach rather than browser-first testing.
- Every source-derived fact must be traceable to its ingest run, provider/dataset context, request parameters, source URL, checksum, and retained raw payload or artifact. Capacity checks must refuse a bulk acquisition when size information is unavailable or storage budget is insufficient.
- Preserve historical evidence: refreshing a logical remote file with different bytes must create a distinct immutable artifact/version identity. Existing rows must continue to resolve to the exact historical checksum they reference, while current canonical rows point to evidence for their current value.
- Artifact versioning must cover unchanged retries, changed-content refreshes, and rollback/replay. It must not silently redefine existing evidence rows.
- Source-derived canonical records need direct evidence and stable, idempotent identity. Duplicate external person identifiers and duplicate artifacts must be rejected; audit remaining source-evidence constraints where applicable.
- The optional repository ruleset should require pull requests and CI for `main`, disallow force-pushes, and use squash merging without requiring an additional human reviewer for the solo operator.

## Technical Decisions

- PostgreSQL 17 with PostGIS, database `opendiscourse`, is the sole system of record for durable facts. DuckDB, PostgREST, and Parquet are derived access layers, not competing authorities.
- Schema contracts for catalog, ingest, stage, core, and fact are managed through Alembic. A provenance/versioning change that changes artifact identity requires an Alembic migration and loader compatibility tests; do not hide it as a behavior-only change to artifact registration.
- Retain raw bytes in the lake and keep evidence identity immutable. Staging is the only layer permitted to evolve automatically; promotion into canonical layers remains reviewed and keyed.
- Canonical schema uses internal UUID keys plus external identifier tables. Preserve source identifiers, use typed grains and idempotent unique keys, and do not infer new ingest scope merely because supporting schema exists.
- Use bound parameters for SQL. Raw psycopg is limited to COPY, set-based promotion, FDW work, and caller-supplied legislative transactions; ordinary persistence follows the repository boundary.
- Long-running operations must surface progress, resumability, and actionable failures through the project feedback mechanism.
- Keep secrets and environment files out of version control. New public modules require docstrings, and relevant failure, idempotency, resume, and provenance tests ship with a change.

## Cross-Story Dependencies

- Story 1.7 builds on the provenance and identity contract baseline in Story 1.6. Keep its migration and loader compatibility work isolated from Connector/FRED and OpenStates promotion branches; it is a cross-cutting integrity change.
- The immutable-artifact gap remains open until Story 1.7 is completed. Until then, do not claim that a refreshed-in-place logical artifact preserves historical evidence.
- Story 1.4 is operationally optional and depends on the operator having sufficient GitHub permissions to apply the ruleset.
