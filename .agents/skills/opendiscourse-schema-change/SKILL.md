---
name: opendiscourse-schema-change
description: 'Change OpenDiscourse warehouse schema the approved way. Use when adding tables, columns, Alembic revisions, SQLModel models, sql/ bootstrap, or when the user mentions migrations, PostGIS, pgvector, or core/fact/stage.'
---

# OpenDiscourse schema change

Read `AGENTS.md`, ADR-0001 (`docs/adr/0001-postgres-system-of-record.md`),
and ADR-0002 (`docs/adr/0002-schema-invariants.md`) first.

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
  revision; keep `repositories/` SQL-only. Follow ADR-0002
  (`docs/adr/0002-schema-invariants.md`): UUID PKs, typed grains, source-derived
  evidence, text session columns are compatibility only.
- Raw psycopg only for COPY, set-based promotion, OpenStates FDW, and
  caller-supplied legislative transactions.
- Runtime SQL lives in `sql/query/`. `sql/NNN_*.sql` is bootstrap/legacy
  reference, not a second migration path.
- Bound parameters only. JSON via `psycopg.types.json.Jsonb`.
- `dlt` writes `stage` only, never `core`/`fact`.
- Shared attributes (ADR-0005, Story 10.2): a value two sources can describe for one entity gets an assertion table
  (`core.person_name_source`, `core.geography_name_source` are the pattern: entity, kind, value, `dataset_id`,
  `source_vintage`, artifact OR payload, run; unique `NULLS NOT DISTINCT`), a ranking in `inventory/precedence.yaml`, and
  a resolver-owned column with a `name_source_id`-style pointer, all in the same change that adds the second source.
  Loaders write assertions (`repositories/names.py`), never the resolved column; `research-db resolve` is the writer.
  A guard trigger refuses other writes to a resolved row (SQLSTATE `42501`); it stops accidental writes, not a
  determined one (any session can set `opendiscourse.resolver`). To delete assertions a resolved row points at, the
  wipe transaction sets that flag and nulls the pointer first.

## Do not

- Invent news, stocks, or corruption-score schema domains (derived scorecard marts come later). Do not load market bars
  because `core.instrument` / `fact.market_bar` exist. Do not promote
  `stage.fec_row` while Epic 7 is closed.
- Dual-write durable facts to DuckDB, Parquet, Qdrant, or files as authority.
- Promote `core.embedding.vector_values` from `real[]` to pgvector without a
  new ADR (extension may already be installed).
- Physically copy the OpenStates database into `opendiscourse`.
- Make `censusdis` a required dependency.
