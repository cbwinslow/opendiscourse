# Reuse catalog

Search for a maintained project before writing acquisition, parse, orchestrate,
search, or export code. Wrap behind provenance.

| Upstream | Decision |
|---|---|
| `unitedstates/congress` | Wrap as vote/bill producer (`vendor/unitedstates-congress`) |
| `unitedstates/congress-legislators` | Identity crosswalk (`vendor/congress-legislators`) |
| OpenStates / Plural dumps | Isolated DB + FDW `openstates_source` |
| dlt | REST → `stage` only |
| dbt | Marts |
| PostgREST | Read-only `api.*` |
| DuckDB | Sidecar + Parquet |
| pgvector | Documents only; extension already on 5434 |
| Prefect | Optional `ops` extra |
| Meltano/Singer | Not the foundation |
| `censusdis` | Optional convenience; not required (license) |
| Serena, Context7, GitHub MCP | Agent retrieval; not authority |
