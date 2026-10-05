---
id: SPEC-district-linked-context
status: approved (operator, 2026-10-05)
companions:
  - jurisdiction-time-model.md
  - stories.yaml
  - ../../../inventory/dataset-roadmap.yaml
  - ../../../inventory/geography-vintages.yaml
  - ../spec-political-research-marts/SPEC.md
  - ../spec-housing-microdata-archive/SPEC.md
  - ../../../docs/adr/0002-schema-invariants.md
---

# District-linked context data

## Why

The research question is how politicians' votes and policies affect the people they
represent. A representative maps to a place (congressional district, state legislative
district, state) and a party. The warehouse must therefore hold who lives there
(age, sex, race, education, income, children, citizenship, benefits), what happens
there (crime, immigration, employment, housing, tax), and how that place voted, all
joined to the member by geography and time, never by name.

## North star and first release

The programme is complete enough to expand only after one vertical slice is proven end to end:

```text
119th Congress member term
  -> OCD post/division
  -> official 119th TIGER boundary
  -> retained 2024 ACS 5-year district facts (2020-2024 window)
  -> reviewed semantic metrics
  -> mart.congressional_district_period
  -> source-evidence drill-through
```

The first release is deliberately **119th Congress + 2024 ACS 5-year**. Census
publishes the 2024 ACS on 119th-Congress boundaries, so this slice does not need
a cross-vintage approximation. One mart row is a division x boundary vintage x
observation period; it is not a fake "district-year" row. Story 10.6 is the
`slice_proven` gate. Until it passes, agents must finish this vertical slice
rather than adding CVAP, IRS, elections, crime, FEC, USAspending, or other
horizontal sources.

The authoritative 2021-2024 geography calendar is
`inventory/geography-vintages.yaml`. In particular, 2021 ACS congressional
district rows use the **116th**, not the 117th, district vintage.

## Measured facts (2026-10-05)

- Retained ACS 5-year table files (2021-2024, 111 GB) already contain every geography:
  440 congressional districts, 1,964 + 4,880 state legislative districts, 2,486 PUMAs,
  33,772 ZCTAs, 85,381 tracts, 242,296 block groups. The loader keeps only state+county.
  District data needs no new download for 2021-2024.
- `fact.acs_bulk_estimate` stores one row per number: 280 M rows, 105 GB, ~375 B per fact.
- Packed layout (one row per release x geography x table, `float8[]` estimate + margin
  arrays): measured 9.3 B per fact on real 2023 B01001 data (47,367 rows, 41 MB).
  Adding all seven levels above (excluding tract/block group), 4 releases, all tables
  is about 3.7 B facts: ~1.4 TB in the current layout, ~35 GB packed.
- Person-level PUMS: one California 2023 file, 55 typed columns, 231 B per person
  (current JSONB staging: ~1,760 B). Extrapolated all-years person+housing: ~200-250 GB
  versus 1.56 TB. Extrapolation, not a full measurement.
- Join path exists: `core.membership` (40,205 House terms since 1789) -> `core.post`
  -> `core.division` (OCD id with state and district). `core.geography` has no
  congressional-district, state-legislative or PUMA types yet.
- The database lives on the 2.9 TB workspace volume (1.4 TB free), not the root disk.

## Capabilities

- **CAP-1** A researcher can get demographic, income, education, housing, nativity and
  benefit measures for a member's district and term. Success: congressional-district,
  state-legislative-district, PUMA and ZCTA geographies load with Census boundary
  vintage recorded; a term resolves to exactly one district vintage via a reviewed
  Congress-to-vintage rule (ADR-0002 #8); cross-vintage comparison is refused.
- **CAP-2** ACS table facts are stored packed, with row-level evidence. Success:
  `(release, geography, table)` is the unique grain; each row retains
  `source_artifact_id` and `source_ordinal`; the existing
  `catalog.dataset_field` is extended/reused as the field dictionary and a
  field-order hash binds packed array positions to field ids/labels; a view
  unnests to one row per field for researchers; the loader
  reconciles parsed versus stored counts and is idempotent and resumable; the existing
  280 M facts are re-derived from retained files and compared before the old table is
  dropped (derived rows only; retained files are never touched).
- **CAP-3** Person-level ACS microdata is queryable at PUMA with typed columns.
  Success: a typed table (~55 analysis columns, integer types, weights kept) is proven on
  one year, then all 1-year files and the four non-overlapping 5-year windows load;
  replicate weights and imputation flags stay in retained ZIPs; every row carries
  artifact, member and ordinal; 1-year and 5-year stay separate products.
- **CAP-4** Topic sources join to members by geography. Success: each source is
  verified at its official endpoint (URL, terms/licence, size, coverage, schema)
  before a Connector is written; each declares its native geography and, where
  it does not match a district, an approved crosswalk with the allocation rule
  stated and uncertainty labelled. Build order and authorization come only from
  `stories.yaml` + `inventory/dataset-roadmap.yaml`: post-slice sources begin
  with CVAP, CBP congressional-district coverage, IRS SOI, LODES, USAspending
  and GAO CPF/CDS; elections/FBI/FEC remain behind Epic 7/person-join gates.
- **CAP-6** A member's division resolves to boundary vintages and observations
  project onto it by a recorded method. Success: `core.division_boundary` (division
  x vintage x validity dates) and `core.geography_crosswalk` (typed `weight_type`,
  coverage, method, evidence) exist; Census relationship files and block
  equivalency files load as their evidence; every derived value names its native
  geography, vintage, aggregation method and coverage ratio; the source selection
  hierarchy (direct, atomic aggregate, weighted crosswalk, interpolation, ZIP) is
  applied and ZIP is never a district key. Model: `jurisdiction-time-model.md`.
- **CAP-7** The dataset backlog is executable. Success: `inventory/dataset-roadmap.yaml`
  gives every source a stable id, native geography, rule, priority, stage, gate and
  status; a source moves out of `verified: false` only after its endpoint, licence,
  size and years are checked at the publisher; the first gold table
  `congressional_district_period` builds in Story 10.6 from the bounded 119th/2024 vertical slice with every column traceable.
- **CAP-8** Outcomes keep honest uncertainty. Success: ACS values carry release
  year and survey window and are never differenced across overlapping windows;
  voluntary-reporting data (FBI) stores coverage and refuses a rate without it;
  PUMS-derived district values are labelled synthetic with standard error.
- **CAP-5** Existing tables are audited for storage type. Success: a per-table report
  (measured bytes per row, wasted width, bloat) with proposed types; changes go through
  reversible Alembic revisions and are verified by row-count and checksum comparison.

## Constraints

- No name matching. Party comes from the member's term and election results, never from
  Census (Census has no party or voter-registration data).
- FEC and election person joins stay behind `identitygate.require_person_join`.
- Download -> inventory -> ingest from official endpoints into the user's DATA_ROOT.
- New sources are Connectors; no `cli.py` / `plans.py` branches.
- Wiping and reloading derived rows is authorised; each wipe is recorded in
  `docs/PROJECT-STATE.md` or the run ledger. Retained artifacts are never changed.
- The roadmap (`inventory/dataset-roadmap.yaml`) does not authorize ingest. Each row
  keeps its `gate`: `v1_spine` means only a currently-ready Epic 10 story
  may proceed; `slice_proven` waits for Story 10.6 (v1-scope.md);
  `epic7` (elections, crime, money) stays closed until Epic 7 opens;
  `person_join` needs BioGuide through `identitygate`.
- Direct district data beats crosswalking; ZCTA/ZIP is an escape hatch, labelled.
- Legislative-effectiveness and any member scorecard are CAP-9 (reserved); they need
  their own spec and stay separate from constituency outcomes and causal claims.
- Publisher facts in the roadmap came from a research summary and are unverified
  until each source's story checks them.
- Tract, block-group, block, VTD, place and school-district geometry are out of the first vertical slice. They open only after Story 10.6, with a capacity preview before any large national transfer.
- Puerto Rico microdata is deferred by operator decision (2026-10-05).

## Phases

0. **Geography calendar — done.** `inventory/geography-vintages.yaml` freezes the
   reviewed ACS/CD/SLD/PUMA vintages and the roles of TIGER, relationship files,
   and BEFs.
1. **Prove the 119th/2024 vertical slice.** Stories 10.1-10.6: ADR/schema,
   CD/SLD boundaries, division-to-boundary model, packed 2024 ACS CD facts,
   semantic metrics, then `mart.congressional_district_period`.
2. **Expand comparable Census coverage.** Only after Story 10.6: CVAP, CBP at
   its verified district vintage, then 118th and earlier district periods where
   geography equivalence is explicit. State legislative districts follow the
   same rule.
3. **Add atomic/crosswalk geography when a source needs it.** Tract, block
   group, block, VTD, place, school district and measure-specific weights are
   acquired under capacity review. PUMS remains PUMA-native and synthetic
   district estimates remain labelled.
4. **Add one topic source at a time.** IRS, LODES, USAspending, GAO CPF/CDS,
   housing, health, education, broadband, immigration, environment, then
   Epic-7 elections/crime/FEC when their gates permit.
5. **Storage cleanup.** Run the table-width/type audit after the new packed
   path is proven; delete only reconciled derived rows, never retained evidence.

The executable story queue is `stories.yaml`. If prose and that queue disagree,
the story dependencies and gates win unless the operator changes the spec.

## Open items (verify in the source-specific story, not by assumption)

- Exact congressional-district vintage used by each selected **CBP** reference year.
- Endpoint, terms/licence, size, coverage years, field dictionary and publisher
  count/manifest for every roadmap source still marked `verified: false`.
- Tract/block/block-group national capacity before those layers are approved.
- Historical 117th-Congress comparability: 2021 ACS is explicitly a 116th-
  Congress geography product and must not be relabelled.
- Why `stage.fec_row` holds ~102 M rows when the registry lists FEC as a
  disabled pilot; this is independent cleanup and does not open Epic 7.
