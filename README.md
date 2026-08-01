# OpenDiscourse Research Database

Provenance-first PostgreSQL/PostGIS foundation for U.S. geography, demographics,
economics, markets, crime, elections, and public-policy research.

## Quick start

```bash
cp .env.example .env
python -m venv .venv && source .venv/bin/activate
pip install -e '.[analytics,spatial,ingest]'
research-db init-db
research-db catalog-check
research-db plan-list
research-db progress-list
```

No provider is contacted by `init-db`. Each ingestion run records the provider,
dataset, request parameters, source URL, response checksum, and raw payload so
typed facts can always be traced back to their source.

Set `OD_LAKE_ROOT` and `DATA_ROOT` in `.env` before starting Docker. The
provided defaults use the large workspace partition for both raw artifacts and
Postgres; see `docs/lake.md` before admitting existing data-lake files.

The primary runtime is bare-metal PostgreSQL 17 on port 5434, using local peer
authentication and the `odspace` tablespace on the large workspace partition.
Docker Compose is retained only as an isolated development fallback; use it
only after overriding `DATABASE_URL` to its port-5433 database.

## Initial adapters

```bash
# ACS variables for every county in one state (example: Maryland, 2023 ACS 5-year)
# Add CENSUS_API_KEY to .env first.
research-db ingest census-acs --year 2023 --state 24 --variables NAME,B01003_001E

# Safe Census discovery: records table metadata and prints the field/request
# plan, but does not download county observations.
research-db ingest census-plan --contract acshome

# Catalog the official ACS table list and produce a local housing-candidate
# manifest. This fetches metadata only, not ACS tables or observations.
research-db ingest census-discover --year 2024

# Load the discovered catalog into PostgreSQL and open the keyboard browser.
# Type to search; Enter shows fields; Space toggles the current table in the
# named draft basket; Ctrl+Q exits. This does not download data.
research-db catalog-sync acs --year 2024
research-db browse --dataset census.acs_5 --basket housing

# Check a proposed bulk batch before any download. A non-zero exit means the
# size is unknown or the required reserve would be breached.
research-db storage-preview --url 'https://example.gov/release.zip'

# A FRED series; add FRED_API_KEY to .env first
research-db ingest fred --series-id UNRATE

# A single Congress.gov bill; add CONGRESS_API_KEY to .env first
research-db ingest congress-bill --congress 119 --bill-type hr --bill-number 1

# Official OpenStates schema archive; add --data to download the ~10 GB data archive.
research-db bootstrap openstates-dump --year 2026 --month 7

# Treasury's full published nominal curve for a calendar year; no key required.
research-db bootstrap treasury-curve --year 2025

# Curated priority-one FRED macro, labor, rates, yield, index, commodity, and FX series.
# Requires FRED_API_KEY in .env.
research-db bootstrap fred-core

# Curated ACS 5-year housing groups for Maryland counties; requires CENSUS_API_KEY.
research-db bootstrap acs-housing --year 2023 --states 24

# Execute a named, version-controlled ingestion contract.
research-db plan-run fredcore
research-db plan-due --dry-run

# Pull a controlled batch of bills from one Congress; advance --offset for a backfill.
research-db bootstrap congress-bills --congress 119 --max-records 250

# Register (but do not copy, parse, or trust) one legacy artifact.
research-db bootstrap register --dataset congress.legislation \
  --path /mnt/storage/data-lake/government/epstein/raw-files/congress/bills/bills_118_chunk_0000.json \
  --key cong118-0000 --note 'legacy cache; pending Congress.gov verification'
```

`inventory/sources.yaml` is the authoritative source registry;
`inventory/plans.yaml` holds runnable refresh jobs; and
`inventory/contracts/` holds reviewed, provider-specific selections such as
the Census housing scope. See `docs/framework.md` for the staging and
promotion rules. `dlt` is optional staging machinery rather than the canonical
database model.
The plan parameters are a reviewable allow-list: they decide which data is
worth loading, rather than asking an adapter to ingest an entire provider.
Add a dataset before creating an adapter and a plan only after choosing its
coverage and storage budget. The next adapter should use the same
`IngestionRun` / raw-payload / typed-fact pattern as the initial adapters.
Bulk acquisition details and profile guidance are in `docs/bulk-bootstrap-plan.md`.
Run `research-db plan-due` from a cron job or systemd timer to refresh every
due plan. It records a per-plan refresh cursor only after the provider run
finishes successfully.

`inventory/progress.yaml` is the operational work register: it records what
has been found, verified, loaded, put on hold, and selected next. See
`docs/runbook.md` for the mandatory intake and validation procedure.

Legislative data follows the Open Civic Data/OpenStates interoperability model;
the canonical mapping and safe migration plan for the existing `government`
workspace are in `docs/model.md` and `docs/consolidation.md`.

## Design rules

- Keep raw source payloads immutable and facts reproducible.
- Store boundary and dataset vintages; never overwrite historical geography.
- Preserve source identifiers alongside internal IDs.
- Use bulk data for historical backfills and APIs for incremental refreshes.
- Treat `yfinance` as a convenience feed, not a canonical production source.
- Put bill text, statutes, and reports in `core.document` and split them into
  `core.document_chunk`; embeddings are model-specific records, never the
  only retained representation of a source document.
