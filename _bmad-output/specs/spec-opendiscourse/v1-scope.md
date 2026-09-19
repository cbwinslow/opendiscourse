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
- Already loaded (pre-Connector paths): ~36k bills, ~465k member votes,
  ACS bulk ~99 GiB, TIGER boundaries ~10 GiB, `stage.fec_row` ~74 GiB.
- Still empty / missing: `core.legislative_session`, `core.membership`,
  market tables. `core.post` / `core.division` exist in the Alembic contract
  (Story 8.1, revision `a4f8c2e9b176`); live `opendiscourse` on 5434 may
  still need `alembic upgrade head`.
- `api` schema exists with no reviewed views. Some `mart` / `leg` views exist.
