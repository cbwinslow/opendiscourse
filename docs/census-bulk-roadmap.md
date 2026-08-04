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
4. **2020 Decennial DHC** (loaded and verified for a deliberate analytical
   scope): product-specific package selection. The complete national archive is
   2.29 GB compressed. GEO records and selected numbered segments join through
   `LOGRECNO`, using the official table matrix to map variables to source
   columns. The verified state/county H1 and P1 load contains 22,758
   artifact-linked values; additional DHC tables or summary levels require an
   explicit new approval rather than silently expanding the canonical scope.
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

## DHC checkpoint

The verified 2020 DHC plan downloads the complete national archive together
with Census's table matrix, selects summary levels `040` and `050`, and selects
tables `H1` and `P1`. It stages 11,379 GEO records, then records both the
source segment/member and source row ordinal for every canonical value. The
Alabama state totals validate directly against the published segments:
`H0010001 = 2,288,330` and `P0010001 = 5,024,279`.

```sql
SELECT geography.geoid, value.table_id, value.variable_id, value.value
FROM fact.decennial_dhc_value AS value
JOIN core.geography AS geography ON geography.geography_id = value.geography_id
WHERE geography.geography_type = 'county'
  AND value.table_id IN ('H1', 'P1')
ORDER BY geography.geoid, value.table_id;
```

## Design constraints

- Keep source-specific parsing inside provider adapters; the browser only
  coordinates packages and lifecycle state.
- Prefer a complete package plus explicit canonical filters over a growing list
  of special-case download toggles.
- Require documented handling for revised vintages, deleted files, and changed
  schemas before an adapter is promoted beyond preview.
- Show phase, completed/total, elapsed time, remaining time when meaningful,
  resume location, and actionable failure messages for download/stage/load jobs.

## Operational verification and regression tests

Run the deterministic contract tests before changing a package builder, a
scope gate, or DHC's table-matrix interpretation:

```bash
uv run --extra ingest python -m unittest tests.test_census_bulk -v
```

The test suite uses only generated local fixtures. It proves that a package
cannot mix releases/vintages, approval cannot bypass a successful preview,
unsupported canonical scopes fail before a load, and table-matrix offsets do
not shift when an earlier DHC table is not selected.

For database stage/load idempotence, use a disposable PostgreSQL database; the
test refuses to run unless its URL is explicitly supplied:

```bash
OPENDISCOURSE_TEST_DATABASE_URL='postgresql:///opendiscourse_test?port=5434' \
  uv run --extra ingest --extra spatial python -m unittest tests.test_census_bulk_integration -v
```

Those integration tests generate a minimal CBP ZIP and PEP CSV locally, run
the real stage/load functions twice, and assert that artifact-linked fact rows
are not duplicated. They never contact Census or use production artifacts.

After a real bulk lifecycle, verify lineage and idempotent coverage in the
database. Counts will grow as additional approved scopes are loaded; every
canonical row must remain linked to an artifact:

```sql
SELECT 'cbp' AS family, count(*) AS rows, count(source_artifact_id) AS linked
FROM fact.business_pattern
UNION ALL
SELECT 'pep', count(*), count(source_artifact_id)
FROM fact.population_estimate
UNION ALL
SELECT 'dhc', count(*), count(source_artifact_id)
FROM fact.decennial_dhc_value
UNION ALL
SELECT 'tiger', count(*), count(source_artifact_id)
FROM core.geography_boundary;
```

For recovery, rerun the same lifecycle command only from the plan's current
state: a `.part` artifact resumes download; `downloaded` permits staging;
`staged` permits canonical loading. Do not edit a loaded plan to widen its
scope—write, preview, and approve a new plan so the expanded evidence remains
separately auditable.
