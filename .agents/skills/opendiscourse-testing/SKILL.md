---
name: opendiscourse-testing
description: 'Run and write OpenDiscourse warehouse tests. Use when adding pytest, choosing markers, running just check-fast or check-db, or when the user mentions testcontainers or live tests. Not for product behavior that belongs in connector, schema-change, or provenance skills.'
---

# OpenDiscourse testing

Use `uv run` / `just`. Bare `pytest` or `ruff` may miss the project environment.

## When to use

- Choosing `unit` / `db` / `integration` / `slow` / `live` / `e2e` markers
- Matching CI before a PR (`just check-fast`)
- Ingest changes that need failure, idempotency, resume, and provenance cases

## Do

- Fast lane (CI `fast` job): `just check-fast` — `ruff check src` plus
  `pytest -m "not db and not slow and not live and not e2e" -n auto --dist worksteal`.
- DB tests: `just check-db` (`uv run --extra ingest --extra spatial pytest -m
  "db or integration"`). One PostGIS server is started for the run, or the
  server in `OPENDISCOURSE_TEST_DATABASE_URL` is used. Migrations run once
  into a template database; each test module gets its own copy. Do not start
  a container per module. Do not pass `-n`: a template cannot be copied while
  another session is connected to it.
- Full suite: `just check-full`. Never run `-m live` in ordinary CI.
- App DSN default: `postgresql:///opendiscourse?port=5434`. Compose fallback
  port `5433`, database still `opendiscourse`.
- TEA target is pytest + PostGIS, not Playwright-first.
- New public modules need docstrings. Ship tests with the change.

## Do not

- Use xdist on DB tests.
- Treat `ty`, `ruff format`, or `sqlfluff` as merge gates (installed, not required).
- Expand ingest scope in a test-only change.
