# Canonical developer/agent commands. GitHub Actions must call these same recipes.

set dotenv-load := false

default:
    @just --list

# Fast PR loop: lint src + deterministic non-DB tests (parallel).
check-fast:
    uv run ruff check src
    uv run pytest -m "not db and not slow and not live and not e2e" -n auto --dist worksteal

# Static analysis that is installed but not yet a merge gate (tree is not clean).
check-lint:
    uv run ruff check src tests
    uv run ruff format --check src tests
    uv run ty check src tests

# PostgreSQL/PostGIS tests. Requires OPENDISCOURSE_TEST_DATABASE_URL or testcontainers.
check-db:
    uv run --extra ingest --extra spatial pytest -m "db or integration"

# Full suite, matching the existing CI integration job.
check-full:
    uv run --extra ingest --extra spatial pytest

# Live provider smokes. Never run in ordinary CI.
check-live:
    uv run pytest -m live

# SQL lint (advisory; existing sql/ is not yet clean).
check-sql:
    uv run sqlfluff lint sql
