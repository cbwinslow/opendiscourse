# Contributing

## Setup

See `docs/getting-started.md` for the fastest path to a running database.

## Running tests

Tests use `pytest`, which also collects the existing `unittest.TestCase`
tests unchanged. CI runs them against a real `postgis/postgis:17-3.5` service
container (`.github/workflows/test.yml`):

```bash
uv run --extra ingest --extra spatial pytest

# Single file / class / test
uv run pytest tests/test_govbackfill.py
```

Tests that touch a real database are skipped automatically unless
`OPENDISCOURSE_TEST_DATABASE_URL` is set — everything else runs against
fakes/mocks with no database required. Write tests alongside the code that
needs them, not after; see `AGENTS.md` for the full engineering standard.

## Lint/format

```bash
ruff check src/
ruff format src/
```

`ruff` is available but not a CI gate yet, and the tree is not currently
clean under it. Don't assume a passing `ruff check` is required to merge,
but don't add new violations either.

## Adding a new data source

Run `research-db new-provider <name>` to generate a starter provider
module, test stub, and a commented `inventory/sources.yaml` entry, then
follow `docs/adding-a-provider.md`, which lists the required behaviors and
walks through how the FRED provider implements each one.

## Commits and branches

Small, cohesive commits, one logical change each, with a concise imperative
subject line. See `AGENTS.md`'s "Git and GitHub workflow" section for the
full convention this project follows.
