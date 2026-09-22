# Reuse catalog

Search for a maintained project before writing acquisition, parse, orchestrate,
search, or export code. Wrap behind provenance.

| Upstream | Decision |
|---|---|
| `unitedstates/congress` | Wrap as vote/bill producer (`vendor/unitedstates-congress`) |
| `unitedstates/congress-legislators` | Identity crosswalk (`vendor/congress-legislators`). Same repo is the source for current committee/subcommittee membership YAML (`committee-membership-current.yaml`); wrap that next, do not scrape Clerk HTML. |
| Voteview / DW-NOMINATE (UCLA) | Official CSVs at voteview.com/data; join on ICPSR already in `core.person_identifier`. Wrap member ideology + roll-call index; do not replace Clerk/Senate.gov votes. |
| BICAM (MIT, *Scientific Data* 2025) | Academic bulk Congress.gov/GovInfo ingest (`bicam.net`, `bicam-data/bicam`). Use as schema/methods literature and a completeness check, not as our system of record. |
| CBO cost estimates | BILLSTATUS JSON already holds `cboCostEstimates` (title, date, URL). CBO also publishes an XML index (`cbo.gov/cost-estimates/xml`). Type the JSON first; fetch PDFs later if analysis needs the full write-up. |
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
| `pygris`, `datamade/census` | EVALUATE when the source's story starts; adopt if licence and maintenance are fine (ADR-0004) |
| `fredapi` | Optional extra `fred`; our FRED client stays |
| LDA.gov API (lobbying) | Candidate, gate `later`: official REST API; verify limits and licence before use |
| USAspending, SAM.gov, Federal Register, Regulations.gov, eCFR, CourtListener | Candidates, gate `later`: use the publisher's own bulk files or API; not scheduled |
| House Clerk and Senate eFD financial disclosures | Official sources are canonical; store disclosed ranges, never a midpoint. Blocked on a filer-identifier bridge |
| `congress-trading-pipeline`, PoliTracker, Quantgress, `us-congress-stock-transactions-retrieval`, `pyCFR` | EVALUATE when the source's story starts; keep what is maintained and correct (ADR-0004) |
| Pandera | Adopt when the first loader needs frame validation before promotion |
| Parquet/DuckDB "normalized lake" | Benchmark story planned (size); if it wins, a derived rebuildable layer, never the authority (ADR-0004) |
| Data.gov | Discovery only; ingest from the publisher's endpoint |
