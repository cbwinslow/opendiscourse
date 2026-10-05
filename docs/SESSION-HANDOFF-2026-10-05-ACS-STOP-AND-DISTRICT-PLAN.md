# Session handoff — ACS loader stopped, district-linked plan — 2026-10-05

## Start here

Read `AGENTS.md`, `docs/PROJECT-STATE.md`, then this file and
`_bmad-output/specs/spec-district-linked-context/SPEC.md` (draft, awaiting operator
review). This supersedes the "do not interrupt" instruction in
`SESSION-HANDOFF-2026-09-29-ACS-STAGING-AND-INVENTORY.md`.

## What happened

- The ACS PUMS/AHS staging service `od-acs-housing-archive.service` ran from
  2026-10-01 23:37 UTC and was **stopped cleanly by the operator's decision on
  2026-10-05 10:30 UTC** (exit 0). No process is running. Nothing was deleted.
- State at stop: run `99a84ef6-cf71-4347-ae3b-0fb079c13ede` still shows
  `status=running` in `ingest.run` (stale, left as is: resume reads `ingest.run_target`).
  1,731 members succeeded, 153,320,047 rows parsed and inserted, 0 rejected.
  `stage.acs_pums_record` is 286 GB (JSONB rows, ~1,760 B each). About 1,898
  members / 558 GB of CSV were still to load.
- I started two heavy `count`/`group by` queries on that table and they lingered;
  both were cancelled. Avoid full scans of `stage.acs_pums_record`.

## Corrections to earlier statements

- The `opendiscourse` database lives on tablespace `odspace`
  (`/home/cbwinslow/workspace/data-lake/opendiscourse/pg17`), on the 2.9 TB workspace
  volume (1.4 TB free). My earlier claim that it would fill the 194 GB root disk
  was wrong. The size problem is real (JSONB staging, ~1.56 TB projected) but not a
  disk-full emergency.

## Measured facts

- Retained PUMS: 3,502 data ZIPs; CSV 1-year 129 GB, 5-year 551 GB (person 488 GB,
  housing 192 GB); AHS ~2 GB; ZIPs on disk 128 GB.
- Typed person table, 55 analysis columns, one California 2023 file
  (392,318 rows): 231 B/row, 86 MB. Full-set figure (~200-250 GB) is an extrapolation.
- ACS 5-year table files (`raw/census/acs_5_bulk/2021..2024`, 111 GB) contain all
  geographies: 440 CD, 1,964 SLDU, 4,880 SLDL, 2,486 PUMA, 33,772 ZCTA, 85,381 tract,
  242,296 block group. Current loader keeps state+county only.
- `fact.acs_bulk_estimate`: ~280 M rows, 105 GB (~375 B/fact). Packed
  `(release, geography, table)` rows with `float8[]` arrays measured 9.3 B/fact
  (B01001 2023, 47,367 rows, 41 MB).
- `core.geography` types: zcta, county, state, cbsa, nation. No CD/SLD/PUMA yet.
- Member to district path: `core.membership` -> `core.post` -> `core.division`
  (OCD id, e.g. `ocd-division/country:us/state:oh/cd:7`).
- Largest tables: `stage.acs_pums_record` 286 GB, `fact.acs_bulk_estimate` 105 GB,
  `stage.fec_row` 74 GB (102 M rows although FEC is a disabled pilot: unexplained),
  `stage.cbp_row` 22 GB + `fact.business_pattern` 12 GB, `stage.tiger_feature` 10 GB +
  `core.geography_boundary` 10 GB (possible duplicate copies).
- BLS LAUS/CPI: 9 national series to 2016 only; QCEW and FBI crime: nothing loaded.

## Decisions (operator, 2026-10-05)

- Stop the ACS loader. Keep person-level microdata, stored compactly.
- Goal: measure effects of politicians' votes and policies; link demographics,
  income, education, crime, immigration, benefits, race, children, sex, age to
  members by district, ZIP and state. Keep all recommended and "maybe" Census
  families. Puerto Rico microdata not wanted.
- Optimize column types and normalize. Approved plan: the four phases in the SPEC.

## Not yet done (next steps, in order)

1. ADR-0006 (packed ACS facts), geography types for CD/SLD/PUMA, Congress-to-vintage
   rule, `fact.acs_table_row` + field dictionary, reload 2021-2024 for new levels,
   reconcile against the old table before retiring it.
2. Compact person table on one year, then all 1-year and four non-overlapping 5-year
   windows. Retire `stage.acs_pums_record` only after reconciliation; record the wipe.
3. Topic sources, one verified at a time (election results by district first).
4. Storage-type audit of existing tables.
5. Resolve open items in the SPEC (earliest district-level ACS year, Congress for each
   ACS vintage, source endpoints/licences, why `stage.fec_row` is populated).
6. The stale `running` run row and `resume_cursor` state need a deliberate decision
   before any restart of the old loader.

## Files created this session (uncommitted, on `main`)

- `_bmad-output/specs/spec-district-linked-context/SPEC.md`
- `docs/research/2026-10-05-census-catalog-draft-decisions.csv` (573 Census families,
  rule-based draft tiers, not reviewed)
- `docs/research/2026-10-05-dataset-candidates-by-topic.md` (non-Census candidates,
  written from general knowledge; every row must be verified at its endpoint)
- Downloaded: `data-lake/opendiscourse/raw/census/catalog/data.json` (Census API catalog)
- Not committed: the working tree also has unrelated Congress/FEC edits and untracked
  skill folders from other work; preserve them.
