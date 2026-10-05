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

### Story 10.2 implementation verification

Re-checked immediately before implementation:

- 2024 TIGER/Line release page:
  https://www.census.gov/geographies/mapping-files/time-series/geo/tiger-line-file.2024.html
- 2024 technical documentation:
  https://www.census.gov/programs-surveys/geography/technical-documentation/complete-technical-documentation/tiger-geo-line.2024.html
- official CD directory:
  https://www2.census.gov/geo/tiger/TIGER2024/CD/
- official SLDU directory:
  https://www2.census.gov/geo/tiger/TIGER2024/SLDU/
- official SLDL directory:
  https://www2.census.gov/geo/tiger/TIGER2024/SLDL/

Census states that the 2024 vintage contains the 119th Congressional District
and 2024 state-legislative plans and that legal boundaries/names are as of
2024-01-01. The official directory members use
`tl_2024_<state FIPS>_cd119.zip`, `tl_2024_<state FIPS>_sldu.zip`, and
`tl_2024_<state FIPS>_sldl.zip`. The publisher indexes contain **56 CD119
archives, 52 SLDU archives, and 50 SLDL archives (158 total)**. These counts are
now a fail-closed completeness contract for the frozen 2024 package: discovery
still comes from Census, but a partial directory response cannot silently become
an approved manifest. File sizes are publisher-listed and are re-probed by the
normal `tiger-bulk-preview` capacity gate before transfer.

The 2024 record layouts make the join contract explicit:

- CD119: `STATEFP`, `CD119FP`, `GEOID`, `NAMELSAD`, `CDSESSN`;
  `CDSESSN` must be `119`.
- SLDL: `STATEFP`, `SLDLST`, `GEOID`, `NAMELSAD`, `LSY`;
  `LSY` must be `2024`.
- SLDU uses the analogous current upper-chamber fields and the same
  `LSY=2024` contract.

The technical-documentation legal disclaimer says U.S. Government works are
not copyright-protected under 17 U.S.C. 105, so Census materials may be
reproduced; Census requests source citation. TIGER/Line is a registered
trademark and the statistical boundary disclaimer must not be misrepresented as
a legal land-description claim.

Implementation decision: discover the exact published ZIP members from those
three Census directory indexes, then pass them through OpenDiscourse's existing
capacity preview, resumable transfer, checksum retention, staging and PostGIS
promotion. This avoids a guessed state/chamber manifest and preserves the
existing evidence model.

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

Story 10.2 evaluation result: **do not adopt `pygris` as the production
acquisition path.** Inspection of `pygris/legislative.py` confirms the same
2024 Census URL patterns used here and makes it a useful validation oracle.
However, its all-state congressional helper catches download exceptions, and it
does not provide OpenDiscourse artifact/version/checksum/run evidence. The
production path therefore reuses the existing OpenDiscourse TIGER downloader
and Pyogrio loader while borrowing the verified upstream URL conventions. No
new runtime dependency is added.

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
