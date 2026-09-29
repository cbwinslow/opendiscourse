# Dataset inventory and priority review

Last reviewed: 2026-09-29. This is the plain-language view of the approved
source catalog. `inventory/sources.yaml` defines what the project may build;
`inventory/progress.yaml`, `docs/PROJECT-STATE.md`, and the current session
handoff define the operational state. A source listed here is not necessarily
loaded or approved for a new transfer.

## Work order

1. **Finish the separate ACS Detailed Tables delta.** Its already-approved
   2021–2024 files still need staging and publication, one year at a time with
   a health check between years.
2. **Let the active ACS PUMS/AHS archive service finish, then validate it.**
   Do not start another worker or bulk load. Confirm final staging and
   published counts, release coverage, and source-row counts only after the
   service exits successfully.
3. **Close congressional completeness only when Congress.gov recovers.**
   Retry the two named 107th-Congress detail pages and three named cosponsor
   pages, not a full bill download.
4. **Maintain population and geography coverage.** Add new official vintages
   when published; broader geography layers need their own approved scope.
5. **Only then consider unbuilt or gated sources.** In particular, FEC and
   election-person links remain blocked until their identifier contracts are
   reviewed. Federal person joins use BioGuide, never names.

## Dataset inventory

| Dataset — owner | What it contributes | Time/product boundary | Actual state | Next safe action / dependency |
|---|---|---|---|---|
| `census.api_catalog` — Census | Index of Census API offerings | Metadata only; each vintage is separate | Catalogued; no tracker entry | Use only to discover a separately approved offering. |
| `census.acs_1` — Census | Annual population, social, economic, and housing estimates | Standard 1-year releases 2005–2024 except 2020; never substitute another product | Catalogued; no direct load tracked | Define an approved annual scope and Connector before acquisition. |
| `census.acs_5` — Census | Small-area estimates and margins of error through the API | Five-year estimates are distinct from 1-year estimates; do not compare overlapping windows as independent observations | Catalogued; no direct API load tracked | Define an approved API scope and Connector before acquisition. |
| `census.acs_5_bulk` — Census | Complete Detailed Tables, estimates, margins of error, and published geographies | Five-year release bundles stay distinct from ACS 1-year releases | Loaded in the prior 2021–2024 scope; the broader Detailed Tables delta is downloaded but not fully staged/published | Finish the approved 2021–2024 delta, one plan at a time with `census-health`. |
| `census.acs_housing_archive` — Census | ACS PUMS person/housing microdata and AHS housing microdata | PUMS 1-year: 2005–2019, 2021–2024; PUMS 5-year: 2005–2009 through 2020–2024; AHS relational public-use CSVs: 2001–2023 | Raw archive retained; staging is running in one managed service | Leave the service alone. After success, validate stage/published counts and release coverage; documentation files are evidence, not data rows. |
| `census.decennial` — Census | Decennial baseline counts | 2020 DHC, H1/P1, state and county only | Loaded | Additional tables or geographies need explicit approval. |
| `census.population_estimates` — Census | Annual population estimates | 2010–2020 and 2020–2025 vintages; vintages stay separate | Loaded | Add a new official vintage series when Census publishes it. |
| `census.tiger` — Census | Boundary shapes for place-based analysis | State, county, CBSA, and ZCTA layers, 2016–2025; 2022 has no CBSA release | Loaded | Maintain new vintages; tract, block-group, and block layers are separate work. |
| `census.business_patterns` — Census | Establishments/employment and nonemployer statistics by industry/place | County Business Patterns is loaded for 2009–2023; Nonemployer Statistics is a separate approved product | CBP loaded; Nonemployer Statistics unbuilt | Add the next CBP release when published; scope and build Nonemployer Statistics separately. |
| `census.government_finance` — Census | Government finance by unit and fiscal year | Product-specific annual/fiscal releases | Catalogued; unbuilt | Require a source-specific scope and Connector. |
| `fred.series` — Federal Reserve Bank of St. Louis | Revision-aware macroeconomic series | 38 loaded series, 1919–2026; observations retain real-time vintages | Loaded | Write and approve the intended-series manifest before expanding it. |
| `bea.regional` — Bureau of Economic Analysis | Regional GDP, income, and price parities | Quarterly or annual releases, by table and geography | Catalogued; unbuilt | Define the target tables/geographies and build a Connector. |
| `bls.laus` / `bls.cpi` — Bureau of Labor Statistics | Local unemployment and consumer prices | Current tracked data is only a 2007–2016 national pilot, not local coverage | Verify/pilot only | Approve target LAUS geographies, CPI series, and history before a real load. |
| `bls.qcew` — Bureau of Labor Statistics | Employment and wages by area, industry, ownership, and quarter | Quarterly | Catalogued; no rows loaded | Define approved coverage and build a Connector. |
| `treasury.yield_curve` — U.S. Treasury | Daily nominal, real, and bill yield curves | Business-day tenors, with methodology | Loaded through the recorded 2026-08-05 check | Repair/confirm freshness as a bounded maintenance task. |
| `treasury.fiscal_data` — U.S. Treasury | Federal fiscal/debt/spending series | Dataset-specific daily or monthly releases | Catalogued; unbuilt | Decide whether it is in scope before registering a load. |
| `usaspending.awards` — USAspending | Federal award and assistance transactions | Daily transaction data | Catalogued; unbuilt | Define the research scope and Connector. |
| `fbi.crime_agency` — FBI Crime Data Explorer | Agency-level reported offense data and reporting coverage | Annual data with incremental updates | Catalogued; unbuilt | Build only after source scope and reporting-coverage policy are approved. |
| `congress.legislators` — congress-legislators | Federal people, terms, offices, identifiers, and leadership | Since 1789; identifiers include BioGuide and other published IDs | Loaded | Refresh from upstream; verify related records after any reviewed person merge. |
| `congress.legislation` — Congress.gov | Broad catalog of federal members, bills, actions, amendments, committees, and House votes | Entity/version or official roll-call position | Catalogued; no single broad all-entity load is tracked | Build bounded source contracts rather than treating the catalog entry as one completed load. |
| `congress.congress_gov_bills` — Congress.gov | Early federal bills, actions, sponsorship, committees, subjects, summaries, and text-version links | Current bounded backfill is Congresses 106–107, before GovInfo BILLSTATUS coverage | Ready with named upstream gaps: 106 matches; 107 has list-backed partial H.R. 2842/2843 rows because detail pages return HTTP 500; cosponsors also fail for 106 S. 1378, 106 S.Res. 218, and 107 H.R. 5346 | Retry only the five named endpoints after the publisher recovers; never rerun the full pass. |
| `congress.govinfo_billstatus` — GovInfo | Bill status and source records | Congresses 108–119 | Loaded through the official Connector | Refresh through the Connector and publisher coverage checks. |
| `congress.govinfo_bills` — GovInfo | Bill-text XML versions | Congresses 113–119; no BILLS bulk for 108–112 | Loaded; six 113th XML files are unreadable upstream bytes | Preserve the named exception; do not fabricate text or use legacy caches. |
| `congress.house_votes` / `congress.senate_votes` — House Clerk and Senate | Official roll calls and member positions | Congresses 108–119 | Loaded | Refresh through their official indexes and coverage checks. |
| `congress.committee_membership` — congress-legislators | Current committees, subcommittees, and assignments | Current assignments; historical bodies may have no membership | Loaded | Refresh from pinned upstream files; use BioGuide joins only. |
| `congress.voteview` — UCLA Voteview | Ideology measurements and roll-call index | Every Congress in the source files; does not replace official votes | Loaded with named unmatched/conflicting identifiers | Refresh through the Connector; retain identifier exceptions. |
| `congress.cbo_cost_estimates` — GovInfo BILLSTATUS | Typed CBO estimate fields already present in bill-status evidence | Bill × estimate | Loaded | A separate Connector is required before acquiring CBO PDFs/XML. |
| `govinfo.bulk` / legacy Congress caches — GovInfo and prior local caches | Potential broader legislative source material | Varies by package and Congress | Official BILLSTATUS/BILLS work is loaded; legacy caches remain verification-only, not inputs | Use the official Connector and publisher manifests; do not parse legacy caches as a shortcut. |
| `openstates.legislation` — OpenStates | State bills, people, votes, committees, and events | Coverage varies by state/session | Catalogued; unbuilt | A future Connector may read the provider; do not make it the researcher contract. |
| `openstates.dump` — OpenStates | Provider snapshot for read-only reference | Monthly snapshot | Loaded in a separate database and exposed through a read-only foreign-data link | Keep separate; promote reviewed facts into project-owned tables rather than copying dump tables. |
| `fec.campaign_finance` — Federal Election Commission | Candidates, committees, filings, receipts, and spending | Cycles from 2000; current stage data is unverified legacy material | Blocked/verify; no canonical facts | First approve identity and candidate/committee-linkage contracts. Never join people by name. |
| `disclosures.financial` / `elections.results` — official disclosure/election publishers | Financial disclosures, transactions, election results, and crosswalks | Filing and election cycles | Catalogued; person joins blocked where applicable | Define source contracts; keep person-linked promotion gated by identifiers. |
| `markets.prices` / `markets.indices` — future licensed/official providers | Prices, corporate actions, fundamentals, and index composition | Provider-dependent | Intentionally deferred; outside v1 loading | Do not load market data without a later approved scope and provider decision. |

## Reading the states

- **Loaded** means the tracked source has been brought into the warehouse or
  its approved reference database, with its stated limits. It does not mean
  every product the owner could publish is present.
- **Raw retained/staging** means official files are safely stored and the
  current job is preparing warehouse rows; it is not yet a published dataset.
- **Catalogued** means the source is approved for future design, not that an
  acquisition is authorized.
- **Ready** means a bounded Connector has completed its planned work except
  for named, retained publisher failures; it is neither a general loaded state
  nor permission to repeat a full acquisition.
- **Blocked/verify** means a missing contract, identity safeguard, or source
  check prevents promotion. It is deliberately not a queue to bypass.

## Operational references

- Current run and safety rules: `docs/SESSION-HANDOFF-2026-09-29-ACS-STAGING-AND-INVENTORY.md`
- Current exceptions and verified counts: `docs/PROJECT-STATE.md`
- Approved catalog and tracked state: `inventory/sources.yaml` and `inventory/progress.yaml`
- ACS product/coverage rules: `_bmad-output/specs/spec-longitudinal-source-coverage/`
- Legislative definition of done: `_bmad-output/specs/spec-opendiscourse/legislative-north-star.md`
