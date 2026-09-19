# Source sequencing

Delivery order (BMAD wins over stale `docs/blueprint.md`):

```text
identity → legislation (incl. Epic 8 primitives) → TIGER/geography
→ Census/housing/economic → marts/access
then v1.1: FEC → disclosures → elections → crime
```

Do not start v1.1 because a staging table already exists. Do not expand
horizontally until a Connector→mart slice is proven (FRED e2e and/or
legislator-vote). Pre-Connector ACS/TIGER/bill loads do not count.

## Coverage target (operator, 2026-09-19)

Federal legislation **Congresses 108-119** (2003 to now): GovInfo BILLSTATUS
bulk starts at the 108th. FEC cycles 2004+ when v1.1 opens. Completeness is
measured (Story 9.3), not assumed. Untrustworthy derived data (unverified legacy
caches, partial/failed-run output, rows from reverted AGY code) may be wiped and
re-ingested; loaded Census/CBP/TIGER/PEP/DHC data is not redone without cause.

## v1 loadable spine

Identities, TIGER geography, legislation (Congress.gov, GovInfo, OpenStates
FDW), census/housing (existing contracts), sparse macro (FRED, Treasury,
bounded BLS).

## v1.1 (do not start in v1)

- **Politician joins** (FEC/disclosure/elections-as-member): blocked on CAP-4
  BioGuide identity. Never name-match.
- **FEC-native and crime-native staging:** not identity-blocked; still v1.1.
  Open only with Epic 7 after the v1 spine and Epic 8. Canonical FEC grain
  (when opened): candidate/committee `(id, cycle)`; itemized `sub_id`+cycle;
  hot fact = current + two prior cycles (`resolved-questions.md`).
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

- Database name `opendiscourse` (234 GiB, port 5434).
- OpenStates 38 GiB stays in database `openstates`; 11 OCD relations mapped
  via FDW. Do not merge the dump. Do not treat FDW as the researcher
  contract; promote into `core` (AD-8).
- `vector` extension 0.8.5 installed; `core.embedding` still portable `real[]`.
- Loaded (updated 2026-09-19): 172,709 bills for Congresses 108-119 with full BILLSTATUS records, CRS
  summaries, laws, related bills and amendments (Stories 9.5, 9.5b); 45,535 member terms with 740 posts
  and 690 divisions (Story 3.3); ~465k member votes for Congresses 118-119 only; ACS bulk ~99 GiB,
  TIGER boundaries ~10 GiB, `stage.fec_row` ~74 GiB.
- Still empty / missing: market tables, `core.document_chunk`, `core.embedding`, votes for
  Congresses 108-117, committee membership. The live database is at the latest Alembic head.
- `api` schema exists with no reviewed views. Some `mart` / `leg` views exist.
