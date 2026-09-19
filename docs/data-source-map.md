# Data source map: congressional data (2026-09-19)

What exists, what is loaded, what is still to acquire, and where each thing comes from.
Companion to `data-acquisition-plan.md` (the workflow and the order of work) and
`inventory/sources.yaml` / `inventory/progress.yaml` (the registry). Items marked *(verify)*
come from general knowledge, not from a check against the live source; confirm against current
documentation before building a Connector.

Every source follows download -> inventory -> ingest from its **original endpoint** into
`DATA_ROOT`. Nothing below authorizes reading a machine-specific path, and no person join may use
a name: federal people join on BioGuide, with LIS (Senate votes) and ICPSR (Voteview) through the
`core.person_identifier` crosswalk.

## 1. Loaded (2026-09-19)

| Data | Where | State |
|---|---|---|
| Bills, actions, sponsors, cosponsors, committees, subjects, Congresses 108-119 | GovInfo BILLSTATUS zips -> `core.bill*` (Story 9.5) | 172,709 bills |
| Every BILLSTATUS element, per bill | `core.bill_source_record` (Story 9.5b) | 172,703 records |
| CRS summaries, laws, related bills, amendments | `core.bill_summary`, `bill_law`, `bill_related_bill`, `bill_amendment` (Story 9.5b) | see PROJECT-STATE |
| People and identifiers | `core.person`, `core.person_identifier` (congress-legislators) | 12,771 people; BioGuide 12,770, ICPSR 12,298, LIS only 328 |
| Roll calls, member votes | `core.roll_call`, `fact.member_vote` (OpenStates federal, read through the FDW) | 1,827 roll calls, 473,490 votes, Congresses 118-119 only |
| Census, FRED, BLS (pilot scale), Treasury curve, OpenStates state dump | `fact.*`, `core.geography*`, `openstates` DB | loaded; see `inventory/progress.yaml` |
| FEC bulk (pas2, oppexp, oth, indiv 2000-2016) | `stage.fec_row`, 101.7M rows | staged, unattributed, person joins gated |

Empty and waiting: `core.membership`, `core.post`, `core.division` (member terms), `core.document_chunk`,
`core.embedding`.

## 2. In the BILLSTATUS record but not yet typed (no new download needed)

CBO cost estimates (`cboCostEstimates`), committee reports (`committeeReports`), recorded votes
inside actions, action detail (committees, calendar numbers, source system), alternate titles
(`titles`), every text format (`textVersions/item/formats`), notes, calendar numbers, amendment
actions, cosponsors and their withdrawal dates. 13 old-style files (`billType`/`billNumber`) also
carry committees and subjects under `committees/billCommittees` and `subjects/billSubjects`, which
`bill_committee`/`bill_subject` do not yet read.

## 3. Tooling we already have

- `vendor/unitedstates-congress` (cloned, not wrapped): tasks for `votes`, `bills`, `bill_info`,
  `amendment_info`, `committee_meetings`, `nominations`, `statutes`, `govinfo`, `voteview` and
  `adler_wilkerson_bills` (Congressional Bills Project topic codes).
- `vendor/congress-legislators` (loaded for people; terms and committee membership are not).
- `providers/congress.py`: Congress.gov API adapter (members, bills, actions, amendments,
  committees, House votes); plan `congcur` refreshes Congress 119.
- `providers/govinfo.py`, `providers/paced.py`: GovInfo HEAD, manifests, paced download.
- `providers/official_counts.py`: official roll-call totals used by `research-db coverage`.

## 4. Legacy lake: remember for when the time comes

`/mnt/storage/data-lake/government` is `legacy_cache_unverified`. It is a shortcut for the
operator's machine only, never an input to the project. Anything worth keeping must be re-acquired
from its origin through a Connector; use the lake to know what to fetch and to compare counts.

| Legacy folder | Contents | Use later |
|---|---|---|
| `epstein/raw-files/congress/bills`, `congress/congress-data` | 268,740 bill JSON files, Congresses 93-113 (2.0 GiB), and 118th list chunks | the only local trace of Congresses 93-107, which BILLSTATUS (108+) does not cover; re-acquire from Congress.gov or GovTrack and compare |
| `epstein/raw-files/govinfo_bulk` | GovInfo BILLS, BILLSTATUS, BILLSUM, 868 artifacts, 5.5 GiB | BILLSTATUS superseded by Story 9.5; BILLS (bill text) and BILLSUM still to acquire from GovInfo |
| `fec_bulk_data` | 50 FEC zips, 19.7 GiB | already staged (`stage.fec_row`); indiv 2018-2024 and the cn/cm/ccl linkage files are missing |
| `financial-disclosures` | congressional disclosure filings | blocked on a filer-identifier bridge; re-acquire from the House Clerk and Senate portals |
| `courtlistener` | court opinions and dockets | evaluate against the CourtListener bulk files |
| `epstein` | 658 GiB mixed collection | **hold**: inventory only, do not process, move or delete |

## 5. To acquire, by area

**Votes and members**

| Source | What | Key |
|---|---|---|
| House Clerk `clerk.house.gov/evs/YYYY/rollNNN.xml` | every House roll call, each member's vote | BioGuide |
| Senate.gov roll-call XML | every Senate roll call and vote | LIS id (328 of ours; fix the crosswalk first) |
| Voteview (UCLA) | all roll calls since 1789, DW-NOMINATE ideology | ICPSR |
| GovTrack bulk | bills, votes, members from the 93rd Congress | GovTrack id |
| congress-legislators terms | terms, party, state, district, committee membership | BioGuide |

**Bill detail**

| Source | What |
|---|---|
| GovInfo BILLS | bill text XML, one file per version |
| GovInfo PLAW, STATUTE, USCODE | public laws, Statutes at Large, U.S. Code |
| Congress.gov API (about 5,000 requests/hour with a key *(verify)*) | amendment detail and text, committee reports and prints, meetings, hearings, nominations, treaties, House/Senate communications, CRS reports |
| Adler-Wilkerson Congressional Bills Project (via `unitedstates/congress`) | policy-topic codes on bills |

**Evidence of "why"**

| Source | What |
|---|---|
| GovInfo CREC | Congressional Record floor statements; speaker BioGuide id is in the package metadata *(verify)* |
| GovInfo CHRG, CRPT, CDOC, SERIALSET | hearings, committee reports, documents, Serial Set |
| `docs.house.gov` | House committee hearings, markups, witness lists |
| `everycrsreport.com` | CRS reports in bulk |

**Money and influence**

| Source | What | Notes |
|---|---|---|
| FEC | cn/cm/ccl linkage, independent expenditures, raw filings, indiv 2018-2024 | person join gated (`person_join`) |
| Lobbying disclosures (LD-1/LD-2/LD-203), Senate LDA | filings, contributions | site is moving to `lda.gov` *(verify)* |
| OpenSecrets bulk | contributions, lobbying, personal finance | registration required; licence restricts commercial use *(verify)* |
| House Clerk / Senate eFD financial disclosures | periodic transaction reports | filers identified by name only: blocked until an identifier bridge exists |
| USAspending.gov | awards, grants, contracts by place | bulk files and API |
| Appropriations Committees | congressionally directed spending per member | published per member *(verify)* |

**Executive, regulatory, courts**

Federal Register API; Regulations.gov (dockets, comments); reginfo.gov (OIRA reviews); CBO
publications; GAO reports (GovInfo `GAOREPORTS`); CourtListener bulk.

**Elections and districts**

MIT Election Lab, OpenElections, VEST (results by district and precinct); UCLA Lewis historical
district boundaries 1789-2012; Census TIGER congressional districts (TIGER is loaded without a
district layer); Census relationship files for district-to-county/ZCTA weights. Elections joins to
members stay in Epic 7, which is not started in v1.

**Historical depth**

GovInfo Statutes at Large, Serial Set and Congressional Record reach back to the 1800s; the Library
of Congress "Century of Lawmaking" earlier still. Congresses 93-107 bills need Congress.gov or
GovTrack (see the legacy lake row above).

**Other**

LegiScan (state bills, next to the OpenStates dump we hold); VoteSmart, Ballotpedia and C-SPAN stay
identifier cross-references only.

## 6. Order of work

1. Member terms and committee membership from congress-legislators (unblocks the `memberships`
   column in `research-db coverage`, 0 for every Congress today). Add the missing LIS ids.
2. Votes Connector wrapping `unitedstates/congress`: House and Senate XML plus Voteview, Congresses
   108-119.
3. GovInfo BILLS text and PLAW, then Congress.gov amendment detail and committee reports; type the
   CBO estimates, committee reports and recorded votes already in the BILLSTATUS record.
4. FEC linkage files, then CREC, CHRG and CRPT evidence packages.

Not in scope: news, stock and market-price domains, opaque corruption scores (SPEC non-goals).
