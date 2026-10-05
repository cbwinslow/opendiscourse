# Jurisdiction-time model

Companion to `SPEC.md` (district-linked context). Source: operator-supplied
ChatGPT research, 2026-10-05. The data backlog is `inventory/dataset-roadmap.yaml`.
Facts about publishers are unverified until each source's story checks them.

## 1. Principle

A member holds a **post** that represents a **division**. A division is a
political identity and persists across redistricting. Each division has one or
more official **boundary vintages**. Observations stay on their native
geography. A controlled **crosswalk** projects them onto the division for the
period studied. Nothing is assigned to a ZIP, and a boundary is never used for
a period it did not exist.

Keeps ADR-0002 (division is not a polygon) and extends it; no redesign.

## 2. Who represents what

| Office | Geography | `geography_type` |
|---|---|---|
| President | nation | nation |
| U.S. Senator, Governor, statewide officials | state | state |
| U.S. Representative | congressional district | congressional_district |
| State senator | upper chamber district | sldu |
| State representative/delegate | lower chamber district | sldl |
| County official | county or county district | county / local_division |
| Mayor | place | place |
| Council member | ward | local_division |
| School board | school district | school_district |
| At-large | the whole jurisdiction | parent jurisdiction |

New `core.geography` types needed: congressional_district, sldu, sldl, tract,
block_group, block, puma, vtd, place, school_district, aiannh, local_division
(present: nation, state, county, cbsa, zcta).

## 3. Two new relations

**`core.division_boundary`**: `division_id`, `boundary_id`, `valid_from`,
`valid_to`, `relationship_kind`, `source_artifact_id`, `certification_status`,
`notes`. One division maps to many vintages over time; never one geography per
division. Example: VA-06 maps to the 119th-Congress polygon from 2025-01-03 to
2027-01-03, then to the next. `VA-06` alone is never a sufficient key: use
division + Congress + boundary vintage + validity dates.

**`core.geography_crosswalk`**: `from_geography_id`, `to_geography_id`,
`from_vintage`, `to_vintage`, `weight_type`, `weight`, `numerator`,
`denominator`, `method`, `coverage_ratio`, `quality_flag`, `valid_from`,
`valid_to`, `source_dataset_id`, `source_artifact_id`. `weight_type` is required
and matches the measure: population, housing_unit, household, employment, area,
address_ratio. One generic area-overlap percentage is not allowed for
population, housing, or employment measures. Weights come from Census
relationship files, block equivalency files, and block-level LODES/decennial
counts; do not hand-roll them (resolved-questions §6).

Supersedes the earlier non-goal "no `core.geography_relationship` until the
first longitudinal mart": the `district_year` mart is that mart (resolved-questions §6 trigger met by this spec).

## 4. Source selection hierarchy

1. Direct observation at the exact political geography (ACS district tables,
   CBP, IRS congressional, USAspending, FCC).
2. Exact aggregation from contained atomic geography (LODES blocks, tracts).
3. Weighted crosswalk (population, housing, or employment weights).
4. Spatial interpolation.
5. ZIP approximation, always labelled.

Every derived value records `aggregation_method`, `native_geography_type`,
`native_geography_vintage`, `crosswalk_id`, `coverage_ratio`, `quality_flag`.

## 5. Period semantics

An ACS 5-year release is a window (2024 release = 2020-2024), not a year.
Store `release_year`, `period_start`, `period_end`, `survey_window_years`.
Never subtract adjacent 5-year releases as independent observations. PUMS is
PUMA microdata and reaches a district only through a labelled synthetic
crosswalk with standard error and coverage. AHS is not a district source.

## 6. Coverage denominators

Crime (voluntary FBI reporting) and any survey-based measure store coverage
next to the value: reporting_agencies, eligible_agencies, months_reported,
population_covered, population_total, coverage_ratio. A rate without its
coverage ratio is refused. An agency's counts are never assigned to the district
holding its headquarters.

## 7. Derived metric table

`analytics.jurisdiction_metric` (name subject to ADR): `division_id`,
`period_start`, `period_end`, `metric_id`, `value`, `numerator`, `denominator`,
`standard_error`, `margin_of_error`, bounds, `source_dataset_id`,
`source_artifact_id`, native geography and vintage, `aggregation_method`,
`crosswalk_id`, `coverage_ratio`, `quality_flag`, `calculated_at`,
`calculation_version`. Metrics attach to division-periods, never copied onto
people. `member_jurisdiction_metric` is a view over metric, division, post,
membership, person. Lives in `mart`/derived schema; follows AD rules (dbt owns
`mart`). Raw ACS stays whole; a versioned semantic metric registry selects
curated metrics (groups in the roadmap's `census.acs_5.metric_pack`).

First gold table: `congressional_district_year` (population, CVAP, income,
poverty, employment, establishments, payroll, housing cost, federal awards,
requested funding, election margin, turnout), built after roadmap stages 1-10.

## 8. Three kinds of performance (project law)

Kept as separate analyses, never blended into one number:

1. **Legislative effectiveness**: what the member did inside the institution
   (sponsored bills by significance and stage reached, committee action,
   passage, laws enacted, amendments, cosponsorship, votes, requested funding).
   Method: reproduce a Legislative Effectiveness Score-style metric
   (5 stages x 3 significance classes, normalized to the chamber) rather than
   invent a formula. This is a scorecard: reserved CAP-9, its own spec first.
2. **Constituency outcomes**: what happened in the represented place
   (this spec).
3. **Causal impact**: evidence that the member or a policy caused a change.
   Separate, later; recessions and disasters are controls, not verdicts.

No metric here asserts 1 caused 2.

## 9. Warehouse culture

Source, immutable artifact, source-shaped staging, validation report,
canonical observation, derived crosswalk, analytic metric. Election results are
validated against official state results and an independent dataset before
use. Matches Redistricting Data Hub practice.
