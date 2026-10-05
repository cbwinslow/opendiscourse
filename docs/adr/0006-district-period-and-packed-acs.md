# ADR-0006: Jurisdiction-time geography and packed ACS district facts

- Status: Accepted
- Date: 2026-10-05
- Spine: AD-11 in `_bmad-output/planning-artifacts/architecture/architecture-opendiscourse-2026-09-14/ARCHITECTURE-SPINE.md`
- Spec: `_bmad-output/specs/spec-district-linked-context/SPEC.md`
- Execution: `_bmad-output/specs/spec-district-linked-context/stories.yaml`
- Geography calendar: `inventory/geography-vintages.yaml`

## Context

OpenDiscourse already has the correct political identity path:

```text
person -> membership -> post -> division
```

and the correct spatial evidence primitive:

```text
core.geography -> core.geography_boundary
```

but the two paths are not linked. The current TIGER loader publishes only
state/county/CBSA/ZCTA boundaries and the current ACS bulk loader promotes only
state/county rows. The retained 2024 ACS 5-year table files already contain
119th-Congress district observations, so the first useful district research
slice can be built without downloading another ACS copy.

The existing `fact.acs_bulk_estimate` is a scalar EAV-like layout: one row per
estimate or margin-of-error field. It is about 280 million rows / 105 GB on the
operator warehouse. A measured packed prototype reduced storage from roughly
375 bytes per scalar fact to roughly 9.3 bytes per scalar value by storing one
row per release x geography x table and arrays of values. ADR-0003 also requires
new large natural-slice facts to be partitioned from creation.

Census political/statistical geography is time-dependent. In particular, the
2024 ACS uses 119th Congressional District boundaries, while 2021 ACS uses
116th boundaries rather than 117th. A row labelled only `VA-06` or only
`release_year=2024` is therefore insufficient unless the boundary/period
contract is explicit.

## Decision

### 1. Political division identity and boundary evidence remain separate

`core.division` remains the Open Civic Data political identity. It does not
gain a `geography_id` column.

Add `core.division_boundary` in Story 10.3:

| Column | Contract |
| --- | --- |
| `division_boundary_id uuid` | internal PK |
| `division_id uuid` | FK to `core.division`, required |
| `boundary_id uuid` | FK to `core.geography_boundary`, required |
| `valid_from date` / `valid_to date` | represented-area validity; half-open interval in application logic |
| `congress integer` | nullable; set for U.S. congressional districts |
| `legislative_year integer` | nullable; set for Census SLD collections |
| `relationship_kind text` | reviewed classification such as `legal_boundary` |
| `source_artifact_id uuid` | required immutable evidence for the association |
| `metadata jsonb` | source-specific details, not identity |

Required checks/indexes:

- unique `(division_id, boundary_id)`;
- `valid_to IS NULL OR valid_from IS NULL OR valid_from < valid_to`;
- index `(division_id, valid_from, valid_to)`;
- index `(congress)` where non-null;
- no name-based population and no direct division -> geography FK.

Do not add a global no-overlap exclusion constraint in this story. Boundary
overlaps are validated by loader/tests because historical/publisher corrections
need to remain representable as evidence before resolution.

### 2. Cross-geography relationships and allocation weights are explicit

Add `core.geography_crosswalk` in Story 10.3:

| Column | Contract |
| --- | --- |
| `geography_crosswalk_id uuid` | internal PK |
| `from_geography_id uuid` / `to_geography_id uuid` | required geography identities |
| `from_vintage integer` / `to_vintage integer` | required source/target geography vintages |
| `method text` | e.g. relationship, block_assignment, population_weighted, employment_weighted |
| `weight_type text` | required: `none`, `assignment`, `population`, `housing_unit`, `household`, `employment`, `area`, `address_ratio` |
| `weight double precision` | nullable only for an unweighted relationship |
| `numerator double precision` / `denominator double precision` | retained when the weight is computed from a measure |
| `coverage_ratio double precision` | nullable 0..1 quality/coverage denominator |
| `quality_flag text` | reviewed quality state |
| `valid_from date` / `valid_to date` | optional relationship validity |
| `source_dataset_id text` | required catalog dataset id |
| `source_artifact_id uuid` | required immutable evidence |
| `source_ordinal bigint` | source row/member ordinal when applicable |
| `metadata jsonb` | source-specific fields |

Rules:

- a Census relationship-file overlap row uses `weight_type=none` unless the
  publisher explicitly defines a usable weighting measure;
- a BEF block assignment is `method=block_assignment`; it is a whole-block
  tabulation assignment and is not legal split-block polygon truth;
- population/housing/employment weights require an appropriate official atomic
  statistic and preserve that evidence;
- `weight` and `coverage_ratio` must be within [0,1] when present;
- a weighted row requires non-null weight; an unweighted relationship does not
  invent one;
- duplicate source relation rows are prevented by an evidence/natural-key
  unique constraint.

### 3. Packed ACS becomes the new canonical bulk-table representation

Create a source-specific field dictionary and packed fact table.

#### `catalog.acs_table_field`

One row describes one logical value position within an ACS Detailed Table for
one release:

| Column | Contract |
| --- | --- |
| `release_year smallint` | ACS release year |
| `table_id text` | Detailed Table id |
| `ordinal smallint` | zero-based packed-array position |
| `estimate_field_id text` | Census estimate variable id |
| `moe_field_id text` | corresponding Census MOE variable id |
| `label text` | official label where published |
| `concept text` / `universe text` | official metadata where published |
| `source_artifact_id uuid` | retained table-shell/metadata evidence |
| `metadata jsonb` | remaining provider metadata |

Primary key: `(release_year, table_id, ordinal)`.
Also require uniqueness of estimate/MOE field ids within a release/table.

This table is a compact field dictionary, not a replacement for the general
Census catalog. Raw metadata remains retained.

#### `fact.acs_table_row`

One row represents one ACS Detailed Table for one geography in one release:

| Column | Contract |
| --- | --- |
| `release_year smallint` | partition key |
| `period_start date` / `period_end date` | complete survey window |
| `survey_window_years smallint` | 5 for this source path |
| `geography_id uuid` | FK to `core.geography` |
| `boundary_id uuid` | nullable FK to exact `core.geography_boundary`; required by the loader for CD/SLDU/SLDL |
| `table_id text` | ACS Detailed Table id |
| `estimates double precision[]` | values in dictionary ordinal order |
| `margins_of_error double precision[]` | MOEs in the same order |
| `source_artifact_id uuid` | retained Detailed Table artifact |
| `source_ordinal bigint` | source row ordinal |
| `loaded_at timestamptz` | operational timestamp |

Rules:

- LIST partition by `release_year` from creation, per ADR-0003;
- first production partition is **2024 only**;
- unique canonical key is `(release_year, geography_id, table_id)`;
- estimates and MOE arrays have equal positive cardinality;
- dictionary cardinality must equal array cardinality (loader validation + DB
  reconciliation query);
- arrays use PostgreSQL double precision, not `numeric[]`; the immutable source
  preserves original text/precision and the packed table is a derived analytical
  representation;
- unavailable/suppressed cells remain SQL NULL and source suppression evidence
  stays in retained/staged source rows;
- political rows must resolve to the boundary required by
  `inventory/geography-vintages.yaml`; a wrong or missing political boundary
  fails the load.

### 4. Observation period is not a fake calendar year

For 2024 ACS 5-year facts:

```text
release_year = 2024
period_start = 2020-01-01
period_end = 2024-12-31
survey_window_years = 5
Congressional District boundary = 119th Congress / TIGER 2024 vintage
```

Adjacent ACS 5-year releases may be displayed as releases but are not treated
as independent annual changes. The first mart is therefore named
`mart.congressional_district_period`, not `district_year`.

### 5. First vertical slice is deliberately narrow

Stories 10.2-10.6 prove only:

1. 119th Congressional District + 2024 SLD boundary acquisition support;
2. division -> 119th CD boundary resolution;
3. 2024 ACS 5-year **congressional-district** packed facts from already-retained
   artifacts;
4. a bounded semantic metric registry;
5. `mart.congressional_district_period` with member/evidence drill-through.

National tract/block-group/block downloads are not prerequisites. A BEF or
relationship loader may create the minimum geography identity rows needed for
its own evidence without acquiring national block polygons.

### 6. Compatibility and retirement

`fact.acs_bulk_estimate` is not dropped by the schema-creation migration.

Retirement sequence:

1. create new dictionary + packed partitioned table;
2. load/reconcile the bounded 2024 CD slice;
3. prove field-level equality for sampled and aggregate counts against retained
   source and, where overlapping, existing scalar facts;
4. widen release/geography scope only through later stories;
5. after all desired old scalar scope is reproducibly represented, record an
   explicit retirement decision and use a separate reversible migration for
   dropping/deprecating derived scalar rows.

No retained Census artifact is deleted or overwritten.

The field-level compatibility surface is a **dbt/read-only view**, not another
Alembic-owned scalar fact table. dbt unnests arrays using
`catalog.acs_table_field.ordinal` when a row-per-variable interface is needed.

## Alembic implementation plan

Story 10.2/10.3/10.4 migrations are additive and independently reversible:

1. **Geography/junction revision:** add `core.division_boundary` and
   `core.geography_crosswalk`; no rewrite of `core.division` or existing
   `core.geography_boundary`.
2. **ACS packed revision:** add `catalog.acs_table_field` and partitioned
   `fact.acs_table_row`, plus only the 2024 partition initially.
3. Update SQLAlchemy table mappings and `models/__init__.py` in the same
   revision/story that owns each table.
4. Downgrade drops only newly added tables/partitions/indexes; it never touches
   `fact.acs_bulk_estimate` or retained artifacts.
5. A later retirement revision is forbidden until reconciliation evidence is
   written to `docs/PROJECT-STATE.md`/run ledger.

Runtime SQL for bulk promotion lives under `sql/query/census/`, not nested
multiline SQL in Python.

## Required tests

Before a story is complete:

- schema upgrade/downgrade/re-upgrade;
- duplicate division-boundary rejection;
- wrong-vintage political boundary rejection;
- crosswalk weighted/unweighted CHECK behavior;
- source-less junction/fact rejection;
- packed array cardinality/dictionary mismatch rejection by loader validation;
- 2024 CD rerun idempotency;
- killed stage/load resume equals clean load;
- source row count and field count reconciliation;
- sampled scalar-vs-packed value/MOE equality;
- dbt mart uniqueness for division x boundary vintage x period;
- no display-name join in member -> district path.

## Alternatives considered

| Option | Decision |
| --- | --- |
| Put `geography_id` directly on `core.division` | Rejected: collapses redistricting history. |
| Use ZIP/ZCTA as district identity | Rejected: postal/statistical ZIP areas are not political districts. |
| Keep expanding `fact.acs_bulk_estimate` | Rejected for new scope: measured storage/index overhead is excessive. |
| JSONB per ACS row | Rejected as canonical analytics representation: repeats field names and recreates the PUMS staging width problem. |
| One generic area-overlap weight | Rejected: population, housing, employment and address allocation mean different things. |
| Download national block geometry first | Rejected for the first slice: high cost and unnecessary for direct 119th ACS district facts. |
| Replace Postgres with Parquet/DuckDB for the packed facts | Rejected by ADR-0001; those remain derived exports. |

## Consequences

- Story 10.2 can focus on a small political-boundary package instead of a
  national TIGER expansion.
- Story 10.4 can reuse the 2024 ACS bytes already retained.
- Historical district analysis becomes explicit rather than silently attaching
  current boundaries.
- Later LODES/HMDA/health/election sources can reuse one typed crosswalk model.
- The packed representation is source-specific enough to be efficient while the
  mart/metric layer stays source-agnostic.
