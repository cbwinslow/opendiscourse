---
id: SPEC-longitudinal-source-coverage
companions:
  - acs-release-matrix.md
  - ../spec-source-completion/SPEC.md
  - ../../spec-opendiscourse/SPEC.md
sources:
  - ../../../inventory/contracts/acscomprehensive.yaml
  - ../../../docs/PROJECT-STATE.md
---

> **Canonical contract.** This SPEC defines the longitudinal-coverage target and the limits on comparable time-series analysis. It does not authorize acquisition until a source-specific build spec and capacity approval exist.

# Longitudinal source coverage and annual ACS estimates

## Why

Researchers need enough official history to see both short-term movement and longer-term change. OpenDiscourse will maximize each source's annual history toward calendar year 2000 where the original publisher offers an equivalent product, while making unavailable years and non-comparable releases explicit rather than manufacturing continuity.

## Capabilities

- **CAP-1**
  - **intent:** An analyst can use every available standard ACS 1-year release from 2005 through 2024, with the unavailable 2020 release explicitly represented.
  - **success:** A release inventory records the official source, coverage, geography eligibility, table/variable manifest, artifact checksum, and ingest run for every acquired 1-year release; it contains no standard 2020 1-year estimate.

- **CAP-2**
  - **intent:** An analyst can use every available standard ACS 5-year release ending 2009 through 2024, independently from the 1-year product.
  - **success:** A release inventory distinguishes each five-year collection period, including 2005-2009 through 2020-2024, and preserves the product and period alongside each estimate.

- **CAP-3**
  - **intent:** An analyst can calculate transparent year-over-year and five-year changes from comparable ACS estimates.
  - **success:** A reproducible query or mart returns the old value, new value, absolute change, percent change when the old value is nonzero, both margins of error, product, collection periods, and a comparison-status reason; it refuses or labels an incompatible comparison.

- **CAP-4**
  - **intent:** The operator can plan historical expansion for every source without pretending all sources can reach 2000.
  - **success:** The source-completion matrix records, for each active source, its earliest equivalent official release, continuous annual span, known publisher gaps, geography limits, and the next source-specific spec required before acquisition.

## Constraints

- Standard ACS 1-year and 5-year estimates are different Census products. They remain separately identified and are never silently combined, substituted, or used as one another's baseline.
- A year-over-year change compares adjacent available 1-year releases only. The lack of a standard 2020 1-year release creates an explicit break between 2019 and 2021, not a year-over-year value.
- A standard five-year change compares non-overlapping five-year periods with end years five years apart, such as 2015-2019 versus 2020-2024. Adjacent rolling 5-year releases overlap and are not independent five-year changes.
- Every comparison must match product, geography, table/variable, measure, universe, and documented methodology. A table or variable change blocks automatic calculation until a reviewed compatibility mapping exists.
- Acquisition uses original publisher bytes, capacity approval, immutable artifact checksums, an ingest run, and idempotent resume behavior. The active 2021-2024 ACS 5-year delta load is not interrupted or broadened by this specification.
- “Back to 2000” is a target, not a license to substitute a different Census product. The 2000 Census long form and Census 2000 Supplementary Survey require separate compatibility review before any use alongside ACS.

## Non-goals

- This does not acquire ACS 1-year files, create a schema migration, or expand geography before a bounded build spec, capacity estimate, and field checklist are approved.
- This does not use experimental 2020 ACS 1-year estimates as standard ACS data.
- This does not claim that every OpenDiscourse source has year-2000 coverage; each source needs an official-availability audit and source-specific plan.
- This does not treat an average of five annual estimates as a 5-year ACS estimate or as a five-year change.

## Success signal

For an eligible ACS geography and variable, a researcher can inspect official annual 1-year values, official 5-year period estimates, and clearly labelled year-over-year or non-overlapping five-year changes with their original evidence and limits. The source queue separately shows how far each other source can extend toward 2000.

## Assumptions

- The current 2021-2024 ACS 5-year comprehensive delta is allowed to finish unchanged before the new annual-product work begins.

## Open Questions

- Which geography baseline should the first ACS 1-year build support: all Census-published 1-year eligible geographies, or a smaller state/county-first slice that can be expanded after capacity evidence?
- Should compatible changes be exposed first as a query/view or as a materialized mart after a research question defines refresh and performance needs?
