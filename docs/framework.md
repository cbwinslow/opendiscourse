# Ingestion framework

The project uses a small, version-controlled contract for every selection.
The contract answers: which provider data is allowed, at what grain, for which
period/geographies, and where it is intended to land. Short IDs such as
`acshome` are operator commands, not vague source names.

The layers are intentionally separate:

1. `raw` — downloaded files and provider responses, checksummed and retained.
2. `ingest` — a tracked run, parameters, status, raw payloads, and cursors.
3. `stage` — replaceable provider-shaped rows. This is the only place an
   automatic loader may create or evolve tables.
4. `core`/`fact` — reviewed research tables with stable keys and provenance.

`dlt` is adopted as an optional staging runner, not as the database model. Its
automatic schema evolution is useful for provider-shaped data but would be a
bad fit for the research model and its provenance requirements. Its pipeline
state belongs under `data-lake/opendiscourse/meta/dlt`; project run history in
`ingest.run` remains authoritative.

## Capacity gate

Every bulk plan must produce a manifest of exact artifact URLs and sizes before
download. `research-db storage-preview --url URL ...` probes each publisher for
its published byte size and compares the batch's conservative peak demand to
the filesystem containing the raw lake and PostgreSQL tablespace. The default
budget is raw download + one staging copy + 1.5x database growth + 100 GiB
left free. Unknown sizes and insufficient capacity exit non-zero, so a fetcher
must refuse to start. Source-specific contracts may use measured multipliers,
but never a smaller reserve without an explicit review.

For the first reference workflow, use the official Census metadata API rather
than guessing what a Python wrapper exposes. The `census` package remains a
useful request convenience wrapper, but it is not the inventory of record.

## Safe first operation

```bash
research-db catalog-check
research-db contract-list
research-db ingest census-plan --contract acshome
```

The last command only retrieves the declared ACS group definitions, records
their provenance, and prints the selected variable count and estimated request
count. It does not retrieve county observations. Review that output before
running an ACS load.

To discover the full set of ACS data products for one release without pulling
any ACS data tables, run:

```bash
research-db ingest census-discover --year 2024
```

It downloads only the Census table-list workbook, records it as an artifact,
and writes `meta/acs/2024/tables.json`. The manifest's `housing_candidates`
are a transparent starting rule, not an automatic inclusion decision.

`inventory/contracts/acshousing.yaml` is the editable bulk selection. Its
`include_*`, `exclude_ids`, and `add_ids` rules are reviewed with:

```bash
research-db ingest census-review --contract acshousing
```

The contract starts disabled and pending approval. Editing it cannot start a
download; the later bulk planner must still create an exact artifact manifest
and pass the capacity gate.

Use the local explorer to make selections by meaning rather than memorizing
table IDs:

```bash
research-db ingest census-search --text 'median gross rent' --product detailed
research-db ingest census-table --id B25064
```

Search never contacts Census. The table command retrieves only that one
table's official estimate/MOE metadata and records the response for
provenance. Add `--all` to include Census annotation fields.

## Catalog browser

The provider-neutral browser uses PostgreSQL catalog resources and persistent
baskets, rather than a provider-specific list of checkboxes. After discovery:

```bash
research-db catalog-sync acs --year 2024
research-db browse
```

The browser starts at Provider → Dataset → Year → Product → Resource. Type to
filter resources; press Enter to descend or inspect fields; press Backspace to
go back; press Space to add/remove the highlighted resource; press `c` to
review your selection; press `Ctrl+Q` to quit.
Selections are drafts only. They do not create a fetch plan or download data.
The same catalog and basket tables will serve FRED, FBI, GovInfo, and other
adapters when they are implemented.

`research-db sync` refreshes every implemented metadata adapter and never
downloads bulk observations. `research-db status` distinguishes catalog-ready
datasets from registered providers that still need an adapter.

`research-db sync --source census` indexes every offering currently published
in the official Census Data API catalog. It stores the source response and
offering metadata only; this is the safe starting point for discovering ACS,
housing, Decennial, PEP, business, and other Census APIs. Open it with
`research-db browse --dataset census.api_catalog`. Browsing a Census offering
or adding it to a basket does not authorize observation or bulk-file ingestion.

Every provider discovery will also create a `catalog.snapshot` record linked to
the original metadata artifact and its checksum. Resources may be refreshed for
search, but snapshots preserve exactly what the provider advertised at a given
time; no discovery job may silently erase that history.

The browser currently auto-discovers the verified modern ACS table-based
releases (2022–2024). Earlier ACS releases remain a separate legacy
sequence-format adapter task; they are not presented as selectable until their
metadata path is implemented and tested.

Use `research-db catalog-options` to see discovered years and products, or
filter the browser with `--year 2024 --product 'Detailed Table'`. `a` requires
a second press before selecting all currently filtered rows; `g` likewise
requires a second press before writing a disabled draft under `meta/drafts`.

## Adding a source

1. Add the provider/dataset to `inventory/sources.yaml`.
2. Add a focused selection to `inventory/contracts/`.
3. Add a metadata-only discovery action first.
4. Add a replaceable staging loader; then add a reviewed canonical transform.
5. Register it in `inventory/progress.yaml` with scope, evidence, and next
   action. Schedule only after a successful bounded run.
