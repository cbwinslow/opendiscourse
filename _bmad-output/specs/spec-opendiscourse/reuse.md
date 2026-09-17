# Reuse catalog

Search for a maintained project before writing acquisition, parse, orchestrate,
search, or export code. Wrap behind provenance.

| Upstream | Decision |
|---|---|
| `unitedstates/congress` | Wrap as vote/bill producer (`vendor/unitedstates-congress`) |
| `unitedstates/congress-legislators` | Identity crosswalk (`vendor/congress-legislators`) |
| OpenStates / Plural dumps | Isolated DB + FDW `openstates_source`; OCD language in `core`, not Django dump schema |
| `pyopenstates` | Evaluate for API v3 incremental after dump promote |
| `openstates-core` | Model reference; do not clone internal schema |
| U.S. BEA `beaapi` | Evaluate before a custom BEA client |
| `usaspending-orm` | Evaluate before a custom USAspending client |
| FEC bulk files (cm, cn, ccl, indiv, pas2, oth, oppexp) | Wrap official cycle zips; typed grains in `resolved-questions.md`. Do not promote `stage.fec_row` jsonb. Evaluate `fec-gov-postgres` as a loader reference, not a schema to copy |
| MIT Election Lab / OpenElections | Evaluate when Epic 7 opens |
| Census relationship files | Wrap for `geography_relationship` when Epic 5 needs vintage comparability |
| IPUMS NHGIS crosswalks | Optional weights; evaluate before hand-rolling interpolation |
| dlt | REST → `stage` only |
| dbt | Marts |
| PostgREST | Read-only `api.*` |
| DuckDB | Sidecar + Parquet |
| pgvector | Documents only; keep `real[]` until kNN story + ADR; extension already on 5434 |
| Prefect | Optional `ops` extra |
| Meltano/Singer | Not the foundation |
| `censusdis` | Optional convenience; not required (license) |
| Serena, Context7, GitHub MCP | Agent retrieval; not authority |
