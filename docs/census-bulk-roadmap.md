# Census bulk package roadmap

## Objective

Make the browser a clear control plane for loading authoritative Census bulk
products into PostgreSQL. The normal path is deliberately short:

```text
package → preview → approve → download → stage → load → query
```

The browser presents packages, not raw FTP directory listings. Every package
shows its scope, source URLs, format, dependencies, capacity estimate, and
current lifecycle state. Advanced table/file selection remains separate and
never changes the meaning of a package.

## Shared lifecycle

Every adapter must use the same states and evidence boundaries:

| State | Meaning |
|---|---|
| `cataloged` | Official package metadata is visible; no data is acquired. |
| `draft` | An explicit plan names files and the intended canonical scope. |
| `previewed` | Published file sizes, disk projection, and source URLs are recorded. |
| `approved` | An operator approves exact files and load scope. |
| `downloaded` | Immutable artifacts and checksums are registered. |
| `staged` | Format-specific source rows are parsed without altering canonical facts. |
| `loaded` | Validated canonical tables reference immutable source artifacts. |

No loader may treat a provider ZIP as canonical data. Raw artifacts, staging
tables, and analytical tables remain separately owned and queryable.

## Package families and order

1. **ACS 5-year Summary File — complete release package** (implemented through
   catalog and preview): yearly Detailed Table archive, geography file, and
   table shells. It is the reference implementation for explicit bulk plans.
2. **County Business Patterns (CBP)** (loaded and verified for 2023): one current-year bundle with
   county, state, U.S., CBSA/MSA, ZIP, and reference artifacts. The source is
   CSV-in-ZIP and maps naturally to a typed business-statistics fact table.
3. **Population Estimates Program (PEP)** (loaded and verified for 2025): one package per published vintage.
   Do not mix vintages; raw CSV releases are revised annually and retain
   `release_vintage` on every canonical estimate. The normal package contains
   national, state, and county totals; it does not imply that every PEP product
   has been loaded.
4. **2020 Decennial DHC** (cataloged and capacity-previewed): product-specific
   package selection. The complete national archive is 2.29 GB compressed and
   projects to 9.14 GB staged; it remains download-disabled until the loader can
   join geographic headers and segmented files with `LOGRECNO`. It is not an
   ACS-compatible table loader.
5. **TIGER/Line** (loaded and verified for 2020 national core layers):
   geography layer packages by vintage. These load into spatial staging and
   `core.geography_boundary`, never measurement facts. The verified core load
   contains 38,020 artifact-linked boundaries: state, county, CBSA, and ZCTA.
   Tract, block-group, and block packages remain deliberately separate, rather
   than hidden inside a monolithic national download.

## CBP first-milestone acceptance criteria

- Browser exposes a single named 2023 CBP complete package and its component
  source artifacts, without a raw-file chooser.
- Preview records published size for every artifact and calculates stage,
  database, and reserve requirements.
- Approval requires an explicit geography/industry scope and does not silently
  promote all source rows to canonical data.
- Download is resumable, checksum-registered, and reports progress per artifact.
- Staging retains the source schema; the canonical loader is idempotent and
  records the source artifact for every loaded fact.
- At least one county-level analytical query is documented and validated against
  source rows.

The verified 2023 load contains 1,461,327 typed facts from three registered
artifacts. For example, a county analyst can start with:

```sql
SELECT geography.geoid, business.naics, business.establishments, business.employment
FROM fact.business_pattern AS business
JOIN core.geography AS geography ON geography.geography_id = business.geography_id
WHERE business.release_year = 2023
  AND geography.geography_type = 'county'
  AND business.naics = '00'
ORDER BY geography.geoid;
```

## PEP checkpoint

The browser exposes a single PEP release vintage, and `P` writes the same
review-only plan as `research-db ingest pep-bulk-plan`. The 2025 package was
previewed, explicitly approved for nation/state/county, checksum-registered,
staged as 3,248 source rows, and loaded as 19,488 annual estimates for
2020–2025. Each fact retains the source artifact, source ordinal, and release
vintage, so a later PEP release cannot silently replace the prior one.

## Design constraints

- Keep source-specific parsing inside provider adapters; the browser only
  coordinates packages and lifecycle state.
- Prefer a complete package plus explicit canonical filters over a growing list
  of special-case download toggles.
- Require documented handling for revised vintages, deleted files, and changed
  schemas before an adapter is promoted beyond preview.
- Show phase, completed/total, elapsed time, remaining time when meaningful,
  resume location, and actionable failure messages for download/stage/load jobs.
