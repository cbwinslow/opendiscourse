# Persistence Foundation: SQLModel/Alembic, Testing Stack, Extensions — Design

Date: 2026-08-13
Status: Approved (pending final review)

## Context

Extensive research (`docs/research/2026-08-13-project-foundations-assessment.md`) established:
- The project's core architecture (PostgreSQL/PostGIS, OCD-aligned relational schema) is validated by three independent comparisons to real, proven systems (GovTrack, OpenStates, mySociety/Popolo) — not in question here.
- The Python data-access layer (raw `psycopg3` SQL, 142 call sites across 25 files) should move to **SQLModel** (SQLAlchemy 2.0 + Pydantic combined) with **Alembic** managing migrations going forward, chosen over the lower-disruption `sqlc` alternative because it matches what the closest real comparable (OpenStates, via Django's ORM) has proven at production scale, and because a single consistent tool is easier to build on than a hybrid two-tool split.
- This is an incremental, test-gated migration of the persistence layer — explicitly **not** a rewrite. The schema, business logic, and existing test suite (64 tests) are being preserved and built upon, not discarded (see the "rewrite vs. incremental" analysis in the same research doc, citing Spolsky's *Things You Should Never Do*).
- The user explicitly wants: no half-measures on the new stack, a real testing framework (not just "add pytest"), and a genuine look at underused PostgreSQL extensions — done in the right order, not all improvised at once.

This document scopes **Phase 1: Foundation** — proving the full pattern (persistence + testing + extensions) on a bounded, representative slice of the schema, before Phase 2 migrates the remaining 24 files and Phase 3 does cleanup (removing the unused `dlt` dependency, updating docs, splitting `browser.py`).

## Goal

By the end of Phase 1: a working SQLModel + Alembic foundation proven on the `catalog.*` schema (already the running example throughout this design's research), a new pytest-based test stack running alongside the existing `unittest` suite without breaking it, and three concrete, low-risk PostgreSQL extension/index additions live in the database.

## Component 1: Testing stack

**Runner switch: `unittest` → `pytest`, non-destructively.**
Pytest natively collects and runs `unittest.TestCase`-based tests without modification — this is not a rewrite of the existing 64 tests. The CI/dev command changes from `python -m unittest discover -s tests -v` to `pytest`; every existing test keeps passing as-is. New tests, starting with this phase's own tests, are written in pytest's plain-function/fixture style, which is the ecosystem standard (confirmed: SQLAlchemy, Django, Flask, FastAPI, pandas, and NumPy all test with pytest).

**New dependencies (test-only, added to a `dev`/`test` dependency group, never shipped):**
- `pytest` — the runner.
- `pytest-cov` — coverage reporting (wraps `coverage.py`).
- `testcontainers[postgres]` — spins up a real, throwaway PostGIS container automatically for tests that need a live database, removing the current manual `OPENDISCOURSE_TEST_DATABASE_URL` provisioning step for local development. (CI's existing GitHub Actions PostGIS service container in `.github/workflows/test.yml` is unaffected and does not need to change — testcontainers is a *local development* convenience, not a CI requirement, since CI already has a real Postgres service.)
- `hypothesis` — property-based testing, for invariants (e.g., in the future district/crosswalk work: "weights per ZCTA sum to ~1.0") and for stress-testing parsers (e.g., BILLSTATUS XML) beyond hand-picked examples.
- `polyfactory` — generates valid fake instances directly from SQLModel/Pydantic model definitions, replacing hand-written test fixtures for the new SQLModel classes.

**Phase 1's own test coverage requirement:** every new SQLModel class and every ported query gets a real test — using `testcontainers` for anything touching the database (no mocking of the ORM layer itself), following this project's existing convention of testing against fakes only where a real dependency genuinely can't be used.

## Component 2: SQLModel + Alembic foundation

**Scope for Phase 1: the `catalog.*` schema only** (`catalog.provider`, `catalog.dataset`, `catalog.dataset_field`, `catalog.resource`, `catalog.resource_field`, `catalog.basket`, `catalog.basket_item` — 7 tables). This schema was chosen because it's self-contained (no complex cross-schema foreign keys into `core`/`fact`), already the concrete example used throughout the research (`browser.py`'s `sync_acs`), and touches real upsert-heavy code — proving the pattern here validates it before the larger `core`/`fact` schema migration in Phase 2.

**New base dependencies** (not optional extras — persistence is core to this project):
- `sqlmodel` (0.0.39 confirmed current)
- `alembic` (1.19.1 confirmed current)
- `geoalchemy2` (0.20.0 confirmed current) — added now even though Phase 1 doesn't touch geometry columns, so Phase 2's `core.geography_boundary` migration doesn't have to reintroduce the dependency question.

`psycopg` stays exactly as it is today — SQLAlchemy uses it as the underlying driver via the `postgresql+psycopg://` dialect. Nothing about the actual wire protocol to Postgres changes.

**Alembic adoption on an existing database (the correct sequence, not a fresh-start assumption):**
1. Define SQLModel classes for the 7 `catalog.*` tables, matching the existing `sql/002_core.sql`/`sql/008_catalog_browser.sql` definitions exactly (column names, types, constraints, defaults).
2. `alembic init` the migrations directory; configure `env.py`'s `target_metadata` to point at the SQLModel metadata.
3. Run `alembic revision --autogenerate -m "baseline: catalog schema"` — Alembic diffs "empty database" against the SQLModel metadata and generates a migration that would recreate these 7 tables.
4. **Do not run that migration normally** (the tables already exist, created by the existing `sql/` files) — instead, `alembic stamp <revision>` marks it as already-applied without executing it. This is the standard, correct pattern for adopting Alembic on a live schema: Alembic and the hand-written `sql/NNN_*.sql` files agree on the starting point, and all *future* changes to these 7 tables go through Alembic from here on.
5. The existing `sql/NNN_*.sql` convention continues to own every table Phase 1 doesn't touch (everything outside `catalog.*`) until Phase 2 migrates it the same way.

**Upsert pattern, decided (not left as an open question):** use SQLAlchemy's native `sqlalchemy.dialects.postgresql.insert(...).on_conflict_do_update(...)`, accepting the verbosity documented in the research as a known, general ORM-world tradeoff (Django itself only solved this cleanly in 4.1) rather than mixing in a second tool (raw SQL or sqlc) for just this pattern — consistency was the explicit reason SQLModel was chosen over the hybrid approach.

## Component 3: PostgreSQL extensions and indexes

Three concrete, evidence-backed additions, via a new migration `sql/023_search_extensions.sql`:

1. **`pg_trgm`** (`CREATE EXTENSION IF NOT EXISTS pg_trgm;`) + a GIN trigram index on `catalog.resource.title` — speeds up the `ILIKE '%term%'` substring-match branch already present in `browser.py`'s `search()` function. Confirmed real-world impact: 100-1000x for this exact query shape.
2. **`unaccent`** (`CREATE EXTENSION IF NOT EXISTS unaccent;`) — normalizes accented characters in search input; cheap, broadly useful, no downside.
3. **A functional GIN index on the existing full-text-search expression** already used in `search()`: `CREATE INDEX resource_fts_idx ON catalog.resource USING GIN (to_tsvector('english', concat_ws(' ', resource_key, title, summary, universe, resource_type, metadata::text)));` — no new extension required (full-text search is core Postgres); this directly speeds up code that already exists and is already correct, just unindexed.

**Explicitly not done in Phase 1, with reasons:**
- **`pg_stat_statements`** — real and valuable, but requires a `shared_preload_libraries` server configuration change (a Postgres restart), which is an operational change outside what a migration file can do. Documented as a recommended manual step in `docs/runtime.md` instead of a migration.
- **`postgres_fdw`** — already correctly, deliberately designed and documented in `docs/openstates-integration.md` as an admin-only, outside-of-app-migrations setup, for least-privilege reasons. No change needed. (Optional, separate, low-priority cleanup: extract the SQL already written in that doc into a runnable `ops/admin/` script file, for operator convenience — not part of this phase.)
- **`pgvector`** — deliberately deferred per the project's own existing documented reasoning (`sql/005_ops.sql`'s comment on `core.embedding`); revisit only when real semantic-search work begins.

## Testing this phase's own work

- Every new SQLModel class: a `testcontainers`-backed test that creates a row, upserts a conflicting row, and asserts the `ON CONFLICT DO UPDATE` behavior matches the current raw-SQL behavior exactly (regression protection during the swap).
- The Alembic baseline: a test that runs `alembic upgrade head` against a fresh `testcontainers` PostGIS instance that also has the existing `sql/NNN_*.sql` files applied first, asserting no diff/no-op (proving the baseline truly matches current reality).
- The new indexes: an `EXPLAIN`-based test asserting the index is actually used for the `search()` query shapes (not just present, but effective).
- Full existing `unittest`-style suite continues running unmodified under `pytest` as the regression safety net for everything Phase 1 doesn't touch.

## Success criteria

1. `pytest` runs the full suite (old + new tests) with the same pass/skip results as the current `unittest` baseline, plus new passing tests for everything built in this phase.
2. `alembic upgrade head` and `alembic downgrade base` both work cleanly against a fresh `testcontainers` database seeded with the existing `sql/` migrations.
3. `browser.py`'s `sync_acs`/`search`/`basket`/`draft` functions are rewritten against the new SQLModel classes, with identical behavior (proven by the regression tests above), removing their raw `cur.execute()` calls.
4. The three extension/index additions are live, migrated, and demonstrated (via `EXPLAIN`) to actually change the query plan for the `search()` function.
5. No existing functionality outside `catalog.*` is touched or broken.
