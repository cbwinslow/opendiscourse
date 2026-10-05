---
id: SPEC-district-linked-context
status: draft-for-operator-review (2026-10-05)
companions:
  - jurisdiction-time-model.md
  - ../../../inventory/dataset-roadmap.yaml
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
  `source_artifact_id` and `source_ordinal`; a field dictionary maps array position to
  field id and label; a view unnests to one row per field for researchers; the loader
  reconciles parsed versus stored counts and is idempotent and resumable; the existing
  280 M facts are re-derived from retained files and compared before the old table is
  dropped (derived rows only; retained files are never touched).
- **CAP-3** Person-level ACS microdata is queryable at PUMA with typed columns.
  Success: a typed table (~55 analysis columns, integer types, weights kept) is proven on
  one year, then all 1-year files and the four non-overlapping 5-year windows load;
  replicate weights and imputation flags stay in retained ZIPs; every row carries
  artifact, member and ordinal; 1-year and 5-year stay separate products.
- **CAP-4** Topic sources join to members by geography. Success: each source is
  verified at its official endpoint (URL, licence, size, coverage) before a Connector
  is written; each declares its native geography and, where it does not match a
  district, an approved crosswalk with the apportionment rule stated (an approximation
  is labelled as one). Priority: election results by district (party), FBI crime,
  immigration (DHS/CBP/EOIR/State), benefits (SNAP, TANF, SSA, Medicaid, HUD),
  IRS income by ZIP/county, BLS LAUS/QCEW by county, BEA county output, HUD-USPS ZIP
  crosswalk.
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
  `congressional_district_year` builds from stages 1-10 with every column traceable.
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
  keeps its `gate`: `v1_spine` (TIGER, ACS, CBP, decennial, PEP) may proceed;
  `slice_proven` waits for a proven Connector-to-mart slice (v1-scope.md);
  `epic7` (elections, crime, money) stays closed until Epic 7 opens;
  `person_join` needs BioGuide through `identitygate`.
- Direct district data beats crosswalking; ZCTA/ZIP is an escape hatch, labelled.
- Legislative-effectiveness and any member scorecard are CAP-9 (reserved); they need
  their own spec and stay separate from constituency outcomes and causal claims.
- Publisher facts in the roadmap came from a research summary and are unverified
  until each source's story checks them.
- Tract and block-group levels are out of this spec's first phase (85 k and 242 k
  geographies); revisit with measured sizes.
- Puerto Rico microdata is deferred by operator decision (2026-10-05).

## Phases

1. ADR for packed ACS facts; geography types and the Congress-to-vintage rule;
   `fact.acs_table_row` + field dictionary; reload 2021-2024 for the new levels.
2. Compact person table proven on one year, then the rest; retire
   `stage.acs_pums_record` after reconciliation.
3. Geography spine (roadmap stages 1-2): TIGER CD/SLDU/SLDL/PUMA (+block, VTD, place,
   school district), `division_boundary`, `geography_crosswalk`, relationship and
   block equivalency files. Then ACS district facts (stages 3-4) and CBP at CD (6).
   Then, only when their gates allow, CVAP, IRS, LODES, USAspending, GAO CPF/CDS
   (stages 5-10), in roadmap order.
3b. Topic sources in the CAP-4 priority order, one verified source at a time.
4. Type and storage audit of existing tables, then cleanup.

## Open items (need verification, not assumption)

- Earliest year for which the table-based Summary File publishes by district.
- Which Congress each ACS vintage's districts correspond to (including mid-decade
  redistricting in some states).
- Official endpoint, licence, size and geography of every CAP-4 source.
- Tract/block-group inclusion: revisit after measured sizes (tract is the crosswalk
  backbone, so it may be needed before ACS tract facts).
- Reconcile CAP-4's priority list with the roadmap order (election results are Epic 7).
- Roadmap `verified: false` rows: endpoint, licence, size, years, geography.
- Why `stage.fec_row` holds ~102 M rows when the registry lists FEC as a disabled pilot.
