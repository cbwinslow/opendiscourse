# Onboarding & Provider-Scaffold Quickstart — Design

Date: 2026-08-08
Status: Approved

## Context

OpenDiscourse's long-term goal is a reusable library of ingestion
scripts/workflows that others can use to stand up a provenance-first
research database combining bills, votes, demographics, and economic data —
and, later, to run policy-impact analysis, econ forecasting, and stock
analysis on top of it. That broader vision spans several independent
subsystems; this spec covers only the first one: making the *existing*
ingestion codebase (Census, Congress, FRED, OpenStates, Treasury providers)
actually reusable by an external contributor who has never seen the repo.

The GitHub repo (`cbwinslow/opendiscourse`) is already public but has no
LICENSE, no CONTRIBUTING.md, and its only docs are agent-oriented
(`CLAUDE.md`, `AGENTS.md`) or deep architecture references (`docs/*.md`).
Concretely:

- `compose.yaml` and `.env.example` both hardcode
  `OD_LAKE_ROOT=/home/cbwinslow/workspace/data-lake` — a path that only
  exists on the maintainer's machine. A clean clone breaks on first
  `docker compose up`.
- `compose.yaml` pins `postgis/postgis:16-3.4` while CI
  (`.github/workflows/test.yml`) runs `postgis/postgis:17-3.5` — a latent
  version inconsistency.
- Providers are plain function modules with genuinely different shapes
  (FRED: paced search + resumable cursor indexing; Congress: one-shot
  `sync()`; Census: catalog discovery plus five separate bulk-package sync
  functions). There is no shared function signature across them today, and
  `AGENTS.md` explicitly directs: "keep provider-specific behavior explicit
  at the adapter boundary" and "generalize only from demonstrated common
  needs." A single instance of rate-limiting logic (`fred.py` only) was
  checked and found not to be duplicated elsewhere, so it does not yet meet
  that bar either. A strict shared Protocol/ABC across providers was
  considered and rejected for this reason.

## Goal

An external contributor can, starting from a clean clone:
1. Get a working local database running in minutes.
2. Understand how to add their own data source, from a checklist and one
   real worked example, without reading the entire codebase first.
3. Know how to run tests/lint and propose a change.

## Explicitly out of scope

- Choosing a LICENSE — deferred; repo stays unlicensed for now.
- PyPI packaging/publishing, versioning, changelog/release process.
- A strict Protocol/ABC/class hierarchy unifying provider modules.
- Policy-impact assessment, econ forecasting, stock analysis — separate
  future sub-projects, each requiring their own design.

## Components

### a. Portable environment config

- `.env.example`: change `OD_LAKE_ROOT` and `DATA_ROOT` defaults from
  `/home/cbwinslow/workspace/data-lake` to a project-relative default
  (`./data-lake`). `.gitignore` currently only excludes `data/`, not
  `data-lake/` — add a `data-lake/` entry so the default path is never
  committed, with a comment
  telling real deployments to point it at real spacious, backed-up storage.
- `compose.yaml`: same default change for `OD_LAKE_ROOT`; bump the Postgres
  image to `postgis/postgis:17-3.5` to match CI.
- Result: `git clone && cp .env.example .env && docker compose up` works
  with zero manual edits.

### b. `docs/getting-started.md` (new, human-facing)

- Docker-first quickstart (~5 minutes): `docker compose up` → override
  `DATABASE_URL` to the port-5433 compose database → `research-db init-db`
  → `research-db browse`.
- Links out to `README.md` for the full adapter/CLI reference and to
  `CLAUDE.md`/`AGENTS.md` for agent-assisted contribution conventions.
- Does not duplicate the bare-metal production setup already documented in
  `README.md` — that remains the maintainer's documented real-deployment
  path.

### c. `CONTRIBUTING.md`

- How to run tests (`unittest`, not `pytest`, against a real PostGIS
  service container — see `CLAUDE.md`), how to run lint (`ruff check
  src/`, `ruff format src/` — available but not a CI gate yet, per
  `pyproject.toml` comments), branch/commit conventions (reference
  `AGENTS.md`'s existing git workflow section rather than restating it),
  and how to propose a new data source (points at `docs/adding-a-provider.md`).

### d. Provider scaffold: `research-db new-provider <name>`

New Typer command in `cli.py`. Given a dataset-source name, generates:

- `src/opendiscourse_research/providers/<name>.py` — module docstring,
  imports wired to the real shared plumbing (`ingestion.base.client`,
  `ingestion.base.json_response`, `config.settings`), and one `sync()`
  stub that raises `NotImplementedError(...)` with a message pointing at
  `docs/adding-a-provider.md`.
- `tests/test_<name>_provider.py` — stub test importing the module, with
  one test marked via `self.skipTest(...)` as a placeholder.
- A commented-out, ready-to-fill provider block appended to
  `inventory/sources.yaml`, matching the existing schema (`id`, `name`,
  `base_url`, `auth`, `datasets`).

Does **not** generate repository/ingestion/staging code — those layers
vary more per dataset (see `docs/framework.md`'s
plan → preview → approve → download → stage → load pipeline), and a stub
there would likely mislead more than help.

**Error handling:** the generator refuses with a clear, non-zero-exit error
if `<name>` already exists as a provider module or already has a
`sources.yaml` entry — it never silently overwrites.

### e. `docs/adding-a-provider.md` (checklist, not interface)

Written checklist of required *behaviors* (not a fixed function shape)
every provider must satisfy, each with a pointer to where an existing
provider demonstrates it:

- Record provenance via existing repository functions.
- Respect provider-specific pacing/rate limits where the provider requires
  it.
- Raise a clear `ValueError` on missing required config/API keys rather
  than failing opaquely.
- Never contact a live provider from `init-db`.

### f. Worked walkthrough

A section within `docs/adding-a-provider.md` (not a separate doc) tracing
FRED end-to-end: `providers/fred.py` → `repositories/catalog.py` cache
calls → its `inventory/sources.yaml` entry → `tests/test_*fred*` — one real
example read alongside the checklist.

## Testing

- `research-db new-provider <name>`: unit test that runs the generator
  against a temp directory/repo copy, asserts the three expected
  files/edits are created with correct placeholder content, and that the
  generated provider module imports cleanly (catches template drift
  against the real `ingestion.base`/`config` APIs it references).
- `compose.yaml` portability: verified manually via a clean-clone smoke
  test in a scratch directory (not practically automatable in CI without a
  fresh machine per run).
- No changes to existing provider/repository/ingestion code — existing
  test suite must be unaffected and must still pass.

## Success criteria

1. Clean clone → `cp .env.example .env` → `docker compose up` →
   (`DATABASE_URL` override) → `research-db init-db` → `research-db browse`
   works with no manual edits beyond the documented `DATABASE_URL`
   override.
2. `research-db new-provider demo` produces a working, importable stub plus
   a valid `sources.yaml` addition, and refuses cleanly on a name collision.
3. `CONTRIBUTING.md` and `docs/getting-started.md` exist and cross-link
   correctly with `README.md` and `AGENTS.md`.
4. Full existing test suite still passes:
   `uv run --extra ingest --extra spatial python -m unittest discover -s tests -v`.
