# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

OpenDiscourse is a provenance-first PostgreSQL/PostGIS research database for
U.S. geography, demographics, economics, markets, crime, elections, and
public-policy data (Census/ACS, FRED, Congress.gov/GovInfo, OpenStates,
TIGER, Treasury). Every ingestion run records provider, dataset, request
parameters, source URL, response checksum, and raw payload so typed facts
trace back to their source. See `README.md` for the adapter-by-adapter quick
start and `AGENTS.md` for the project creed (feedback UX, code/data
boundaries, git workflow, library conventions) — read it before writing
code; it is not duplicated here.

## Commands

```bash
# Setup
cp .env.example .env
python -m venv .venv && source .venv/bin/activate
pip install -e '.[analytics,spatial,ingest]'
research-db init-db        # creates schema; contacts no provider

# Core loop
research-db status          # catalog-ready datasets vs. registered-but-unimplemented
research-db sync            # refresh metadata adapters only, never bulk observations
research-db browse           # TUI catalog browser (Provider -> Dataset -> Year -> Product -> Resource)
research-db audit
research-db validate
```

Run everything through `uv` if available (`uv run research-db ...`,
`uv sync --extra ingest --extra spatial`) — this matches CI.

### Tests

CI (`.github/workflows/test.yml`) runs `unittest`, not `pytest`, against a
real `postgis/postgis:17-3.5` service container:

```bash
uv run --extra ingest --extra spatial python -m unittest discover -s tests -v

# Single file / class / test
uv run python -m unittest tests.test_govbackfill -v
uv run python -m unittest tests.test_legislation_persistence.TestLegislationPersistence.test_parse_billstatus_xml -v
```

Tests that touch a real database are skipped unless
`OPENDISCOURSE_TEST_DATABASE_URL` is set (see the workflow file for the
expected DSN shape); everything else runs against fakes/mocks with no DB.

### Lint/format

`ruff` is available (`ruff check src/`, `ruff format src/`) but is not wired
into CI and the tree is not currently clean under it — don't assume a
passing `ruff check` is a merge gate, but don't add new violations either.

## Architecture

### Layered data model (`docs/blueprint.md`)

```
provider -> fetch -> raw object -> parse -> typed tables -> research views
              |          |              |              |
             plan     artifact        run          document/embed
```

| Layer | Role | Stored in |
|---|---|---|
| raw | Immutable original evidence | object storage; URL/checksum/coverage in `ingest.artifact` |
| log | Reproducible operation history | `ingest.run`, `ingest.raw_payload`, `ingest.cursor` |
| core | Cross-source identities | geography, people, organizations, bills, documents |
| fact | Narrow analytical observations | measurements, votes, awards, crime, election results |
| mart | Purpose-built research views | bill timelines, member records, place-year panels |

Within ingestion, four further stages are kept intentionally separate
(`docs/framework.md`): `raw` (checksummed files) -> `ingest` (tracked run +
params + cursor) -> `stage` (replaceable provider-shaped rows — the only
place an automatic loader may create/evolve tables) -> `core`/`fact`
(reviewed tables with stable keys). `dlt` is optional staging machinery, not
the canonical database model.

### Module boundaries (`docs/conventions.md`)

- `src/opendiscourse_research/providers/*` — HTTP requests only (one file per
  provider: `census.py`, `congress.py`, `fred.py`).
- `src/opendiscourse_research/repositories/*` — PostgreSQL persistence only,
  bound parameters, no string-interpolated SQL.
- `src/opendiscourse_research/ingestion/*` — per-dataset bulk pipelines
  (plan -> preview -> approve -> download -> stage -> load), one module pair
  per dataset (`acs_bulk.py`/`acs_load.py`, `cbp_bulk.py`/`cbp_load.py`,
  `dhc_bulk.py`/`dhc_load.py`, `tiger_bulk.py`/`tiger_load.py`,
  `pep_bulk.py`/`pep_load.py`).
- `cli.py` — Typer entry point (`research-db`) coordinating the above; most
  subcommands are `hidden=True` and reached through `browse`/`status`/`sync`
  rather than being advertised directly. Subgroups: `ingest` (per-provider
  plan/preview/load steps), `bootstrap` (resumable bulk downloads), `catalog`
  (browser internals).
- Schema changes are ordered `sql/NNN_name.sql` migrations; reusable runtime
  SQL lives in `sql/query/<area>/`.

### Registry files (reviewed in Git, not runtime config)

- `inventory/sources.yaml` — what a source is (authoritative registry).
- `inventory/plans.yaml` — exactly what the system is allowed to ingest
  (source, handler, cadence, parameters); run via `research-db plan-run
  <id>` or all-due via `research-db plan-due`.
- `inventory/contracts/` — reviewed, provider-specific selections (e.g. the
  ACS housing scope), start disabled/pending approval.
- `inventory/progress.yaml` — operational work register (found, verified,
  loaded, on hold, selected next); see `docs/runbook.md`.

Adding a source (`docs/framework.md`): register in `sources.yaml` -> add a
focused `contracts/` selection -> add a metadata-only discovery action first
-> add a replaceable staging loader, then a reviewed canonical transform ->
register progress with scope/evidence/next action.

### Database runtime (`docs/runtime.md`)

Primary: bare-metal PostgreSQL 17 on port `5434`, peer-authenticated, DSN
`postgresql:///opendiscourse?port=5434`, `odspace` tablespace on the large
workspace partition. Two databases:

- `opendiscourse` — canonical catalog, raw lineage, curated entities, facts,
  documents, vectors.
- `openstates` — provider staging DB restored from the OpenStates dump;
  never alter its source schema. `opendiscourse` reaches it only through the
  read-only `openstates_source` foreign schema.

`compose.yaml` (port `5433`) is a development-only fallback — set
`DATABASE_URL` explicitly before using it so migrations never hit it by
accident.

### Capacity gate

Every bulk plan must produce a manifest of exact artifact URLs/sizes before
any download; `research-db storage-preview` probes publisher sizes against
free space on the raw-lake + tablespace filesystem (default budget: raw
download + one staging copy + 1.5x DB growth + 100 GiB free). Unknown sizes
or insufficient capacity exit non-zero — a fetcher must refuse to start
rather than guessing.

## Further reading

`docs/` holds the fuller design docs referenced above plus
`consolidation.md` and `model.md` (legislative Open Civic Data mapping),
`lake.md` (raw storage layout), `bulk-bootstrap-plan.md` and `runners.md`
(scheduled/bounded bulk runs), and `census-operations.md` /
`congressional-operations.md` / `openstates-integration.md` (per-provider
operational detail).
