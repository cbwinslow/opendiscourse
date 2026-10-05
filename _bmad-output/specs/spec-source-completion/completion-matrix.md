# Source completion matrix

Read with `SPEC.md`. “Loaded” means current operational evidence says rows are in the live warehouse; it does not override a missing field checklist, stale tracker, or named publisher exception.

## Shared completion gate

A source is complete only when all applicable checks pass:

1. A Connector downloads from the original publisher into `DATA_ROOT`, capacity is known, and artifacts are immutable and registered.
2. The loader records `ingest.run` and target coverage, is safe to rerun, and resumes a stopped run without duplicate facts.
3. Rows carry source evidence; person joins use a provider-stated stable identifier.
4. A field checklist accounts for every offered field as typed, whole-record-only, or intentionally out of scope.
5. A source count or manifest comparison is recorded when one exists; otherwise the matrix names the best available basis and its limitation.
6. `inventory/progress.yaml`, the live verification, and `docs/PROJECT-STATE.md` agree before the source is marked `loaded`.

## V1 delivery queue

| Order | Source / bounded work | Current evidence | Completion gap and next deliverable | Stop condition |
|---:|---|---|---|---|
| 1 | Legislative tracker reconciliation | Bills 106–119, official votes 108–119, bill text 113–119, people, terms, committees, Voteview, and CBO estimates are live. | Update `inventory/progress.yaml` to match verified live status; retain named exceptions. Retry only when Congress.gov serves the two missing 107th bill detail pages and three cosponsor pages. Write a small reconciliation spec. | Do not rerun the full 106–107 bill job while those five pages return HTTP 500. |
| 2 | Member completion closeout | The reproducible profile run `2acfd000-8f44-4eb4-94d3-6baee9566801` succeeded on port 5434 and the checklist exists. | Verify the person-merge committee-seat behavior before claiming the legislative member north star fully met. | Do not change a displayed name from an upstream roster string. |
| 3 | Epic 10: 119th/2024 district vertical slice | District spec is approved; retained 2024 ACS files already contain congressional-district rows; current TIGER/ACS loaders do not publish the needed district geography/facts. | Execute Stories 10.1→10.6: ADR/storage contract, 119th TIGER boundary, division-boundary relation, packed 2024 ACS CD facts, metric registry, then `mart.congressional_district_period`. | Do not add horizontal sources or national block/tract geometry before Story 10.6 opens `slice_proven`. |
| 3a | Compact ACS PUMS/AHS continuation | Raw official archive is retained; the JSONB staging run was stopped 2026-10-05 after 153.3M rows because the representation is too wide. | Resume only through the compact typed model specified by the district/housing contracts after the first district slice is stable; reconcile before deleting derived JSONB staging. | Do not restart `od-acs-housing-archive.service` or treat PUMA records as district microdata. |
| 3b | ACS longitudinal expansion | Standard 1-year and older 5-year products remain valuable, but period/geography comparability is not yet a first-slice requirement. | After Story 10.6, use `spec-longitudinal-source-coverage` for a bounded comparable release/geography slice. | Never mix 1-year and 5-year estimates or relabel 2021 ACS district rows as 117th-Congress geography. |
| 4 | FRED contract and refresh | 38 series, 1919–2026, are loaded, but no reviewable intended-series manifest exists. | Specify the governed series manifest, field checklist, freshness rule, coverage basis, and Connector/run-ledger adoption. | Do not silently grow the series set or revive reverted central-dispatch code. |
| 5 | Treasury and BLS scope decisions | Treasury yield curves are loaded through 2026-08-05; BLS has only nine national pilot series for 2007–2016. | Decide whether Treasury fiscal data belongs in v1; separately specify the BLS geographic products, series, historical range, and completion basis before acquisition. | Do not call the BLS pilot comprehensive or load arbitrary API series. |
| 6 | OpenStates v1 boundary | A verified snapshot is available through a read-only FDW; promotion work was reverted and must be redone under AD-8. | Audit fields and define one bounded, evidence-backed promotion slice only after the legislative/Census work above is stable. | Never write source dump tables or expose FDW relations as the researcher contract. |
| 7 | Access and marts | Core data exists; reviewed API views and reproducible research packs/marts do not. | Define a first researcher question, then build the needed `api` view or `mart` with its own spec. | Do not build generic dashboards or scorecards first. |

## Legislative evidence and named exceptions

| Dataset | Covered period | Live evidence | Named remaining gap |
|---|---|---|---|
| Congress.gov bills | 106–107 (2000–2002) | 106: 10,840 bills, matching publisher list; 107: 10,789. | 107 H.R. 2842 and H.R. 2843 detail pages return HTTP 500. Cosponsor pages for 106 S. 1378, 106 S.Res. 218, and 107 H.R. 5346 return HTTP 500; their bills exist. |
| GovInfo BILLSTATUS | 108–119 (2003–present) | 96 verified ZIPs; full source records and typed bill sections loaded. | Current Congress refresh is normal operations; named surplus/format exceptions remain recorded in the legislative north star/state. |
| GovInfo BILLS text | 113–119 (2013–present) | 135,136 versions attached to bills. | Six 113th XML members are unreadable due to invalid publisher bytes; 108–112 have no BILLS bulk. |
| Official votes | 108–119 | 23,359 roll calls and 7,384,589 member votes. | House Letlow and two Senate publisher quirks remain named exceptions. |
| Members / terms / committees | People 1789–present; coverage 108–119 | 12,770 people, 45,535 memberships, 559 committees, 3,895 seats, and reproducibly loaded profile fields. | Live person-merge committee-seat behavior remains to verify. |
| Voteview | Historical files, including 108–119 | 51,064 members, 113,553 roll calls, 848 party rows. | 32 recent member rows remain unlinked because ICPSR values conflict; individual-vote file is intentionally excluded. |

## Deferred, conditional, and prohibited work

| Class | Sources | Trigger before work begins |
|---|---|---|
| V1 active | Census CD/SLD boundaries, bounded relationship/BEF evidence, packed 2024 ACS district facts | Epic 10 Stories 10.1-10.6, in order. |
| Post-slice conditional | CVAP, CBP congressional district, IRS SOI, LODES, BEA/additional BLS, USAspending, Treasury fiscal data and later topic sources | Story 10.6 complete plus a source-specific spec that defines grain, years, capacity, field checklist and coverage basis. |
| Epic-7 deferred | Elections, FBI crime, FEC-native expansion | Epic 7 explicitly opened; applicable identity/source prerequisites complete. |
| Approved strict-gated programme | FEC canonical facts, OpenStates promotion, campaign joins | Follow the FEC/OpenStates specifications: pilot and model gates first; each transfer batch needs capacity approval/reconciliation; joins wait for their reviewed identifier contract. |
| Catalogued only | Congress.gov amendments/reports/meetings/nominations, GovInfo PLAW/CREC/CHRG/CRPT, CourtListener, regulations | A bounded user research question and source-specific completion spec. |
| Prohibited now | News, stock prices, opaque corruption scores, mixed Epstein collection | Remain out of product scope or on legal/sensitivity hold; no ingestion from legacy storage. |

## Tracker repair checklist

- Compare each `inventory/progress.yaml` state to a fresh read-only verification and the current project state before changing it.
- Correct stale “ready” entries for live legislative sources, but preserve unresolved pages and malformed publisher files in `next`/validation text.
- Add missing field checklists before claiming a non-legislative source complete.
- Record every source decision and story status change in `docs/PROJECT-STATE.md`.
