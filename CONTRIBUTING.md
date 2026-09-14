# Contributing

## Setup

See `docs/getting-started.md` for the fastest path to a running database.

## Running tests

Tests use `pytest`, which also collects the existing `unittest.TestCase`
tests unchanged. Prefer the canonical commands (requires `just`, or run the
matching `scripts/ci/` shell):

```bash
just check-fast    # ruff check src + non-DB pytest, parallel
just check-db      # PostgreSQL/PostGIS tests
just check-full    # entire suite (CI integration job)
just check-lint    # ruff + ty over src and tests (not yet a merge gate)
just check-sql     # sqlfluff (advisory)

# Single file / class / test
uv run pytest tests/test_govbackfill.py
```

CI (`.github/workflows/test.yml`) runs `check-fast` without a database, then
the PostGIS service job runs `check-full`. Tests marked `db` / `integration`
need `OPENDISCOURSE_TEST_DATABASE_URL` or testcontainers; `live` tests must
not run in ordinary CI. Write tests alongside the code that needs them, not
after; see `AGENTS.md` for the full engineering standard.

Pack a repo snapshot for an external model with `npx repomix` (config:
`repomix.config.json`).

## Lint/format

```bash
uv run ruff check src
uv run ruff format src
uv run ty check src tests
```

`ruff check src` is part of the fast CI lane. `ruff format`, `ty`, and
`sqlfluff` are installed but the rest of the tree is not yet clean under
them — don't add new violations.

## Adding a new data source

Run `research-db new-provider <name>` to generate a starter provider
module, test stub, and a commented `inventory/sources.yaml` entry, then
follow `docs/adding-a-provider.md`, which lists the required behaviors and
walks through how the FRED provider implements each one.

## Commits and branches

Small, cohesive commits, one logical change each, with a concise imperative
subject line. See `AGENTS.md`'s "Git and GitHub workflow" section for the
full convention this project follows.
