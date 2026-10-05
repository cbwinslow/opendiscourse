# District-linked source verification — 2026-10-05

Status: research evidence for Epic 10. The authoritative execution contract is
`_bmad-output/specs/spec-district-linked-context/`. A source-specific story must
re-check fast-changing access/terms immediately before implementation.

## Verified first-wave Census geography facts

Official sources:

- ACS geography by year:
  https://www.census.gov/programs-surveys/acs/geography-acs/geography-boundaries-by-year.html
- 2020 Census geographic relationship files:
  https://www.census.gov/geographies/reference-files/2020/geo/relationship-files.html
- Congressional/SLD relationship layouts:
  https://www.census.gov/programs-surveys/geography/technical-documentation/records-layout/2020-CD-SLD-record-layout.html
- 119th Congressional District programme:
  https://www.census.gov/programs-surveys/decennial-census/about/rdo/congressional-districts.119th_Congress.html
- 119th Congressional District BEF:
  https://www.census.gov/geographies/mapping-files/2025/dec/rdo/119-congressional-district-bef.html
- 2024 State Legislative District programme:
  https://www.census.gov/programs-surveys/decennial-census/about/rdo/state-legislative-district.2024.html
- 2024 SLD BEF:
  https://www.census.gov/geographies/mapping-files/2025/dec/rdo/2024-state-legislative-bef.html

Verified mapping used by `inventory/geography-vintages.yaml`:

| ACS 5-year release | Survey window | Congressional districts | State legislative districts | PUMA |
| --- | --- | --- | --- | --- |
| 2021 | 2017-2021 | 116th Congress | 2018 SLD | 2010 |
| 2022 | 2018-2022 | 118th Congress | 2022 SLD | 2020 |
| 2023 | 2019-2023 | 118th Congress | 2022 SLD | 2020 |
| 2024 | 2020-2024 | 119th Congress | 2024 SLD | 2020 |

The ACS 5-year product uses the geography vintage of the final year in its
survey window. This is why release year alone must not be translated to Congress
number by arithmetic.

Relationship files describe geographic relationships for a stated vintage. Do
not treat every overlap field as a demographic allocation weight.

BEFs assign whole 2020 Census blocks to districts for tabulation. Where an
official plan splits a block, Census TIGER/Line geometry can depict the actual
split boundary; the whole-block BEF does not replace that geometry.

## Verified post-slice source candidates

### Census CVAP

Official source:
https://www.census.gov/programs-surveys/decennial-census/about/voting-rights/cvap/2020-2024-CVAP.html

The 2020-2024 Citizen Voting Age Population special tabulation was released in
2026. It includes congressional districts, upper/lower state legislative
districts, county, place, tract and block-group geographies. It is an unusually
strong post-slice source because it aligns directly with the 2024 ACS geography
vintage rather than requiring a ZIP/county approximation.

Decision: Story 10.7, after `slice_proven`.

### Census County Business Patterns

Official API/product documentation:
https://www.census.gov/data/developers/data-sets/cbp-zbp/cbp-api.html

CBP supports congressional-district geography and publishes establishment,
employment and payroll statistics by industry. OpenDiscourse already has CBP
county ingestion.

Decision: extend the existing source in Story 10.8. Before code, verify the
congressional-district vintage used by each selected CBP reference year; do not
infer it from the publication date.

### IRS Statistics of Income — Congressional District

Official entry point:
https://www.irs.gov/statistics/soi-tax-stats-data-by-congressional-district

IRS publishes direct congressional-district individual income-tax statistics,
including income, wages, returns, taxes and credits. Current official pages
cover tax years 2017-2022.

Decision: Story 10.9. Prefer the direct district files to ZIP/county
interpolation and retain the district-boundary basis stated in each year's
documentation.

### Census LEHD LODES

Official source:
https://lehd.ces.census.gov/data/

LODES Version 8 uses 2020 Census blocks and provides workplace-area,
residence-area and origin-destination files. Official documentation records
state/year availability and gaps.

Decision: Story 10.10. It is valuable precisely because block-level records can
be aggregated to political boundaries, but it requires a capacity-gated bulk
story rather than being pulled into the first slice.

### GAO Community Project Funding / Congressionally Directed Spending

Official source:
https://www.gao.gov/tracking-funds

GAO publishes downloadable project-level data for Community Project Funding /
Congressionally Directed Spending and exposes analysis by requesting member,
location and agency. The current tracker covers FY2022-FY2024.

Decision: Story 10.12, behind the reviewed person-identity gate. Requesting
member display text is not an identity key.

## Reuse/tool decisions

### `pygris`

Repository: https://github.com/walkerke/pygris

`pygris` is an actively maintained MIT-licensed Python library for Census
TIGER/Line geography and exposes helpers for congressional districts, state
legislative districts, PUMAs, tracts, block groups, blocks and voting districts.

Decision: **evaluate in Story 10.2 before extending custom TIGER download
code.** It may save URL/discovery/parsing work. OpenDiscourse still retains the
official Census ZIP URL, bytes, checksum and its own canonical keys.

### U.S. Census Bureau Data API MCP

Repository:
https://github.com/uscensusbureau/us-census-bureau-data-api-mcp

This is an official Census Bureau MCP for dataset/geography discovery and Data
API queries.

Decision: useful for Claude/Codex interactive source discovery and schema
verification. It is not production ETL and its local state is not a warehouse
authority.

### `beaapi`

Repository: https://github.com/us-bea/beaapi

Official BEA Python package, useful for metadata discovery and Regional API
access.

Decision: preferred optional adapter candidate when the BEA source story opens.
Keep/disable any package cache so retained project evidence stays under
`DATA_ROOT`.

### `usaspending-orm`

Repository: https://github.com/planetary-society/usaspending-orm

Typed Python client/ORM for USAspending with pagination/retry conveniences.

Decision: smoke-test behind the provider boundary in Story 10.11 before writing
custom pagination/model code. Official USAspending responses/bulk artifacts
remain evidence.

### LODES community downloaders

References:

- https://github.com/jamaps/lehd
- https://github.com/UrbanInstitute/lodes-data-downloads

Decision: reference/evaluate only. They can save time understanding file
patterns but are not pre-approved production dependencies; Story 10.10 must
check maintenance, license and Version-8 coverage before adoption.

## Tooling we should keep rather than replace

- PostgreSQL 17 + PostGIS: canonical spatial/system-of-record layer.
- GeoPandas + Pyogrio + Shapely: retained TIGER parsing/validation fallback.
- dbt: owns `mart`, including `mart.congressional_district_period`.
- DuckDB/Parquet: derived exploration/export only.
- dlt: optional source-to-`stage` helper only, never `core`/`fact`.
- OpenStates/Open Civic Data IDs: political identity language.
- Census GEOID + boundary vintage: statistical/spatial identity.

The principle remains **wrap maintained acquisition/parsing tools where they
save real work, but never outsource provenance, canonical identity, or source
completion to them**.
