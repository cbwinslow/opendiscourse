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

1. **ACS 5-year Summary File — reviewed Detailed Table packages** (state/county
   loader implemented, now loaded comprehensively across 2021-2024 -- see
   "Comprehensive ACS scope" below): the browser offers `Housing Core` as
   seven reviewed Detailed Tables, and `research-db ingest acs-bulk-plan`
   plus `relevant_acs_tables()` cover the full ~600-615 table/year scope. It
   stages source rows and loads estimates/MOEs with artifact lineage.
   Complete release packages remain preview/download-only until their
   distinct archive parser and scope contract are reviewed.
2. **County Business Patterns (CBP)** (loaded and verified for every
   published year, 2009-2023, one plan per release year): county, state,
   U.S., CBSA/MSA, ZIP, and reference artifacts per year. The source is
   CSV-in-ZIP and maps naturally to a typed business-statistics fact table.
3. **Population Estimates Program (PEP)** (loaded and verified for both
   published vintage series, 2010-2020 and 2020-2025): one package per
   published vintage. Do not mix vintages; raw CSV releases are revised
   annually and retain `release_vintage` on every canonical estimate. The
   normal package contains national, state, and county totals; it does not
   imply that every PEP product has been loaded.
4. **2020 Decennial DHC** (loaded and verified for a deliberate analytical
   scope): product-specific package selection. The complete national archive is
   2.29 GB compressed. GEO records and selected numbered segments join through
   `LOGRECNO`, using the official table matrix to map variables to source
   columns. The verified state/county H1 and P1 load contains 22,758
   artifact-linked values; additional DHC tables or summary levels require an
   explicit new approval rather than silently expanding the canonical scope.
5. **TIGER/Line** (loaded and verified across vintages 2016-2025):
   geography layer packages by vintage. These load into spatial staging and
   `core.geography_boundary`, never measurement facts. State/county/CBSA/ZCTA
   are covered for every vintage in range except TIGER2022, which Census
   never published a CBSA file for; ZCTA switches from the 2010-vintage
   naming/columns (`GEOID10`/`ZCTA5CE10`) to the 2020-vintage ones
   (`GEOID20`/`ZCTA5CE20`) starting with the 2020 release, and both vintages
   coexist that one transition year. Tract, block-group, and block packages
   remain deliberately separate, rather than hidden inside a monolithic
   national download.

## Comprehensive ACS scope (2026-08-07)

The original ACS Detailed Table selection excluded four narrow
administrative families (`B10`, `B13`, `B26`, `B29`) and, by default, the
entire `B25` housing family, on top of the always-excluded quality/flag
tables (`B98`/`B99`), collapsed `C`-prefix duplicates, and race/ethnicity
iteration variants (`^B\d{5}[A-Z]{1,2}$`). Given three concrete scope
options, an explicit decision was made to broaden the default to include
every Detailed Table except that fixed exclusion set — roughly 600-615
tables/year rather than ~410. `relevant_acs_tables(year)` in
`ingestion/census.py` implements this and is deliberately regenerable: it
reads that year's discovered `meta/acs/<year>/tables.json` manifest rather
than hand-listing table IDs, so a future year's release resolves the
equivalent expanded selection automatically. The exact rule, decision date,
and rationale are also registered in
`inventory/contracts/acscomprehensive.yaml` per this project's normal
source-registration workflow, even though the selection is too broad to
express as that file's static include/exclude ID list (the executable rule
lives in code; the contract file documents and points at it).

Because the original narrower load (2021/2022/2024 fully loaded, 2023
loading as of this writing) had already downloaded, staged, and loaded
~380-387 tables/year, expanding to the comprehensive scope was done as an
incremental **delta**, not a rebuild: `acs5-comprehensive-delta<year>.yaml`
plans contain only the net-new ~221-228 tables/year the original load
didn't already cover, built by diffing `relevant_acs_tables(year)` against
each year's already-loaded table list. This avoids re-downloading,
re-staging, or re-loading anything already present -- both `download()`
(skips existing files) and stage/load (`ON CONFLICT DO NOTHING`) are
idempotent, but there is no reason to pay their I/O cost twice when the
delta is known in advance.

A handful of Detailed Tables consistently return no reliable size from
Census's server (a HEAD, Range GET, and plain GET all fail to return
headers within a reasonable window) -- dominated by the `B24`
industry-by-occupation and `B27` health-insurance wide cross-tab families,
plus a fluctuating handful of others. This is a genuine, real server
behavior, not a probing bug: retrying the preview at least once (sometimes
twice) reliably resolves most of an initial spike, and the confirmed-
unresolvable set converges to the same small core (~29-30 tables) every
year despite very different initial unknown-size counts (2021 saw 30, 2022
saw 87 → 29, 2023 saw 60 → 29, 2024 saw 100 → 29). `ACS_SIZE_PROBE_UNRESOLVABLE`
in `ingestion/census.py` documents the confirmed set per year; extend it
only after a genuine retry, never on the first unknown-size result, and
never force-approve a plan with unresolved sizes.

## Repeatable refresh

`ops/census-bulk-refresh.sh <prefix> <plan-file> [--geography TYPES] [--workers N]`
drives one plan idempotently through
`preview -> approve -> download -> stage -> load -> census-health`,
reading the plan's own `state:` field and skipping whatever stages it has
already passed -- safe to re-run against a plan at any point (an
interrupted download, an already-loaded plan, a plan stuck mid-stage after
an earlier failure). `<prefix>` is one of `acs-bulk`, `cbp-bulk`,
`pep-bulk`, or `tiger-bulk`, matching each dataset's CLI command prefix.
`--workers` only takes effect for `acs-bulk` (the only loader with a
parallel/`ProcessPoolExecutor` path as of this session); it is silently a
no-op for the others.

For ACS plans specifically, the script also implements the retry-then-
exclude discipline described above: on an unapproved preview it retries
once, then checks whatever remains unresolved against
`ACS_SIZE_PROBE_UNRESOLVABLE` for that plan's release year. If every
remaining unresolved table is already documented there, it rebuilds the
plan without them and re-previews. If a genuinely new, undocumented
unresolved table appears, the script stops and asks for manual review
rather than ever force-approving an unknown size.

```bash
ops/census-bulk-refresh.sh acs-bulk meta/bulk-plans/acs5-comprehensive-delta2024.yaml --workers 6
ops/census-bulk-refresh.sh cbp-bulk meta/bulk-plans/cbp-cbp2015.yaml
```

Concurrency note: ACS-on-ACS runs across different years are safe to run
in parallel (its `core.geography` upsert is `ON CONFLICT DO NOTHING` and
scoped to each plan's own artifact IDs), but avoid overlapping a TIGER or
CBP load with anything else writing `core.geography` -- both loaders write
that shared table too, and two lock-contention incidents this session were
traced to exactly that kind of overlap combined with (now-fixed) missing
artifact scoping. When several plans must run back-to-back, prefer running
them one at a time rather than backgrounding all of them simultaneously.

## ACS Housing Core checkpoint

The first production ACS package is the 2024 5-year `Housing Core` selection:
`B25001`, `B25002`, `B25003`, `B25004`, `B25010`, `B25064`, and `B25077`.
Its reviewed preflight measured nine official artifacts (the seven tables plus
geography and table-shell evidence) at 263,760,889 bytes. The explicit
state/county approval staged 26,775 source rows and loaded 153,000 typed
estimate/MOE facts. All raw files retain SHA-256 checksums; every fact retains
its Detailed Table artifact and source row ordinal. `research-db census-health`
reports this package and the broader Census families as `healthy`.

The separate 2024 `Housing Extended` plan covers the other reviewed housing
tables: `B25034`, `B25035`, `B25070`, `B25071`, `B25075`, `B25081`, and
`B25093`. Its 463,508,537-byte preflight passed the same explicit state/county
scope, then staged 26,775 rows and loaded 680,850 facts. Together the two
plans provide all 14 reviewed ACS housing tables, 833,850 canonical facts,
3,274 state/county geographies, and 14 source Detailed Table artifacts.

The identical two-plan, state/county package was then verified for the 2023
ACS 5-year release: 833,850 facts across the same 14 reviewed tables and
3,274 geographies. The current verified housing baseline is therefore
1,667,700 artifact-linked facts across 2023 and 2024, with all four plans
reported `healthy`.

The final currently supported table-based release, 2022, was also loaded with
the same two reviewed plans: 152,920 Core facts and 680,494 Extended facts
(833,414 total). The 2022–2024 state/county housing baseline now has six
loaded plans, 2,501,114 artifact-linked facts, 14 reviewed tables per year,
and six health-verified artifact sets. Pre-2022 ACS uses a different source
format and remains a separate adapter/project rather than an undocumented
extension of this loader.

An analyst can start with total housing units (`B25001_E001`) like this:

```sql
SELECT geography.geography_type, geography.geoid, estimate.value AS housing_units
FROM fact.acs_bulk_estimate AS estimate
JOIN core.geography AS geography USING (geography_id)
WHERE estimate.release_year = 2024
  AND estimate.table_id = 'B25001'
  AND estimate.field_id = 'B25001_E001'
  AND estimate.measure = 'estimate'
ORDER BY geography.geography_type, geography.geoid;
```

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

Run the read-only operational report before a refresh or any new bulk approval:

```bash
research-db census-health
```

It writes `meta/health/census.json` and classifies each Census family as
`healthy`, `attention`, `failed`, or `unknown`. A family is only `healthy` when
the plan's expected artifacts are registered, canonical rows retain artifact
lineage, and the plan's approved scope is actually loaded. ACS is only healthy
when selected Detailed Table facts are linked to all expected downloaded
artifacts; a cataloged package or ZIP alone is not a health signal.

## ACS Housing Core workflow

Open a 2022-or-later ACS Detailed Table release in the browser. Press `H`
twice to add the seven reviewed Housing Core tables or `J` twice to add the
seven complementary Housing Extended tables. The packages are defined in
`inventory/acs_housing_groups.yaml`, so they are visible and reviewable outside
the TUI. Press `P` to write a plan, then follow the normal lifecycle:

```bash
research-db ingest acs-bulk-preview --plan meta/bulk-plans/acs5-<selection>.yaml
research-db ingest acs-bulk-approve --plan meta/bulk-plans/acs5-<selection>.yaml --geography state --geography county
research-db ingest acs-bulk-download --plan meta/bulk-plans/acs5-<selection>.yaml
research-db ingest acs-bulk-stage --plan meta/bulk-plans/acs5-<selection>.yaml
research-db ingest acs-bulk-load --plan meta/bulk-plans/acs5-<selection>.yaml
research-db census-health
```

The `H` and `J` shortcuts only change a persistent selection; neither downloads data.

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

Those integration tests generate minimal ACS, CBP, PEP, DHC, and TIGER source
fixtures locally, run the real stage/load functions twice, and assert that
artifact-linked fact rows are not duplicated. They never contact Census or use
production artifacts.

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
