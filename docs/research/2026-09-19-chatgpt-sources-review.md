> **Research input, not authority.** A ChatGPT review of data sources and tools, supplied by the operator on
> 2026-09-19. Its claims about external sources are unverified by us, and some claims about this project are wrong
> (for example, Prefect is an optional extra that no code uses). Under the hierarchy of truth in `AGENTS.md`
> it ranks below code, specs and ADRs. The evaluation and what we adopted, deferred and rejected is in
> `docs/adr/0004-source-catalog-and-tool-policy.md`.

Yes. I inspected the current `cbwinslow/opendiscourse` repository and compared what you already have with the current official APIs, bulk datasets, Python libraries, and community projects available in 2026.

The main conclusion is: **I would not start over and I would not replace the architecture you have now.** Your current “immutable raw source → staging → typed PostgreSQL/PostGIS facts → research marts” model is exactly the right shape for this problem. The biggest opportunity now is to aggressively reuse upstream acquisition projects and broaden the source catalog rather than writing more bespoke downloaders.

A useful way to think about OpenDiscourse is that we want to reconstruct this chain:

**politician → membership → bill → vote → enacted law → regulation/implementation → government spending → affected geography/population/industry → measurable outcomes**

…and simultaneously capture **campaign finance, lobbying, financial disclosures, elections, demographics, economics, crime, health, housing, education, environment, and other confounders** around that chain.

---

# 1. Federal legislation: this should be the legislative backbone

You already made a very good choice here.

| Source/tool                             | Contains                                                                                                                                                                              | How I would use it                             |
| --------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------- |
| **Congress.gov API**                    | Bills, amendments, actions, sponsors, cosponsors, committees, committee reports, hearings, nominations, members, summaries, text metadata, House votes, Congressional Record metadata | **Canonical API source**                       |
| **GovInfo Bulk Data/API**               | BILLSTATUS, actual bill text, statutes, Congressional Record, CFR/eCFR, Federal Register and many official documents                                                                  | **Canonical bulk/document source**             |
| **`unitedstates/congress`**             | Mature collection tooling over congressional/GovInfo/House/Senate sources; roll calls in particular                                                                                   | **Reuse rather than rebuilding scrapers**      |
| **`unitedstates/congress-legislators`** | Historical/current legislators, IDs, terms, committees and memberships                                                                                                                | **Canonical-ish identity bootstrap/crosswalk** |
| **Senate XML feeds**                    | Senate roll calls, memberships, schedules, nominations, etc.                                                                                                                          | Official supplement                            |
| **House vote endpoints / House Clerk**  | House roll calls and member votes                                                                                                                                                     | Official supplement                            |

Congress.gov's API is considerably more complete than it used to be. It exposes bills and their actions, amendments, committees, cosponsors, related bills, subjects, summaries and texts; member sponsorship/cosponsorship; hearings and reports; nominations; and now House roll-call information as well. ([Congress.gov API][1])

GovInfo complements that perfectly because it is much better for **bulk historical acquisition and source documents**. BILLSTATUS goes back to the 108th Congress, and GovInfo also exposes bill text, Statutes at Large, CFR/eCFR, Federal Register and other collections. ([GovInfo][2])

The Senate still publishes useful official XML sources independently, including roll calls and membership information. ([U.S. Senate][3])

And `unitedstates/congress` remains extremely useful because it already solves some of the ugly acquisition problems around House/Senate roll calls and GovInfo. ([GitHub][4])

### Recommendation for OpenDiscourse

**Keep exactly the approach your current BMAD plan has started moving toward:**

```text
Congress.gov API
       +
GovInfo bulk/BILLSTATUS/documents
       +
unitedstates/congress
       +
congress-legislators
       +
Senate/House official feeds
       ↓
OpenDiscourse Connector interface
       ↓
raw artifacts
       ↓
core.bill
core.bill_action
core.amendment
core.person
core.membership
core.committee
core.sponsorship
fact.roll_call
fact.vote
core.document
```

I would **not write another Congress scraper** unless there is truly something none of those projects expose.

---

# 2. Congress person/identity data: use `congress-legislators`

The `unitedstates/congress-legislators` repository is especially important because identity resolution is going to become one of OpenDiscourse's hardest problems.

It contains legislators going back to 1789, terms, committees and numerous external identifiers. ([GitHub][5])

You should retain crosswalks such as:

```text
OpenDiscourse person_id
    ├── bioguide_id
    ├── congress.gov ID
    ├── House/Senate identifiers
    ├── FEC candidate IDs
    ├── OpenStates/OCD identifiers
    ├── Wikidata ID
    └── other source IDs
```

**Bioguide should remain a particularly important federal legislative identifier. Never reconcile politicians by name alone.**

That decision in your current blueprint is correct.

---

# 3. State legislation: OpenStates / Plural is still the right cornerstone

For state government, I would absolutely continue using **OpenStates/Plural Policy**.

It provides:

* bills
* bill versions/text
* actions
* sponsors
* legislators
* legislative memberships
* committees
* votes
* sessions
* jurisdictions
* geographic boundaries
* bulk CSV/JSON data
* PostgreSQL dumps

Their bulk archives continue to be updated and can be only a day or two behind the live system. ([Plural Policy][6])

The underlying Open Civic Data approach is particularly valuable because it gives OpenDiscourse a sensible interoperability model for people, organizations, jurisdictions, divisions, bills and votes. ([GitHub][7])

### One important correction

**OpenStates is not an exhaustive source for city/county/local government.**

Its current legislative coverage focuses on the 50 states, DC, Puerto Rico and Congress. ([Plural Policy][8])

So I would define:

```text
Federal
    Congress.gov/GovInfo

State
    OpenStates/Plural

Municipal/county
    Open Civic Data IDs
    + local government connectors
    + community municipal scrapers where available
```

Open Civic Data has had community municipal scraper projects, but I would treat those as **seed/reference implementations rather than a guaranteed national source**. ([GitHub][9])

There really isn't one free, authoritative, exhaustive national API for every mayor, county commissioner, city council member and local vote.

That is an area where OpenDiscourse itself could eventually add significant value.

---

# 4. Campaign finance: FEC should be canonical

Your existing FEC ingestion work is worth preserving.

Use two methods together:

| Method             | Purpose                                          |
| ------------------ | ------------------------------------------------ |
| **FEC bulk files** | Historical backfill, huge volumes                |
| **OpenFEC API**    | Incremental updates, discovery, targeted queries |

The official OpenFEC API and bulk downloads expose candidates, committees, reports, receipts, expenditures, individual contributions and related campaign-finance information, with bulk data refreshed regularly. ([OpenFEC API][10])

Your project already has roughly 100M staging rows, so I **wouldn't replace that acquisition effort**.

The hard problem now is identity.

For example:

```text
person
  ↓
candidate
  ↓
FEC candidate_id
  ↓
authorized committees
  ↓
committee transactions
  ↓
donor/payee entities
```

The next work here should be **entity resolution and typed promotion**, not downloading yet another copy of FEC.

OpenSecrets can still be useful as an **enrichment/validation/reference source**, but I would keep official FEC records underneath it rather than making OpenSecrets the authoritative layer.

---

# 5. Lobbying: add LDA.gov

This is one of the most important sources that I think OpenDiscourse should add.

The official **Lobbying Disclosure Act API** exposes:

* registrants
* lobbying clients
* lobbyists
* quarterly LD-1/LD-2 filings
* lobbying income/expenses
* lobbying issues
* government entities contacted
* LD-203 contribution reports

The Senate's LDA system exposes an official REST API and documented rate limits. ([LDA][11])

That gives you a powerful relationship:

```text
organization
   ↓
lobbying client
   ↓
lobbying issue
   ↓
bill / policy area
   ↓
legislator / agency
   ↓
law / regulation
```

I would put **LDA.gov near the front of your v1.1 source roadmap**.

---

# 6. Congressional stock trades and financial disclosures

This is another high-value addition.

### Official sources

Use:

**House Clerk Financial Disclosure reports**

The House makes disclosure filings available by year, including current 2026 reports. ([House Disclosures][12])

**Senate Electronic Financial Disclosure system**

Use the official Senate EFD data as the underlying evidence.

The annoying part is parsing it. House and Senate formats differ, old documents can be scans, and transaction values frequently appear as ranges rather than exact amounts.

This is an excellent place to **borrow existing software rather than invent it ourselves**.

Useful GitHub projects include:

**`seralifatih/congress-trading-pipeline`**
Pulls from official House/Senate disclosure sources and creates cleaned/deduplicated structured records. ([GitHub][13])

**PoliTracker**
Interesting because its ingestion handles official disclosure data and scanned documents/OCR cases. ([GitHub][14])

**`us-congress-stock-transactions-retrieval`**
Python implementation for retrieving/parsing House reports. ([GitHub][15])

**Quantgress**
A particularly interesting architectural reference: a self-hosted project combining Congressional trading, campaign finance, lobbying, USAspending and other government datasets in a unified analytical pipeline. I would study its code rather than blindly adopt its schema. ([GitHub][16])

For OpenDiscourse, preserve the actual disclosure:

```text
disclosure
transaction
asset
transaction_type
transaction_date
filing_date
amount_min
amount_max
owner
source_document
```

Do **not** convert `$15,001–$50,000` into an invented `$32,500` canonical value. An analytical mart may calculate a midpoint later, while preserving the actual disclosed range.

---

# 7. Elections

You need elections if you eventually want to study whether policies or economic conditions affect electoral outcomes.

Two very useful national research sources are:

### MIT Election Data + Science Lab

Federal, state and local election datasets, with county/precinct-level datasets available for many contests. Their catalog continues to publish updated 2024 datasets in 2026. ([MIT Election Lab][17])

### Redistricting Data Hub

Extremely useful for:

* precinct election results
* precinct boundaries
* congressional boundaries
* legislative districts
* demographic joins
* turnout datasets
* redistricting vintages

They maintain data/source directories across the states and have national joined precinct datasets. ([Redistricting Data Hub][18])

Use those **in addition to official state election authorities**, not instead of them.

That gives you:

```text
candidate
     ↓
election
     ↓
contest
     ↓
precinct result
     ↓
district
     ↓
Census geography
```

That is enormously valuable for OpenDiscourse.

---

# 8. Census: your choices are already good, but we can expand them significantly

Your current use of Census ACS + TIGER + PEP + DHC + CBP is good.

The Census Bureau exposes the Data API, TIGERweb and geocoding services programmatically. ([Census.gov][19])

### Python libraries worth using

**`censusdis`** is one I particularly like for OpenDiscourse.

It supports Census dataset/geography discovery and makes Census API work much less painful. ([GitHub][20])

Also useful:

**`datamade/census`** — lightweight Python Census API wrapper. ([GitHub][21])

**`pygris`** — excellent Python access to TIGER/Line and cartographic boundaries. ([GitHub][22])

And Census now publishes modern TIGER/Line GeoPackages as well as traditional formats; GeoPackage is attractive for your raw lake. ([Census.gov][23])

### Census datasets I'd eventually catalog

| Dataset                 | Why it matters                            |
| ----------------------- | ----------------------------------------- |
| ACS 1-year / 5-year     | demographics, income, housing, employment |
| Decennial Census        | population baseline                       |
| PEP                     | annual population estimates               |
| TIGER/Line              | geography                                 |
| CBP                     | businesses/employment                     |
| **SAIPE**               | poverty and income                        |
| **SAHIE**               | health insurance                          |
| **PUMS**                | microdata                                 |
| **LEHD / LODES**        | jobs/commuting/workplace geography        |
| **BDS**                 | business formation/destruction            |
| Building Permits Survey | construction/housing                      |
| CPS                     | labor/social outcomes                     |
| SIPP                    | household/program participation           |
| American Housing Survey | housing conditions                        |
| Migration flows         | population movement                       |

**LEHD/LODES in particular should eventually be in OpenDiscourse.**

It allows much better research into employment location and commuting patterns than ACS alone.

---

# 9. Economic data

You already have FRED. Keep it—but expand the economic spine beyond FRED.

## FRED + ALFRED

Use **FRED API directly** for canonical acquisition.

For bulk backfills, the newer release-oriented API capabilities are useful; ALFRED is important whenever you need to know **what data actually looked like at a historical point in time rather than today's revised number**. ([FRED][24])

`fredapi` is fine as a Python convenience wrapper. ([GitHub][25])

But retain the FRED IDs and raw responses.

## BLS

This should be a major OpenDiscourse source.

Use BLS API for:

* CPI
* PPI
* unemployment
* LAUS
* CES
* QCEW
* wages
* occupations
* workplace injuries
* productivity

The Public Data API covers BLS statistical programs programmatically. ([Bureau of Labor Statistics][26])

**QCEW + LAUS should be relatively high priority** because they give you strong local labor-market outcomes.

## BEA

Add the BEA API.

Especially:

* county GDP
* state GDP
* personal income
* employment
* regional economic accounts
* industry accounts

BEA exposes those through its API, and BEA also maintains Python tooling. ([BEA Apps][27])

## Treasury Fiscal Data

Absolutely include it.

Fiscal Data provides machine-readable APIs and data dictionaries for federal fiscal datasets, including debt and broader government finances. ([Fiscal Data][28])

You already have Treasury curve support; expand the catalog over time.

---

# 10. Government spending: USAspending should be a major source

This may be one of the **most useful sources in the entire project** for studying implementation of policy.

USAspending exposes:

* contracts
* grants
* loans
* direct payments
* awards
* transactions
* federal accounts
* agencies
* recipients
* geographic information
* subawards
* bulk downloads

Its API directly supports bulk award and transaction downloads. ([USAspending API][29])

That lets you construct:

```text
law / appropriation
        ↓
federal program
        ↓
agency
        ↓
award
        ↓
recipient
        ↓
county / congressional district
        ↓
economic/social outcome
```

That is exactly the kind of bridge OpenDiscourse needs between **legislation** and **observable effects**.

---

# 11. SAM.gov

I'd ingest a selective subset rather than everything.

SAM.gov exposes APIs for:

* assistance listings
* entities
* contract awards
* contract opportunities
* subaward reporting
* federal organizational hierarchy
* exclusions

GSA currently publishes these APIs centrally. ([GSA Open Technology][30])

The Entity API can also help resolve government contractors using **UEI, CAGE, NAICS and company information**. ([GSA Open Technology][31])

Very useful alongside USAspending.

---

# 12. Regulation: a critical missing link between a law and its actual effect

A bill becoming law is frequently only the beginning.

You really want:

```text
Bill
 ↓
Law
 ↓
Statute
 ↓
Agency
 ↓
Proposed rule
 ↓
Public comments
 ↓
Final rule
 ↓
CFR provision
 ↓
Enforcement / spending / outcome
```

### Sources

**Federal Register**

Rules, proposed rules, notices, executive documents.

**Regulations.gov API**

Documents, dockets, comments and attachments. The current API explicitly supports documents/comments/dockets. ([GSA Open Technology][32])

**eCFR**

Current regulatory code.

**CFR**

Historical annual regulatory snapshots.

GovInfo provides bulk material for Federal Register/CFR/eCFR-related collections, which fits your immutable-raw-artifact philosophy very well. ([GovInfo][2])

There's also the Python `pyCFR` project for working with eCFR data, although I'd consider it a convenience layer rather than a canonical dependency. ([GitHub][33])

This entire regulatory dimension should eventually become a major OpenDiscourse module.

---

# 13. Crime

Your choice of FBI CDE is correct.

Use:

### FBI Crime Data Explorer / UCR

Relevant datasets include:

* NIBRS
* Summary Reporting System
* arrests
* hate crime
* law-enforcement data
* agency participation
* estimated crime

The FBI provides downloadable CDE data, including larger files. ([CDE UCR CJIS][34])

There's also an FBI-maintained GitHub repository for the Crime Data API/backend that can be useful for understanding their schema and implementation. ([GitHub][35])

One crucial modeling rule:

**Store reporting/participation coverage alongside crime observations.**

NIBRS participation has changed substantially over time, so naïvely interpreting raw incident-count changes as crime changes can create serious research errors. ([CDE UCR CJIS][36])

Also eventually ingest relevant **Bureau of Justice Statistics** datasets for incarceration, victimization, prisons and jails.

---

# 14. Housing

You already have ACS housing. Add:

### FHFA House Price Index

Very useful because it has long-running housing-price measures at multiple geographic levels including state, metro, county and other geographies. ([FHFA.gov][37])

### HUD

Useful datasets/APIs include:

* Fair Market Rents
* income limits
* CHAS
* housing affordability/needs
* public/subsidized housing
* homelessness datasets

HUD continues to expose programmatic datasets around these programs. ([HUD User][38])

Potential later additions:

* Zillow/ZTRAX-type private datasets where licenses allow
* county recorder data
* building permits
* HMDA mortgage data

HMDA in particular would be excellent for studying housing-credit effects.

---

# 15. Health

For policy outcomes, health belongs in the database.

### CDC WONDER

Excellent for:

* mortality
* causes of death
* population statistics
* natality
* various public-health outcomes

CDC maintains programmatic access to WONDER, subject to dataset-specific disclosure rules. ([CDC WONDER][39])

### CMS / data.cms.gov

Later add:

* Medicare
* Medicaid
* provider data
* hospital outcomes
* utilization
* drug spending
* enrollment

These could become very valuable for studies involving health legislation.

---

# 16. Education

Use NCES and Department of Education datasets.

Worth cataloging:

| Dataset                      | Use                       |
| ---------------------------- | ------------------------- |
| Common Core of Data          | schools/districts         |
| EDFacts                      | K-12 outcomes             |
| Civil Rights Data Collection | student/school conditions |
| NAEP                         | achievement               |
| IPEDS                        | universities              |
| College Scorecard            | higher education outcomes |

NCES continues to publish current CCD school and LEA datasets with stable identifiers, which is useful for longitudinal joins. ([National Center for Education Statistics][40])

---

# 17. Environmental and energy data

### EPA Envirofacts

Excellent for facilities, emissions and environmental regulatory datasets. EPA exposes programmatic REST-style services and multiple export formats. ([US EPA][41])

### EIA

Energy Information Administration API:

* electricity
* natural gas
* petroleum
* generation
* prices
* production
* energy consumption

Excellent source for evaluating energy policy. ([U.S. Energy Information Administration][42])

### NOAA/NCEI

Important as a **confounder dataset**.

Weather can affect employment, agriculture, energy prices, disasters, mortality, crime, migration and other outcomes.

NCEI has JSON APIs plus bulk/GIS/NetCDF services. ([NCEI][43])

### USGS

Eventually add:

* water flows
* groundwater
* drought/hydrology
* geological/environmental datasets

---

# 18. Agriculture

For agricultural policy:

### USDA NASS Quick Stats

This is extremely comprehensive for:

* crop production
* livestock
* prices
* acreage
* yields
* county/state agriculture
* Census of Agriculture-related measures

USDA supplies API access and bulk compressed datasets, with Quick Stats data refreshed frequently. ([NASS][44])

Also eventually investigate USDA ERS economic datasets.

---

# 19. Courts and judicial outcomes

Add **CourtListener**.

This gives you a way to connect laws/regulations to litigation.

CourtListener provides APIs/bulk access around:

* opinions
* dockets
* courts
* judges
* RECAP/PACER-derived materials where available
* oral arguments

It has thousands of court/jurisdiction identifiers and mature API infrastructure. ([CourtListener][45])

Then OpenDiscourse could eventually model:

```text
law
 ↓
regulation
 ↓
court case
 ↓
decision
 ↓
appeal
 ↓
precedent / invalidation / injunction
```

That's a fascinating research surface.

---

# 20. SEC / corporations

SEC EDGAR is another source I would catalog.

`data.sec.gov` exposes unauthenticated JSON APIs for company submissions and XBRL financial data. ([SEC][46])

Relevant things could include:

* company financials
* industry impacts
* 10-K/10-Q filings
* Form 4 insider transactions
* 13F holdings
* company identifiers
* corporate disclosure text

This could help study industry responses around regulations/laws and improve entity resolution for companies appearing in lobbying, government awards and financial disclosures.

---

# 21. Disasters and transportation

These are easy to overlook but useful controls/outcomes.

I would eventually catalog:

**FEMA/OpenFEMA**

* disaster declarations
* individual assistance
* public assistance
* mitigation
* claims

**NHTSA FARS**

* fatal crashes
* vehicles
* road safety

**Bureau of Transportation Statistics**

* aviation
* freight
* transportation activity

**FHWA**

* roads
* traffic
* highway programs

These become important when evaluating transportation, disaster-relief and infrastructure policies.

---

# 22. Data.gov is useful—but as discovery, not canonical storage

Use **Data.gov** to discover datasets and agencies.

Don't build OpenDiscourse ingestion around Data.gov itself whenever an authoritative agency API exists.

Think:

```text
Data.gov
   ↓ discovery
agency API / bulk endpoint
   ↓ acquisition
OpenDiscourse
```

That keeps provenance as close to the publisher as possible.

---

# 23. Python/tooling stack I would standardize on

You've already accidentally assembled most of the stack I'd choose.

| Function                    | Tool                                 |
| --------------------------- | ------------------------------------ |
| HTTP/API                    | **httpx**                            |
| retries                     | **tenacity**                         |
| contracts/models            | **Pydantic**                         |
| PostgreSQL                  | **psycopg 3**                        |
| migrations                  | **Alembic**                          |
| lightweight EL              | **dlt**                              |
| huge transformations        | **Polars**                           |
| lake format                 | **Parquet + PyArrow**                |
| querying lake               | **DuckDB**                           |
| geography                   | **GeoPandas + Pyogrio + Shapely**    |
| DB geography                | **PostGIS**                          |
| Census                      | **censusdis**, optionally `census`   |
| TIGER                       | **pygris**                           |
| FRED convenience            | **fredapi**                          |
| analytics marts             | **dbt**                              |
| workflow orchestration      | **Prefect 3**                        |
| validation                  | **Pandera**                          |
| testing                     | pytest + Hypothesis + Testcontainers |
| lint/type                   | Ruff + `ty`                          |
| very large PostgreSQL loads | **COPY**, not ORM inserts            |

`dlt` is useful for turning REST/API sources into PostgreSQL pipelines and already fits your project as optional staging infrastructure. ([dltHub][47])

Pandera would be a good addition for validating DataFrames/Arrow data before promotion into canonical tables. ([Pandera][48])

DuckDB is particularly valuable because it can query Parquet/object storage directly rather than forcing every raw dataset into PostgreSQL. ([DuckDB][49])

And because you're already using Prefect, **I would not add Dagster right now**. Dagster is good, but having two orchestration frameworks would add complexity without solving a problem you currently have. ([Dagster][50])

---

# 24. I would use bulk → Parquet → PostgreSQL much more aggressively

One refinement I would make to the existing design:

Don't interpret “ingest government data” as “everything belongs in PostgreSQL.”

I'd use:

```text
Internet
   │
   ▼
┌─────────────────────────────┐
│ RAW DATA LAKE               │
│ original ZIP/XML/JSON/CSV   │
│ immutable + checksummed     │
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│ NORMALIZED LAKE             │
│ Parquet                     │
│ partitioned by source/year  │
└──────────────┬──────────────┘
               │
        DuckDB / Polars
               │
               ▼
┌─────────────────────────────┐
│ PostgreSQL + PostGIS        │
│ identities                  │
│ curated facts               │
│ relationships               │
│ research marts              │
└─────────────────────────────┘
```

That is particularly appropriate for:

* FEC
* Census
* election precinct data
* FBI crime data
* USAspending
* SEC filings
* huge administrative datasets

Postgres becomes the **research database**, not your ZIP-file warehouse.

That is consistent with the direction your current `docs/blueprint.md` already takes.

---

# 25. A source registry is going to become one of OpenDiscourse's most valuable assets

Rather than immediately coding every one of these, I would greatly expand:

```text
inventory/sources.yaml
```

A source could have fields conceptually like:

```yaml
id: fec.individual_contributions
publisher: Federal Election Commission
authority: primary
domain: campaign_finance

acquisition:
  preferred: bulk
  incremental: api

formats:
  - zip
  - csv

grain: transaction

identifiers:
  - sub_id
  - committee_id
  - candidate_id

geographies:
  - state
  - zip

cadence: daily

connector:
  implementation: fec
  library: null

raw_retention: permanent
canonical_target: fact.campaign_transaction
```

Then **the catalog itself tells us what software to build**.

---

# 26. My proposed OpenDiscourse source portfolio

If we assemble everything discussed above, I'd organize the project approximately like this:

| Domain                  | Core sources                                                     |
| ----------------------- | ---------------------------------------------------------------- |
| Federal legislation     | Congress.gov, GovInfo, unitedstates/congress                     |
| Federal legislators     | congress-legislators, Congress.gov                               |
| State legislation       | OpenStates / Plural                                              |
| Local government        | OCD IDs + jurisdiction-specific connectors                       |
| Elections               | official state sources, MIT Election Lab, Redistricting Data Hub |
| Campaign finance        | FEC                                                              |
| Lobbying                | LDA.gov                                                          |
| Financial disclosures   | House Clerk, Senate eFD                                          |
| Federal spending        | USAspending                                                      |
| Contractors/programs    | SAM.gov                                                          |
| Regulations             | Federal Register, Regulations.gov, eCFR/CFR                      |
| Courts                  | CourtListener                                                    |
| Demographics            | Census/ACS/Decennial/PEP                                         |
| Geography               | TIGER/Line                                                       |
| Employment/business     | BLS, LEHD/LODES, CBP, BDS                                        |
| Economic accounts       | BEA                                                              |
| Macro                   | FRED/ALFRED                                                      |
| Treasury/fiscal         | Treasury Fiscal Data                                             |
| Housing                 | ACS, FHFA, HUD                                                   |
| Crime                   | FBI CDE/UCR, BJS                                                 |
| Health                  | CDC WONDER, CMS                                                  |
| Education               | NCES, EDFacts, CRDC, IPEDS                                       |
| Environment             | EPA                                                              |
| Energy                  | EIA                                                              |
| Weather/climate         | NOAA/NCEI                                                        |
| Water/natural resources | USGS                                                             |
| Agriculture             | USDA NASS/ERS                                                    |
| Corporate               | SEC EDGAR                                                        |
| Disasters               | FEMA/OpenFEMA                                                    |
| Transportation          | NHTSA/FARS, BTS, FHWA                                            |

That is much closer to the complete research universe I think you're actually trying to build.

---

# The most important architectural realization

OpenDiscourse shouldn't really be thought of as a **government-data downloader** anymore.

It's becoming a **temporal policy research graph sitting on top of a reproducible lakehouse**.

The interesting part isn't merely having `ACS`, `FEC`, `Congress` and `FRED` in the same PostgreSQL server.

It's being able to express:

```text
Representative X
      │
      ├── represented District Y
      │       └── contained Census geographies A/B/C
      │
      ├── received campaign contributions from Industry Z
      │
      ├── was lobbied regarding Issue Q
      │
      ├── sponsored Bill 123
      │
      └── voted YES on Bill 456
                     │
                     ▼
                 became Law
                     │
                     ▼
             Agency implemented
                     │
                Regulation R
                     │
                     ▼
            $800M appropriated
                     │
               USAspending
                     │
         ┌───────────┴──────────┐
         ▼                      ▼
      County A               County B
         │                      │
     employment              employment
     wages                   wages
     housing                 housing
     crime                   crime
     mortality               mortality
     migration               migration
         │                      │
         └──────────┬───────────┘
                    ▼
              policy research
```

**That** is where OpenDiscourse becomes different from just another API wrapper.

And this makes me even more confident in the raw/core/fact/mart separation you've now established.

## What I think we should do next

Rather than immediately writing another connector, I recommend three concrete follow-ups:

1. **Build a comprehensive `SOURCE-CATALOG.md` / machine-readable `sources.yaml` expansion** containing all the sources above, their APIs/bulk downloads, helper libraries/repos, identifiers, grain, temporal coverage, geography, licensing, update cadence, and whether OpenDiscourse currently supports them. This becomes our authoritative acquisition map.

2. **Audit your existing connectors against this catalog.** Congress/GovInfo/OpenStates/FEC/Census/FRED/etc. can each be marked `implemented`, `partial`, `registered`, `candidate`, or `blocked`. That will expose duplication and missing pieces immediately.

3. **Prioritize the “policy chain” connectors next rather than random datasets.** The especially valuable missing pieces are **LDA lobbying → House/Senate financial disclosures → USAspending → Regulations.gov/Federal Register/eCFR → elections**, followed by outcome datasets such as BLS/BEA/FBI/FHFA/CDC.

I would also make a fourth improvement: create a **community-tool inventory** alongside source inventory—for example `unitedstates/congress`, `congress-legislators`, `censusdis`, `pygris`, the disclosure parsers, CourtListener, etc.—so an agent working on OpenDiscourse is explicitly instructed: **check the inventory and upstream projects before implementing acquisition code.**

If we do that next, we can go source-by-source and make a concrete **“USE / WRAP / REFERENCE / DON'T NEED” matrix for OpenDiscourse**, including the exact GitHub repo/package/API for every source and identifying which of your current custom code can be deleted or simplified. That is the direction I'd take before adding more ingestion code.

[1]: https://api.congress.gov/?utm_source=chatgpt.com "Congress.gov API"
[2]: https://www.govinfo.gov/developers?utm_source=chatgpt.com "Developer Hub | GovInfo"
[3]: https://www.senate.gov/general/XML.htm?utm_source=chatgpt.com "U.S. Senate: XML Sources Available on Senate.gov"
[4]: https://github.com/unitedstates/congress?utm_source=chatgpt.com "GitHub - unitedstates/congress: Public domain data collectors for the work of Congress, including legislation, amendments, and votes. · GitHub"
[5]: https://github.com/unitedstates/congress-legislators?utm_source=chatgpt.com "GitHub - unitedstates/congress-legislators: Members of the United States Congress, 1789-Present, in YAML/JSON/CSV, as well as committees, presidents, and vice presidents. · GitHub"
[6]: https://open.pluralpolicy.com/data/?utm_source=chatgpt.com "Open States Bulk Data"
[7]: https://github.com/opencivicdata/docs.opencivicdata.org/blob/master/ocdids.rst?utm_source=chatgpt.com "docs.opencivicdata.org/ocdids.rst at master · opencivicdata/docs.opencivicdata.org · GitHub"
[8]: https://pluralpolicy.com/tools?utm_source=chatgpt.com "Tools and API | Plural"
[9]: https://github.com/opencivicdata/ocd-division-ids?utm_source=chatgpt.com "GitHub - opencivicdata/ocd-division-ids: Open Civic Data Division IDs definition & canonical repository · GitHub"
[10]: https://api.open.fec.gov/developers?trk=public_post_comment-text&utm_source=chatgpt.com "OpenFEC API Documentation"
[11]: https://lda.gov/api/tos/?utm_source=chatgpt.com "API Help | LDA.gov"
[12]: https://disclosures-clerk.house.gov/FinancialDisclosure?utm_source=chatgpt.com "Office of the Clerk, U.S. House of Representatives - Financial Disclosure Reports"
[13]: https://github.com/seralifatih/congress-trading-pipeline?utm_source=chatgpt.com "GitHub - seralifatih/congress-trading-pipeline: Congressional stock trading disclosures (US House + Senate) as clean, deduplicated JSON. Parses official STOCK Act filings straight from the source — no aggregators. · GitHub"
[14]: https://github.com/shaqnawe/Politracker?utm_source=chatgpt.com "GitHub - shaqnawe/Politracker: Track U.S. Congress stock trades, straight from official STOCK Act disclosures — no middleman data feed. · GitHub"
[15]: https://github.com/jaredbest/us-congress-stock-transactions-retrieval?utm_source=chatgpt.com "GitHub - jaredbest/us-congress-stock-transactions-retrieval: A Jupyter Notebook that retrieves stock trade information of Members of Congress from publicly available financial disclosure reports. · GitHub"
[16]: https://github.com/DMulajkar/Quantgress?utm_source=chatgpt.com "GitHub - DMulajkar/Quantgress: Scrapes congressional trading (Senate + House PTRs) and a growing catalog of alternative datasets — lobbying, government contracts, Form 4 insider trades, 13F holdings, off-exchange short volume, patents, corporate donors, Wikipedia pageviews, into a resumable DuckDB pipeline · GitHub"
[17]: https://electionlab.mit.edu/data?utm_source=chatgpt.com "Data | MIT Election Lab"
[18]: https://redistrictingdatahub.org/data/download-data/?utm_source=chatgpt.com "Download Data - Redistricting Data Hub"
[19]: https://www.census.gov/data/developers/guidance/api-user-guide.html?utm_source=chatgpt.com "Census Data API User Guide"
[20]: https://github.com/censusdis/censusdis?utm_source=chatgpt.com "GitHub - censusdis/censusdis: censusdis is a Python package for discovering, loading and analyzing, U.S. Census demographic, economic, and geographic data and metadata. It is designed to be intuitive and Pythonic, giving users access to the full collection of data and maps the U.S. Census publishes via their APIs. · GitHub"
[21]: https://github.com/datamade/census?utm_source=chatgpt.com "GitHub - datamade/census: A Python wrapper for the US Census API. · GitHub"
[22]: https://github.com/walkerke/pygris?utm_source=chatgpt.com "GitHub - walkerke/pygris: Use US Census shapefiles in Python (port of the R tigris package) · GitHub"
[23]: https://www.census.gov/geographies/mapping-files/time-series/geo/tiger-geopackage-file.html?utm_source=chatgpt.com "TIGER/Line GeoPackages"
[24]: https://fred.stlouisfed.org/docs/api/fred/?utm_source=chatgpt.com "St. Louis Fed Web Services: FRED® API"
[25]: https://github.com/mortada/fredapi/blob/master/README.md?utm_source=chatgpt.com "fredapi/README.md at master · mortada/fredapi · GitHub"
[26]: https://www.bls.gov/developers/api_signature_v2.htm?utm_source=chatgpt.com "BLS Public Data API Signatures (Version 2.0) : U.S. Bureau of Labor Statistics"
[27]: https://apps.bea.gov/api/signup/?utm_source=chatgpt.com "BEA Data Application Programming Interface (API)"
[28]: https://fiscaldata.treasury.gov/datasets/historical-debt-outstanding/?utm_source=chatgpt.com "Historical Debt Outstanding | U.S. Treasury Fiscal Data"
[29]: https://api.usaspending.gov/docs/endpoints?utm_source=chatgpt.com "USAspending API"
[30]: https://open.gsa.gov/api/?utm_source=chatgpt.com "APIs | GSA Open Technology"
[31]: https://open.gsa.gov/api/entity-api/?utm_source=chatgpt.com "SAM.gov Entity Management API | GSA Open Technology"
[32]: https://open.gsa.gov/api/regulationsgov/?utm_source=chatgpt.com "Regulations.gov API | GSA Open Technology"
[33]: https://github.com/getinterface/pyCFR?utm_source=chatgpt.com "GitHub - getinterface/pyCFR: A production-grade Python REST API wrapper for the Electronic Code of Federal Regulations (eCFR) API. · GitHub"
[34]: https://cde.ucr.cjis.gov/LATEST/webapp/?_nhids=zdWAigrx&_nlid=BQDNHg6MZQ&utm_source=chatgpt.com "CDE"
[35]: https://github.com/fbi-cde/crime-data-api?utm_source=chatgpt.com "GitHub - fbi-cde/crime-data-api: RESTful API service providing Uniform Crime Reporting (UCR) data for the United States · GitHub"
[36]: https://cde.ucr.cjis.gov/LATEST/resources/reports/UCR%20Summary%20of%20Reported%20Crimes%20in%20the%20Nation%202024.pdf?utm_source=chatgpt.com "Table 1: Participation, 2023-2024"
[37]: https://www.fhfa.gov/data/hpi/datasets?utm_source=chatgpt.com "FHFA House Price Index® Datasets | FHFA"
[38]: https://www.huduser.gov/portal/dataset/chas-api.html?utm_source=chatgpt.com "CONSOLIDATED PLANNING/CHAS Dataset API Documentation | HUD USER"
[39]: https://wonder.cdc.gov/wonder/help/wonder-api.html?utm_source=chatgpt.com "CDC WONDER API for Data Query Web Service"
[40]: https://nces.ed.gov/use-work/dataset/2025-26-common-core-data-ccd-preliminary-directory-files?utm_source=chatgpt.com "2025-26 Common Core of Data (CCD) Preliminary Directory Files | IES"
[41]: https://www.epa.gov/enviro/envirofacts-data-service-api?utm_source=chatgpt.com "Envirofacts Data Service API | US EPA"
[42]: https://www.eia.gov/developer/?utm_source=chatgpt.com "U.S. Energy Information Administration - EIA - Independent Statistics and Analysis"
[43]: https://www.ncei.noaa.gov/cdo-web/webservices/v2?utm_source=chatgpt.com "Web Services API (version 2) Documentation | Climate Data Online (CDO) | National Climatic Data Center (NCDC)"
[44]: https://www.nass.usda.gov/Quick_Stats/?utm_source=chatgpt.com "USDA - National Agricultural Statistics Service - Quick Stats"
[45]: https://www.courtlistener.com/help/?utm_source=chatgpt.com "Getting Help – CourtListener.com"
[46]: https://www.sec.gov/search-filings/edgar-application-programming-interfaces?utm_source=chatgpt.com "SEC.gov | EDGAR Application Programming Interfaces (APIs)"
[47]: https://dlthub.com/docs/pipelines/rest_api/load-data-with-python-from-rest_api-to-postgres?utm_source=chatgpt.com "Rest API to PostgreSQL: Load data with the dlt python library | dlt Docs"
[48]: https://pandera.readthedocs.io/en/latest/dataframe_schemas.html?utm_source=chatgpt.com "DataFrame Schemas - pandera documentation"
[49]: https://duckdb.org/docs/current/core_extensions/httpfs/overview?utm_source=chatgpt.com "httpfs Extension for HTTP and S3 Support – DuckDB"
[50]: https://dagster.io/platform-overview/data-orchestration?utm_source=chatgpt.com "Data Orchestration for Modern Workflows | Dagster"
