# Data audit, phase 1: what we hold versus what the report card needs

Date: 2026-10-10. Read-only. Measured against
`_bmad-output/planning-artifacts/briefs/brief-OpenDiscourse-2026-10-10/` (brief + addendum).
Counts are planner estimates from `pg_class.reltuples`, not exact. Nothing was changed or deleted.
Verdicts are proposals for operator sign-off. I did not verify that every staging table can be
rebuilt from retained files; that check must come before any wipe.

## 1. Database size: 536 GB total

| Table | Size | Rows | What it is | Proposed verdict |
|---|---:|---:|---|---|
| `stage.acs_pums_record` | 286 GB | 144 M | Half-loaded person-level census microdata, raw JSON | **Trim** (see 3a) |
| `fact.acs_bulk_estimate` | 105 GB | 281 M | ACS table values, one row per value, state/county scope | **Replace** by packed table after checks (ADR-0006) |
| `stage.fec_row` | 74 GB | 102 M | FEC files as raw JSON, unverified legacy | **Replace** with typed cycle tables, then drop (3b) |
| `stage.cbp_row` | 22 GB | 29 M | Business-patterns staging; loaded into `fact.business_pattern` (12 GB) | Trim staging once the fact table is verified |
| `core.geography_boundary` | 11 GB | 377 K | District/county/etc shapes | Keep; consider simplified copy for display |
| `stage.tiger_feature` | 11 GB | 374 K | TIGER staging used by 10.2 validation | Keep until Story 10.3 done, then trim |
| `stage.acs_bulk_row` | 5.5 GB | 5.6 M | ACS staging | Trim after packed load verified |
| Legislation and votes (core/fact) | about 9 GB | | bills, text, actions, votes (7.2 M), sponsors | **Keep** (core of cards) |

About 388 GB (72%) is staging or superseded data. The report-card core (people, votes, bills, text,
committees) is under 10 GB.

## 2. Report-card sections versus holdings

| Card section | Needed data | Have | Gap |
|---|---|---|---|
| Identity, tenure, offices | people, memberships, terms, IDs | 12,770 people, 45,535 memberships, BioGuide | Pre-Congress offices (prior positions) |
| Attendance, party loyalty | roll calls, member votes | 23,359 roll calls, 7.2 M votes, 108-119; party totals | Reasons for dissent (floor speeches) |
| Ideology | votes | Voteview 51 K members, 113 K roll calls | Issue-level scales (need topic taxonomy) |
| Committees | assignments | 559 committees, 3,895 seats (current only) | Historical seats |
| Bill and law text | text, summaries, subjects | 135 K text versions (113-119), 208 K summaries, 2.1 M subject rows | 108-112 text; amendments text |
| Consistency over time | topic labels + votes | subjects exist | Topic taxonomy, human-checked sample |
| Ethics actions | committee reports | none | Source to build |
| Donors | FEC cycles 2000-2024 | 102 M raw rows, unverified, not linked to people | Typed model, candidate-committee bridge |
| Lobbying, foreign agents | LDA, FARA | none | Sources to build |
| Trades and assets | House/Senate disclosures | none | Source to build |
| District change | place-time outcomes | ACS (state/county), population estimates, DHC 2020, business patterns, FRED macro | District-level ACS, jobs (LAUS/QCEW), crime, housing, health, taxes, immigration measures |
| Money into district | awards | none | USAspending |
| Constituent opinion | CES | none | New source |
| Statements | CREC speeches, GDELT | none (OpenStates snapshot has no federal speeches) | Sources to build |

## 3. Notes behind the verdicts
a. **ACS person microdata.** The published district tables already provide district income, housing,
nativity and similar measures. Person-level records matter only for custom tabulations (they are keyed to
PUMAs, not districts) and do not feed any card section directly. The 136 GB of source files stay
retained. The 286 GB raw-JSON staging can be dropped, with the decision recorded, and a typed reload
done only if a research question needs it.
b. **FEC.** The approved plan already replaces `stage.fec_row` with typed, cycle-partitioned facts after a
four-file pilot. Dropping the raw JSON before the typed pilot passes would remove the only copy of the
parsed rows; the source ZIPs remain retained, so it is rebuildable.
c. **Margins of error.** Keep them only for curated metrics that get compared across districts; drop them
from other packed tables.

## 4. Sources to add, in priority order (for the cards)
1. FEC typed cycles + candidate-committee bridge (donors, concentration).
2. Lobbying Disclosure Act (bill-level links) and FARA.
3. USAspending (money into districts).
4. Outcome measures at district/county: BLS LAUS and QCEW, IRS SOI, HUD, FHFA, NIBRS, CDC PLACES, CBP.
5. Congressional Record speeches; ethics actions; House/Senate disclosures.
6. Cooperative Election Study; election results; topic taxonomy.
7. GDELT news-quoted statements, then social media if obtainable.

Each needs a source contract (coverage, licence, size) before acquisition.

## 5. Decisions needed from the operator
1. Approve dropping `stage.acs_pums_record` (286 GB derived rows only; files retained)?
2. Approve dropping `stage.fec_row` after the typed FEC pilot passes (not now)?
3. Approve the priority order in section 4?
4. Confirm the short list of card sections for the first published card.

## 6. Operator decision on PUMS (2026-10-10)
Keep all ACS PUMS: every 1-year release (2005-2019, 2021-2024) and every 5-year release
(2005-2009 through 2020-2024), person and housing, as typed tables with the person weight and all 80
replicate weights, plus a per-year harmonization mapping. No sampled subset. The 286 GB raw-JSON staging
is dropped only after the typed tables are loaded and reconciled per release; retained source ZIPs are
never touched. Size estimate (about 100-200 GB typed) must be measured on one release before the full run.
The 5-year file pools five annual survey years (about 5x the records of a 1-year file); it is not a
change measure, and its respondents overlap with the 1-year files. Reason: policy-impact and
standard-of-living analysis, multilevel models, and small-area estimation all need it.
