# Reuse catalog

Search for a maintained project before writing acquisition, parse, orchestrate,
search, or export code. Wrap behind provenance.

| Upstream | Decision |
|---|---|
| `unitedstates/congress` | Wrap as vote/bill producer (`vendor/unitedstates-congress`) |
| `unitedstates/congress-legislators` | Identity crosswalk (`vendor/congress-legislators`). Same repo is the source for current committee/subcommittee membership YAML (`committee-membership-current.yaml`); wrap that next, do not scrape Clerk HTML. |
| Voteview / DW-NOMINATE (UCLA) | Wrap the three current official exports: `HSall_members.csv`, `HSall_rollcalls.json`, and `HSall_parties.csv`; join people on ICPSR. Do not replace Clerk/Senate.gov votes, download `HSall_votes.csv`, or run the obsolete `unitedstates/congress` Voteview task. |
| BICAM (MIT, *Scientific Data* 2025) | Academic bulk Congress.gov/GovInfo ingest (`bicam.net`, `bicam-data/bicam`). Use as schema/methods literature and a completeness check, not as our system of record. |
| CBO cost estimates | Retained GovInfo BILLSTATUS XML carries `cboCostEstimates` (`pubDate`, `title`, `url`, `description`), promoted with bill/artifact/member/ordinal evidence. A scripted fetch of cbo.gov/cost-estimates/xml returned HTTP 403 (2026-09-22). |
| OpenStates / Plural dumps | Isolated DB + FDW `openstates_source`; OCD language in `core`, not Django dump schema |
| `pyopenstates` | Evaluate for API v3 incremental after dump promote |
| U.S. Census Bureau Data API MCP | Official agent-facing Census metadata/query tool. Use for Claude/Codex exploration and source verification; production acquisition still follows Connector + retained official bytes. Do not make the MCP's local database a warehouse authority. |
| `openstates-core` | Model reference; do not clone internal schema |
| U.S. BEA `beaapi` | Preferred optional adapter to evaluate before a custom BEA client; official BEA GitHub project, keep its cache under DATA_ROOT or disable it |
| `usaspending-orm` | Strong adapter candidate before custom USAspending pagination/model code; smoke-test it behind the provider boundary and retain OpenDiscourse evidence/keys |
| FEC bulk files (cm, cn, ccl, indiv, pas2, oth, oppexp) | Wrap official cycle zips; typed grains in `resolved-questions.md`. Do not promote `stage.fec_row` jsonb. Evaluate `fec-gov-postgres` as a loader reference, not a schema to copy |
| MIT Election Lab / OpenElections | Evaluate when Epic 7 opens |
| Census relationship files, block equivalency files | Wrap for `geography_crosswalk` / `division_boundary` (Epic 10) |
| `jamaps/lehd`, Urban Institute `lodes-data-downloads` | Reference/evaluate only for LODES file conventions and aggregation ideas. Do not pre-approve as production dependencies; verify maintenance and official Version-8 coverage when Story 10.10 starts. |
| LEHD LODES, IRS SOI, CVAP, FCC BDC, GAO CPF/CDS, HMDA, CDC PLACES, NCES CCD/CRDC | Candidates per `inventory/dataset-roadmap.yaml`; verify at the publisher, use official files |
| Redistricting Data Hub | Comparison/validation source for election and boundary data, not a system of record |
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
| `pygris`, `datamade/census` | EVALUATE in Epic 10 before custom TIGER/Census API convenience code. `pygris` directly supports CD/SLD/PUMA/tract/block/BG TIGER access through 2024; it may assist discovery/parsing but cannot hide the official ZIP URL/bytes. `datamade/census` is an optional API client, not a reason to replace retained ACS bulk files. |
| `fredapi` | Optional extra `fred`; our FRED client stays |
| LDA.gov API (lobbying) | Candidate, gate `later`: official REST API; verify limits and licence before use |
| USAspending, SAM.gov, Federal Register, Regulations.gov, eCFR, CourtListener | Candidates, gate `later`: use the publisher's own bulk files or API; not scheduled |
| House Clerk and Senate eFD financial disclosures | Official sources are canonical; store disclosed ranges, never a midpoint. Blocked on a filer-identifier bridge |
| `congress-trading-pipeline`, PoliTracker, Quantgress, `us-congress-stock-transactions-retrieval`, `pyCFR` | EVALUATE when the source's story starts; keep what is maintained and correct (ADR-0004) |
| Pandera | Adopt when the first loader needs frame validation before promotion |
| Parquet/DuckDB "normalized lake" | Benchmark story planned (size); if it wins, a derived rebuildable layer, never the authority (ADR-0004) |
| Data.gov | Discovery only; ingest from the publisher's endpoint |
