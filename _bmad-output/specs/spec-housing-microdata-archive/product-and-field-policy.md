# Product and field policy

## Archive scope

| Product | Retain in full | Time range | What it is for | Important limit |
|---|---|---|---|---|
| ACS PUMS 1-year | Current official U.S. and Puerto Rico housing/person CSV packages, dictionaries, release notes | 2005-2019; 2021-2024 | Annual household/person sample analysis | No standard 2020 release; PUMA is the finest published geography. |
| ACS PUMS 5-year | Current official U.S. and Puerto Rico housing/person CSV packages, dictionaries, release notes | Periods ending 2009-2024 | Small-area-period household/person sample analysis | A pooled five-year product, not a rollup of stored annual estimates. |
| AHS national PUF | Current official relational CSV, codebook, release notes, value labels, and sample documentation | Every published release from 2001 onward | Nationwide housing-unit condition and cost analysis | The publisher has no public-use 2000 release; survey fields and samples change, so preserve the release definition. |
| AHS metropolitan PUF | Current official relational CSV, codebook, release notes, value labels, and sample documentation | Every published release from 2001 onward where published | Metropolitan housing-unit analysis | The publisher has no public-use 2000 release. It is a separate survey component; do not double-count it with national rows. |

Initial official-index capacity measure: ACS PUMS is approximately 64.10 GiB compressed; the upper bound for all candidate AHS CSV PUF packages is 3.68 GiB compressed. The Connector must calculate exact bytes and projected extracted/stage/canonical/index size from its selected manifest before download.

## Field policy

| Policy domain | Retain raw source fields | Initial analytic coverage | Source boundary |
|---|---|---|---|
| Demographics | Yes | age, sex, race/ethnicity, disability, citizenship/nativity, language | ACS PUMS and tabulations |
| Income and poverty | Yes | household/family/person income, earnings, benefits, poverty, insurance | ACS PUMS and tabulations |
| Education and family | Yes | attainment, enrollment, marital status, relationship, household/family composition | ACS PUMS and tabulations |
| Housing | Yes | tenure, rent, gross rent, mortgage, property value, taxes, utilities, structure, rooms, year built, vacancy, affordability | ACS PUMS/tabulations and AHS |
| Housing quality | Yes | physical condition, repairs, neighborhood, financing, moving, detailed costs | AHS is the principal source; retain ACS housing fields too |
| Work and mobility | Yes | employment, occupation/industry, commute, vehicle availability, migration | ACS PUMS and tabulations |
| Crime | No invented ACS/AHS field | Future official crime source only | Separate source contract required |

Raw retention is the expansion mechanism, not the documentation itself. The field registry records every source variable, its versioned official definition, value labels, and the dictionary/codebook artifact that defined it; the first typed/mart layer promotes the policy-domain fields above. A later approved field is mapped from retained raw data, tested, and published without a repeat download.

## Product rules

- Use ACS 1-year for annual movement where it is published.
- Use ACS 5-year for the full geography and non-overlapping five-year comparisons.
- Use PUMS for custom estimates from public sample records; keep weights and margins-of-error methodology.
- Use AHS for housing-unit longitudinal and detailed-condition questions.
- Do not mix survey components, periods, geographies, or raw/flat duplicate representations without a documented transform.
- A release cannot publish until every selected data member has reconciled expected, parsed, inserted, duplicate, and rejected-row counts in the Connector-owned run ledger.
- A microdata projection keeps its source identity and geography vintage; malformed scalar conversion is visible as a recorded validation result, never an unexplained analytical null.
