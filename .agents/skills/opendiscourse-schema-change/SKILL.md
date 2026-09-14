---
name: opendiscourse-schema-change
description: 'Change OpenDiscourse warehouse schema the approved way. Use when adding tables, columns, Alembic revisions, SQLModel models, sql/ bootstrap, or when the user mentions migrations, PostGIS, pgvector, or core/fact/stage.'
---

# OpenDiscourse schema change

Read `AGENTS.md` and ADR-0001 (`docs/adr/0001-postgres-system-of-record.md`)
first.

## When to use

- New or altered catalog/core/fact/ingest/stage tables
- Alembic vs raw SQL questions
- Embedding/pgvector column type changes

## Do

- Database name is `opendiscourse` (CI: `opendiscourse_test`). Postgres/PostGIS
  is the system of record.
- Models: `src/opendiscourse_research/models/`. Revisions:
  `migrations/versions/`. Baseline `d207df35ca10` (`migrations/baseline/`,
  `scripts/render_baseline_ddl.py --check`).
- Alembic for catalog/core/fact/ingest/stage contracts. Cut a reversible
  revision; keep `repositories/` SQL-only.
- Raw psycopg only for COPY, set-based promotion, OpenStates FDW, and
  caller-supplied legislative transactions.
- Runtime SQL lives in `sql/query/`. `sql/NNN_*.sql` is bootstrap/legacy
  reference, not a second migration path.
- Bound parameters only. JSON via `psycopg.types.json.Jsonb`.
- `dlt` writes `stage` only, never `core`/`fact`.

## Do not

- Invent news, stocks, or corruption-score domains.
- Dual-write durable facts to DuckDB, Parquet, Qdrant, or files as authority.
- Promote `core.embedding.vector_values` from `real[]` to pgvector without a
  new ADR (extension may already be installed).
- Physically copy the OpenStates database into `opendiscourse`.
- Make `censusdis` a required dependency.
