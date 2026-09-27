# ACS release and comparison matrix

## Official availability

| Product | Standard official releases to acquire | Geography limit | Explicit gap / boundary |
|---|---|---|---|
| ACS 1-year Detailed Tables | 2005-2019 and 2021-2024 | Census-published eligible geographies; currently areas with population 65,000 or more | No standard 2020 ACS 1-year release. No standard ACS 1-year release exists for 2000-2004. |
| ACS 5-year Detailed Tables | Periods 2005-2009 through 2020-2024 (end years 2009-2024) | Down to Census block groups where Census publishes the product | No standard 5-year ACS period ending before 2009. |

The current project loader covers a 2021-2024, state/county, 5-year Detailed Table scope. Pre-2022 files use a different source format in that loader and need a separate adapter/build decision. This matrix specifies the target; it does not change the active job.

Official availability references:

- [Census ACS 1-year API catalog](https://www.census.gov/data/developers/data-sets/acs-1year.html)
- [Census ACS 5-year API catalog](https://www.census.gov/data/developers/data-sets/acs-5year.html)
- [Census ACS data tools and product availability](https://www.census.gov/programs-surveys/acs/data/data-tools-chart.html)

## Change semantics

| Measure | Valid operands | Formula | Do not do this |
|---|---|---|---|
| Year-over-year | Adjacent available standard 1-year releases of the same comparable measure and geography | `new - old`; percent change is `(new - old) / old * 100` when old is nonzero | Do not create a 2020 value or label 2021 versus 2019 as year-over-year. |
| Five-year change | Two non-overlapping standard 5-year periods that end five years apart, such as 2015-2019 and 2020-2024 | `new - old`; percent change is `(new - old) / old * 100` when old is nonzero | Do not compare adjacent rolling 5-year releases such as 2019-2023 and 2020-2024 as independent five-year change. |

The change result must retain both estimates and both margins of error. Before reporting a difference as meaningful, the implementation must apply Census comparison guidance and the published confidence level; it must not hide uncertainty behind one number.

## Required build sequence

1. Inventory official product/year availability, table manifests, format changes, eligible geographies, and capacity for 1-year releases 2005-2024 and 5-year releases ending 2009-2020.
2. Write a bounded source/build spec that selects the initial geography and table scope, maps the source format, and proves artifact, resume, idempotency, field, and coverage behavior.
3. Build and verify 1-year ingestion separately from the existing 5-year path; do not overload a 5-year artifact or field as a 1-year value.
4. Add a reviewed comparison layer only after comparable-variable mappings and statistical handling are tested.
5. Audit each non-ACS source against the same earliest-year, continuous-span, gap, and comparability fields before authorizing its historical backfill.
