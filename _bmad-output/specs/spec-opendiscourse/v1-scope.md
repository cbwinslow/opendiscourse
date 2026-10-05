# Source sequencing

Delivery order (BMAD wins over stale `docs/blueprint.md`):

```text
identity → legislation (incl. Epic 8 primitives) → TIGER/geography
→ Census/housing/economic → marts/access
then v1.1: disclosures → elections → crime
```

District geography (TIGER CD/SLD/PUMA, `division_boundary`, crosswalks, ACS at
districts, CBP at districts) is part of the TIGER/Census step above (Epic 10,
stages 1-6 of `inventory/dataset-roadmap.yaml`). Other roadmap sources wait for
a proven slice; elections, crime, and money stay v1.1.

Do not start v1.1 because a staging table already exists. For district-linked
context, "slice proven" now has one concrete meaning: Epic 10 Story 10.6 is
complete and `mart.congressional_district_period` proves the 119th-Congress /
2020-2024 ACS vertical slice with evidence drill-through. Pre-Connector
ACS/TIGER/bill loads do not count by themselves; the touched district path must
meet the Connector/lifecycle and mart completion checks in Stories 10.1-10.6.

The FEC/OpenStates political-research programme is a separately approved,
strict-gated sequence: OpenStates field/coverage mapping → four-file FEC pilot
→ typed model/benchmark → approved 2000–2024 batches → identifier bridge →
research marts. It does not authorize a raw transfer, canonical promotion, or
person join merely because planning is complete.

## Coverage target (operator, 2026-09-19)

Federal legislation **Congresses 108-119** (2003 to now): GovInfo BILLSTATUS
bulk starts at the 108th. The approved FEC target is every available equivalent
official cycle from **2000–2024**, subject to its source-specific gates.
Completeness is measured (Story 9.3), not assumed. Untrustworthy derived data (unverified legacy
caches, partial/failed-run output, rows from reverted AGY code) may be wiped and
re-ingested; loaded Census/CBP/TIGER/PEP/DHC data is not redone without cause.

## v1 loadable spine

Identities, TIGER geography, legislation (Congress.gov, GovInfo, OpenStates
FDW), census/housing (existing contracts), sparse macro (FRED, Treasury,
bounded BLS).

## Post-v1 work and approved FEC programme

- **Politician joins** (FEC/disclosure/elections-as-member): blocked on CAP-4
  BioGuide identity. Never name-match.
- **FEC-native facts:** their planned Connector and pilot are approved, but
  historical transfer and canonical promotion remain gated by the FEC
  specification. Candidate/committee use `(id, cycle)` and transactions use
  FEC `sub_id`+cycle in compact typed, cycle-partitioned facts. All approved
  available 2000–2024 cycles remain queryable; derived Parquet is not the sole
  older-history store.
- **Crime-native staging:** remains v1.1 and opens only with its own approved
  specification after the v1 spine and Epic 8.
- **`stage.fec_row` already holds ~102M rows on the operator cluster.**
  That is leftover staging, not authorization to promote, join, or open
  Epic 7. Schema support ≠ ingest scope (AD-10).

## Not a product domain

News, stocks/CFA, Epstein-as-schema, corruption scores as a schema domain.
Scorecards over evidence-backed rows are allowed later as derived marts (SPEC
non-goals); not part of the v1 ingest spine.
`core.instrument` / `fact.market_bar` are retained empty compatibility
tables; no market-price ingest.

## Already true on the cluster

Live status moves. The legislative done-state is `legislative-north-star.md`.
The handoff with counts is `docs/PROJECT-STATE.md` (read that, not this list,
when they disagree).

- Database name `opendiscourse`, port 5434 (~242 GB as of 2026-09-22).
- OpenStates stays in database `openstates`; OCD relations mapped via FDW.
  Do not merge the dump. Do not treat FDW as the researcher contract;
  promote into `core` (AD-8).
- `core.embedding` stays portable `real[]` until a chunk story needs pgvector.
- Loaded through 2026-09-23: bills 108–119 with full BILLSTATUS records;
  official House and Senate votes 108–119; bill text 113–119; people, terms,
  and current committee seats. Not loaded live: Voteview (command is on
  `main`) and typed CBO columns (written, not merged).
- `api` schema exists with no reviewed views. Some `mart` / `leg` views exist.
