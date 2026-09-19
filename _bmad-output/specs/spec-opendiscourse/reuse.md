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
| Voteview (UCLA) | Wrap through the `voteview` task in `unitedstates/congress`; joins on ICPSR |
| `pygris`, `datamade/census` | REFERENCE until licence, maintenance and fit are checked (ADR-0004) |
| `fredapi` | Optional extra `fred`; our FRED client stays |
| LDA.gov API (lobbying) | Candidate, gate `later`: official REST API; verify limits and licence before use |
| USAspending, SAM.gov, Federal Register, Regulations.gov, eCFR, CourtListener | Candidates, gate `later`: use the publisher's own bulk files or API; not scheduled |
| House Clerk and Senate eFD financial disclosures | Official sources are canonical; store disclosed ranges, never a midpoint. Blocked on a filer-identifier bridge |
| `congress-trading-pipeline`, PoliTracker, Quantgress, `us-congress-stock-transactions-retrieval`, `pyCFR` | REFERENCE only: small, unverified projects (ADR-0004) |
| Pandera | Evaluate when a loader needs frame validation before promotion |
| Parquet/DuckDB "normalized lake" | Derived, rebuildable side cache only; needs its own ADR and a benchmark (ADR-0004) |
| Data.gov | Discovery only; ingest from the publisher's endpoint |
