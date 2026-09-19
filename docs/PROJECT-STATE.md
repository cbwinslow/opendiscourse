# Project state and handoff

Last updated: 2026-09-19 (Stories 3.1, 3.2, 9.1, 9.2, 9.3, 9.5 merged; 9.5b lossless BILLSTATUS records and typed summaries, laws, related bills, amendments loaded live; 3.3 member terms, posts and divisions loaded live; sources review evaluated, ADR-0004; backup risk found, see "Stop-and-fix items"). Read this first when resuming, then `AGENTS.md`,
`_bmad-output/specs/spec-opendiscourse/SPEC.md`, and
`_bmad-output/planning-artifacts/epics.md`. If this file and code disagree, the
code and tests win (hierarchy of truth in `AGENTS.md`). Update this file when a
decision or story status changes.

## Goal

A reusable, provenance-backed research database for U.S. political and policy
research that other people can bootstrap onto their own servers. Facts must trace
to immutable source evidence. Later, on top of it: NLP and vector search over bill
text, vote summaries, politician voting profiles, and scorecards.

**Now:** build the database and its ingestion workflows: complete, trustworthy,
idempotent, fast, portable. Do not build scorecards, NLP, or analysis yet. Do not
code for one specific analysis; build generic, extensible pieces (Connector, run
ledger, load strategies, coverage checks) that later models can sit on.

## Decisions (operator-approved)

1. **Scope:** federal legislation for **Congresses 108-119** (2003 to now). GovInfo
   BILLSTATUS bulk starts at the 108th (to be confirmed against manifests in
   Story 9.3). FEC cycles 2004+ later (v1.1). Census, ACS housing, crime, FRED are
   useful but later; crime is Epic 7 (not v1).
2. **Wipe and re-ingest is allowed** for untrustworthy derived data (unverified
   legacy caches, partial/failed-run output, rows written by reverted AGY code).
   No need to ask first; record what was wiped. Do not redo the loaded
   Census/CBP/TIGER/PEP/DHC data without cause. Never delete or overwrite retained
   artifact files (raw evidence).
3. **Idempotency and speed:** load strategy depends on grain (Story 9.1 / ADR-0003,
   pending a benchmark on one real dataset):
   - bulk facts and staging: reload by partition (COPY to a temp table, validate,
     delete-and-insert the slice in one transaction); fastest, no update bloat.
   - entities other tables reference (bill, person, roll_call): set-based upsert
     from a temp table touching only changed rows; wiping would change UUIDs and
     break foreign keys.
   - raw downloaded bytes: never wiped; reused unless the remote checksum changed.
4. **Scorecards:** allowed later only as derived `mart` outputs over evidence-backed
   rows with transparent indicators; never a corruption score as a schema domain or
   an opaque composite. Needs its own spec (CAP-9). Spec amended 2026-09-19.
5. **Run tracking:** `ingest.run`/`ingest.artifact` exist but lack per-table and
   per-period detail and `code_version` is blank. Story 9.2 adds `ingest.run_target`.
6. **Keep raw bill text** as immutable artifacts + `core.document` now; embeddings and
   vector search later (keep `real[]`, ADR first).
7. **Do not trust Gemini/Antigravity (AGY) output.** Thousands of lines of its code
   were reverted after Codex review. Verify independently; do not delegate to it.
8. **Process:** BMAD is the software SDD; `inventory/` is the data SDD; ADRs record
   decisions. LLMs propose, the operator decides; disagreements are settled by tests
   or benchmarks, not by asking another model. The operator delegates judgment:
   do the right thing rather than adding restrictions or asking permission for
   routine engineering steps. Merge when asked and CI is green.

## What happened (so nobody repeats it)

- AGY merged Story 1.7 (#25), FRED 2.2 (#18), FRED 2.3 (#20), OpenStates 8.2 (#22)
  to `main` unreviewed. Codex audited: 1.7's downgrade deleted evidence and bulk
  refresh overwrote files; 2.2 hard-coded FRED in `registry.sync`; 2.3 left stuck
  leases; 8.2 skipped snapshot validation and mis-keyed memberships.
- PR #26 reverted all four (main = `910823b`). Story 1.6 (AGY-authored tests, PR #24)
  was kept by Codex as sound; treat as unverified until re-checked.
- Story 1.7 was rebuilt by Codex on `fix/1-7-immutable-artifacts` (two reviews, see
  its spec). Data written by the reverted OpenStates/FRED code may still be in the
  database (`ingest.run.code_version` is blank, so runs can't be attributed).

## Data on the cluster (audit 2026-09-19, port 5434, 234 GB)

| Area | Loaded | Gap |
|---|---|---|
| Congress bills | 108th-119th, 172,709 bills (GovInfo's 172,703 plus 6 from another source), Story 9.5; every bill's full record plus CRS summaries, laws, related bills and amendments, Story 9.5b | 6 surplus 119th bills, see "Story 9.5"; CBO estimates, committee reports, recorded votes, alternate titles are in the record but not typed |
| Roll calls / member votes | 118th-119th only (1,827 / 473,490) | 108-117; Senate source is "idea" |
| People | 12,771 (12,770 with BioGuide; loaded 2026-09-19, Story 3.1) | 1 baseline person has no BioGuide; politician joins still gated (Story 3.2) |
| Member terms | 45,535 memberships (41,545 House, 3,990 Senate, 1789-present), 740 posts, 690 divisions, Story 3.3; `coverage` memberships 100% for 108-119 | 1,340 terms have no post (unknown district in the source); committee membership not loaded |
| FEC | 102M rows in `stage.fec_row` (pas2, oppexp, oth complete; indiv 2000-2016 only; unattributed, see above) | staging only; not promoted; person join gated (3.2): needs reviewed contract + cn/cm/ccl files; v1.1 |
| GovInfo BILLSTATUS zips | 96 zips, 574,316,859 bytes (574 MB, 548 MiB; measured 2026-09-19 from the current registry rows) downloaded from govinfo.gov into `DATA_ROOT` and registered (Story 9.5); every zip matches GovInfo's directory manifest | none; the legacy lake copy is no longer an input |
| OpenStates | 10 ok, 5 partial, 3 failed runs | coverage unmeasured; promotion reverted |
| FRED | 135 ok, 6 failed (HTTP 400/500) | some series missing |
| Treasury yields | 29 ok, 24 failed | parser broke ("no recognizable rate table") |
| Census ACS/CBP/TIGER/PEP/DHC | loaded (ACS 281M rows) | no coverage check; most complete area |

Story 9.3 adds `research-db coverage` (first measurement below).

## Decision: fresh start, download from origin (2026-09-19)

Operator decision: the project ships only ingestion that downloads from the original
government source into the user's configured `DATA_ROOT`, then inventories and ingests it
(see AGENTS.md policy and `docs/data-acquisition-plan.md`). Old data on the operator's
server (the legacy lake under `/mnt/storage/data-lake/government`, the `~/workspace/government`
checkout) is not an input to the project. It is being discarded rather than organised; what
is registered in `ingest.artifact` stays until a Connector re-downloads and replaces it.

Discarded work: the lake registry, legacy roots and prune tooling (closed PR #42) were built
to organise that server's data; they are parked locally and will not ship.

**Known debt** (modules on `main` that read fixed local paths; replace with Connectors, do
not extend): `audit.py` `ROOTS`, `ingestion/fec_bulk.py` `LEGACY_ROOT`. The BILLSTATUS debt is
now replaceable (Story 9.5): `legvalidate.BILLSTATUS_ROOT` and its users (`legarchive`,
`govbackfill`, `legload`, `legreconcile`, `govplan`) and their CLI commands (`validate billstatus`,
`plan billstatus`, `backfill-billstatus`, `reconcile billstatus`, `load-billstatus`) are
superseded by `research-db sync-billstatus` and can be removed next. Two things still import
from them, so move those first: `coverage.py` uses `legreconcile._bill_details`, and
`congresshealth.billstatus_coverage` reads run parameters (`congress`, `coverage`) that only the
old loader wrote (it is 119-only and superseded by `research-db coverage` / `loaded`).
`research-db coverage` finds downloaded zips through the artifact registry instead of a fixed path.

## Coverage report (Story 9.3, first measurement 2026-09-19)

`research-db coverage [--congress N] [--refresh-official] [--json]` is warehouse read-only (it only writes metadata caches). Expected counts are
official: GovInfo BILLSTATUS manifests (bills), Senate.gov vote menus and House Clerk index (roll
calls). Actions (`lake_archive`, counted in the unverified BILLSTATUS zips) and members
(`legislators_yaml`, term overlap by BioGuide id) have no official manifest and are labelled so.
Official counts are cached in `data-lake/opendiscourse/meta/coverage/official.json` (current
Congress and year expire after a day); `latest.json` holds the last report.

- **The 108th start is confirmed:** GovInfo's BILLSTATUS root lists Congress folders 108-119 only.
- **Bills:** 108-117 loaded 0 of 10,637-17,828 each (about 134K bills in total); 118 is complete
  (19,315); 119 has 18,058 of 18,956 (898 missing).
- **Lake vs official:** the BILLSTATUS zips match the official manifest exactly for 108-112, 114,
  116, 118; short by 1 (113, 115), 11 (117) and 904 (119). This replaces the earlier "2,831
  missing" figure for the 119th.
- **Actions:** 118 and 119 equal the lake counts; 108-117 not loaded. The 119th has 6 more bills loaded (18,058) than the lake holds (18,052); the extra six came from a source other than these zips and are unexplained.
- **Roll calls:** House 118 has 912 of 1,241 and 119 has 488 of 676; Senate 118 has 176 of 691 and
  119 has 251 of 897. Senate member votes: 118 has 407 (49 Senate roll calls with none), 119 has 0.
- **Members:** `core.membership` is empty: 0 of about 545-560 members per Congress. People are loaded
  (Story 3.1) but no terms.
- **Unattributed:** 286 of 287 runs have no `code_version`; `stage.fec_row` about 101.7M rows.

Roll-call "expected" is the highest number on the official index, so it counts every recorded
call, including ones the source loaders may legitimately skip; check that before treating the
House gap as a loader bug.

## Story 9.5: BILLSTATUS Connector (built and run live, 2026-09-19)

`research-db sync-billstatus [--congress N] [--bill-type T] [--download-only]` is the whole
download -> inventory -> ingest workflow for GovInfo BILLSTATUS (spec
`_bmad-output/implementation-artifacts/spec-9-5-billstatus-connector.md`; code
`ingestion/billstatus.py`, `providers/govinfo.py`, `providers/paced.py`,
`repositories/billstatus.py`). Exit code 0 complete, 1 failed (rerun resumes), 2 loaded but
coverage incomplete.

- **How it decides:** one HEAD per zip (size and `Last-Modified`) against what the registry
  recorded; an unchanged, origin-verified zip is never downloaded again; a registry row with no
  recorded origin state is re-verified by download; each zip is compared with GovInfo's directory
  manifest and the verdict is stored on the artifact (`metadata.coverage`).
- **Refresh:** a changed zip is a new artifact version. Child tables (actions, sponsorships,
  committees, subjects) key on `source_artifact_id`, so the Connector deletes the older versions'
  rows for the bills it rewrites in the same transaction; without that every refresh would
  duplicate every row. Observed live: GovInfo regenerated the 119th `hr` and `s` zips during the
  session; the Connector replaced 294,354 rows for 15,931 bills. **Known cost:** a refresh reloads
  every bill in the zip (about 4.5 minutes for the 119th), not only the changed ones; skipping
  members by content hash is the next optimization if it matters.
- **Live result:** 96 zips (the first pass fetched 572,533,669 bytes; GovInfo has since regenerated the 119th zips, so the current total is the 574,316,859 above and drifts; `du` on the folder also counts superseded versions, 591 MB), 172,703 XML files in the official manifests;
  172,709 bills, 929,756 actions and 2,272,151 sponsorships (every one resolved to a person by BioGuide) loaded for Congresses 108-119 at about 60 bills/s. `research-db
  coverage`: bills loaded equal expected for every Congress 108-118, and every Congress's
  actions equal the zips. A no-op rerun downloads nothing and loads nothing (about 2 minutes,
  mostly the 96 paced HEADs).
- **The 119th surplus (6 bills, 18,962 loaded vs 18,956 official):** H.R. 6, 9, 11, 13, 16, 19,
  "Reserved for the Speaker/Minority Leader", loaded earlier from a `congress.gov` source
  (`metadata.source`), with no identifiers and so no provenance. They are not in GovInfo's
  BILLSTATUS manifest. Left in place; give them provenance or drop them when the Congress.gov
  API Connector is built.
- **What the live run found:** (1) 13 GovInfo files (113th `hr` 1, 115th `hr` 1, 117th `hr` 11: the
  House's reserved numbers) spell identity `<billType>/<billNumber>` instead of `<type>/<number>`;
  the parser skipped them and the run reported partial (exit 2) rather than hiding it. Fixed in
  `parse_billstatus_xml` and `legreconcile._bill_details`; the earlier coverage figures "lake short
  by 1, 1, 11" were these files, not missing data. (2) The 16 registered 118th/119th artifacts
  pointed at legacy-lake files that no longer exist; each was re-downloaded from the origin as a new
  version (v2) and its rows re-loaded and replaced (734,021 child rows superseded). The old v1
  registry rows remain as history and point at missing files; nothing references them.
- **Speed:** the first real load ran at 15 bills/s. A profile showed 27% of the time re-reading SQL
  files and a third of the round trips repeating sponsor lookups; `_query` is now cached and
  sponsor lookups are memoized per run (2.1x in the same profile).
- **Ledger and locking:** every committed batch updates the run's `ingest.run_target` for that
  Congress (`partial` until all of its zips finish, then `succeeded`), so a killed or failed run
  shows the work it really did in `research-db loaded`. A session advisory lock allows one
  `sync-billstatus` at a time (a second fails at once with a clear message). Only strictly older
  artifact versions are ever superseded.
- **Known limitations:** `core.bill_document` (text-version links) has no artifact provenance, so a
  refresh adds text versions but cannot retract one a newer BILLSTATUS file drops; upstream only
  adds text versions, so this is accepted for now (a provenance column is the fix if it ever
  matters). A refresh reloads the whole zip (see above). Concurrent `sync-billstatus` is refused
  rather than merged.
- `ingest.run.code_version` on the backfill runs reads `<sha>-dirty` because docs were being
  edited (tracked files differ); the SHA is the right commit. Runs before 9.2 stay unattributed.

## Story 9.5b: lossless BILLSTATUS records and typed promotion (built and run live, 2026-09-19)

Spec `_bmad-output/implementation-artifacts/spec-9-5b-billstatus-lossless.md`; code
`ingestion/billstatus_record.py` (lossless XML -> JSON and the checks), `ingestion/billstatus_sections.py`
(typed extraction), `repositories/legislation.py::_save_promoted_sections`, migration `e2b7d4a9c815`.
No new command: `research-db sync-billstatus` does it.

- **Why:** a survey of all 172,703 files found 418 distinct element paths; the old parser read about
  60. CRS summaries, amendments, related bills, laws, CBO estimates, committee reports, alternate
  titles, action detail (committees, recorded votes, calendar, source system) and all but the first
  text format were being dropped at load.
- **`core.bill_source_record`:** the whole file as jsonb, unique on `(source_artifact_id, source_member)`,
  written last in each bill's batch transaction, so **a record row means the member is fully loaded**
  (`normalize` resumes by it). A refresh supersedes the older version's record and typed rows for the
  bills it rewrites, in the same transaction (`supersede_bill_children` now clears nine tables).
  Encoding: leaf text stripped of layout whitespace; `item`, `summary`, `link`, `amendment`,
  `recordedVote`, `committeeReport` are always arrays, any other repeated tag too; `dc:` prefix for the
  Dublin Core namespace; attributes as `@name`, text beside children as `#text` (none exist in the corpus);
  text after a child element raises (the member is reported malformed) instead of being lost.
- **Typed tables:** `core.bill_summary` (HTML text kept), `bill_law`, `bill_related_bill` (type lower-cased so
  it joins `core.bill`; relationships as jsonb), `bill_amendment` (sponsor by BioGuide id only, no `person_id`:
  join through `core.person_identifier` at query time). The 13 old-style files
  (`summaries/billSummaries/item`) are covered for summaries. 173 amendments in 115hr3354 repeat
  their scalars (`number`, `congress`, `type`); the typed row takes the first, the record keeps all.
- **Live run (2026-09-19):** migration applied; `sync-billstatus` over all 96 zips reloaded every bill once
  (idempotent: bills 172,709, actions 929,756, sponsorships 2,272,151 unchanged, no duplicates), 0 malformed,
  exit 0. Result: 172,703 records (923 MB with indexes; the 6 surplus 119th bills have none, as they have no
  zip member), 189,511 summaries, 4,278 laws, 142,399 related bills, 67,956 amendments. The run's
  `ingest.run.code_version` reads `7b10ec9...-dirty`: it started before the commit `586f0f6` that holds this
  code, from the same working tree.
- **Verification:** every stored record was compared with its XML member (0 mismatches, 0 missing, 0 bad
  `record_sha256`) and each typed table's total equals the XML element count exactly. Standing checks:
  `tests/test_billstatus_record.py` (14 real fixtures chosen by set-cover over the 418 paths) and the slow
  `tests/test_billstatus_record_corpus.py` (`uv run pytest -m slow tests/test_billstatus_record_corpus.py`,
  about 25 minutes; every member of every zip under `DATA_ROOT`; skips when there are none; both tests
  set `pytest.mark.timeout(3600)` because the suite default is 60 s).
- **Known limitations:** the 13 old-style files' committees and subjects (`committees/billCommittees`,
  `subjects/billSubjects`) are in the record but not in `bill_committee`/`bill_subject`. `save_billstatus_bill`
  writes the record and typed sections on the connection path only (the SQLAlchemy path used by the old fixed-path
  loaders does not). A refresh still reloads a whole zip. Not yet typed: CBO estimates, committee reports,
  recorded votes, alternate titles, text formats, notes (each is one more section function and table).
- **What else exists to acquire** (votes, terms, bill text, amendments detail, FEC linkage, floor statements,
  lobbying, elections, and the legacy-lake items to remember): `docs/data-source-map.md`.

## Story 3.3: member terms, posts and divisions (built and run live, 2026-09-19)

Spec `_bmad-output/implementation-artifacts/spec-3-3-member-terms.md`; code `ingestion/legislator_terms.py`
(parsing and the placement rules), `ingestion/legislators.py` (`_term_rows`, `publish`),
`repositories/people.py::promote_terms` and `sql/query/people/*term*.sql`, migration `f3a8c5d1b7e2`.
No new command: `research-db load-legislators` now loads terms after identifiers, from the same two
retained YAML artifacts.

- **Model:** one `core.membership` per term (person by BioGuide only, House or Senate organization,
  `role` representative/senator, term start and end dates, `metadata` with state, district, party,
  Senate class, state rank, how it began or ended, caucus, party affiliations). Where it was served
  is a `core.post` on a `core.division` with an OCD id: state, `state:xx/cd:N`, `state:xx/cd:at-large`
  (district 0), `district:dc`, `territory:pr|gu|vi|as|mp`, and the historical `territory:dt|ot|pi`
  (upstream codes DK, OL, PI). Every id form was confirmed against the OCD registry we already hold in the
  `openstates` database; none is invented. Senate posts are per state and class ("Senator, Class 1");
  several members can share one post (multi-member at-large). Territory and DC posts ignore the district
  number. A term with an unknown district (`-1`, 1,340 terms) keeps its state and gets no post.
- **A division id names a place, not a boundary.** `cd:7` of Washington means different geography before
  and after each redistricting; the membership dates say when. District geometry and crosswalks by
  vintage are a later story.
- **Idempotency:** unique keys `membership_term_key` (person, organization, role, start date, where the row
  has artifact evidence) and `post_organization_division_label_key`. Same bytes: nothing changes. A new
  upstream version updates an edited end date, party or post and moves the row's evidence to the newest
  artifact, and adds new terms; a term removed upstream is not retracted (accepted for now). House and
  Senate organizations are looked up (US `lower`/`upper`, exactly one each) and the load fails naming
  `load-openstates-organizations` if they are absent or ambiguous. An unknown jurisdiction code is
  reported (`terms_unknown_jurisdiction`) and the run is `partial`, never guessed.
- **`research-db coverage`:** a membership now counts for a Congress by its session id (old rule) or, with no
  session id, by term/Congress date overlap, the rule `expected_members` already used. Memberships are 100%
  for Congresses 108-119.
- **Live run:** migration applied; 45,535 terms staged, 45,535 memberships created, 690 divisions, 740 posts,
  0 unresolved BioGuide ids, 0 unknown jurisdictions; the immediate rerun changed nothing (45,535
  unchanged). Spot checks matched (Cantwell: WA-1 then five Senate terms; Pelosi: CA-5, CA-8, CA-12, CA-11).
  The vendored checkout is at `8a3c7e6` (2026-09-03).
- **LIS ids are not a gap.** Only senators have one (328 in all); every one of the 254 senators who served
  since 2003 has it. The earlier "fix the LIS crosswalk first" note was wrong.
- **Not done:** committee membership (`committee-membership-current.yaml` is current-only; committees
  exist as OpenStates organizations), social media, district offices, district geometry.

## Sources review, backup risk and branch cleanup (2026-09-19)

**Backups (fixed 2026-09-19).** The OpenDiscourse database (238 GB) had no working backup. The operator decided:
one copy only, rebuild the big layers from raw files, no point-in-time recovery. Built and proven:
`scripts/ops/backup_opendiscourse.sh` (nightly 03:30 from the operator's crontab; about 0.75 GB; writes to
`/mnt/storage/data-lake/backups/opendiscourse/`, never the root disk; exactly one copy, replaced only after a
verified new dump) and `scripts/ops/restore_drill.sh` (restores into a throwaway container and compares row counts;
**passed**). The database is also crash-safe for power cuts (fsync on, clean WAL replay, auto-start, healthy RAID 5);
a UPS is the remaining real protection. Details, open options and the power-loss findings:
`docs/storage-and-backup-plan.md`. Not yet done: the rebuild kit (below) that must exist before the rebuildable `stage`
duplicates (about 37 GB) may be dropped, and an optional off-machine copy (Google Drive via `rclone`, needs the
operator to sign in).

1. **Sources review.**   `docs/research/2026-09-19-chatgpt-sources-review.md` was evaluated and decided in
   `docs/adr/0004-source-catalog-and-tool-policy.md`: architecture unchanged; the source catalog (with a size
   estimate and a `verified_on` date per source) and the tool matrix in `reuse.md` become the acquisition map;
   the review's ~26 domains are catalog entries, not a build order; `censusdis` stays rejected as a dependency;
   the small disclosure and `pyCFR` repos are reference only; Parquet is at most a derived side cache after its
   own ADR; Prefect is not adopted (the review wrongly said we use it). Sequencing stays `v1-scope.md`.
   After the operator asked for less caution about tools, the tool positions were softened the same day: "evaluate and adopt if good" instead of "reference only", and a Parquet benchmark is planned because size is a real constraint (ADR-0004, revised).

**What we already have for "bill details and amendments".** Bill details: complete (every field of every
BILLSTATUS file is in `core.bill_source_record`; actions, sponsors, cosponsors, committees, subjects, summaries,
laws and related bills are typed). Amendments: the per-bill list is loaded (67,956, with sponsor and latest
action). **Not yet:** full amendment records and text (Congress.gov API), bill text (GovInfo BILLS), committee
report and hearing text, and typed CBO estimates and committee reports (already in the record).

**Branch cleanup.** Local and GitHub now hold only `main` (plus dependency-bot branches) and the parked
`wip/lake-registry-homelab`. Deleted: every branch whose PR was merged or whose content is on `main`, and every
AGY (Gemini) branch: 1.6 (`8805f93`), 1.7 (`32d8e1f`), 2.2 (`fe3847e`, refinement `385799b`), 2.3 (`324915d`,
`f33a430`), 8.2 (`ffeacd8`, refinement `e5994dd`) and `revert/agy-unsafe-merges` (`70f34e0`). Their merged
versions remain in `main`'s history (and were reverted in #26); the SHAs are noted only so a mistake can be
undone soon after (`git branch <name> <sha>` works while the commits are still in the reflog or on GitHub).
Nothing on those branches is wanted: AGY output is not trusted (rule 7 above). The dependency-bot PRs (#11,
#12, #14, #31) are automatic and untouched.

**Operator preferences (restated 2026-09-19; they apply to every session).** Keep the project organized: proper
folders and consistent file and command names. Use established libraries and upstream GitHub tools for
downloading and extracting data instead of writing our own; do not limit the tools we consider. Store all
downloaded data so nothing is lost (raw files immutable and checksummed, full records in the database). Every
ingestion run is monitored and tracked (`ingest.run`, `research-db loaded`, `coverage`, `congress-health`). Use the
BMAD process for software (spec first for anything M or larger). Do not use or trust Gemini/AGY output. Push code
to GitHub and merge our own PRs when CI is green. Keep the root disk free (it is small and holds the WAL); keep
data on the RAID volume; keep only one database backup. Explain results in plain language.

**Next steps, in order.**

0. **Folder and naming audit: done (2026-09-19)**, see `docs/layout-and-naming-audit-2026-09-19.md`.
   Fixed: tests no longer write into the real lake (autouse `DATA_ROOT` isolation), `lake.md` matches the lake
   and code, naming rules written in `conventions.md`. Needs the operator: move 109 test-fixture files out of the
   real `raw/` into `hold/`; repoint two legislators registry rows and drop the stray checkout `data-lake/`;
   untrack `.agent/` (Antigravity copy of the skills); commit or drop `docs/data-inventory-2026-09-19.md`.
   Debt found: FEC (20 GB) and 16 BILLSTATUS rows still point at `/mnt/storage`, so **FEC is not rebuildable from
   an empty `DATA_ROOT` yet** (the rebuild kit must close this); 96 stale `.lock` files; mixed verb and module names.
1. **Rebuild kit** (proof done for Congress 108 bills: identical to live, idempotent, see `docs/rebuild-proof-2026-09-19.md`; spec written: `_bmad-output/specs/spec-rebuild-kit/SPEC.md`; includes OpenStates restore and promotion per AD-8, and FEC as the last phase; next: build phase 1). (operator condition for dropping `stage` duplicates, and for portability): one documented,
   tested command sequence that downloads and ingests every loaded source from an empty `DATA_ROOT`; then a small
   project skill `opendiscourse-rebuild` that points agents at it. Commands are the portable part; skills only guide.
2. Story 9.6 (proposed number): expand `inventory/sources.yaml` into the source catalog described in ADR-0004
   and audit the existing Connectors against it. Change class M: spec with `bmad-spec`, then build.
3. Votes Connector (the legislator-vote proof slice `v1-scope.md` requires before expanding horizontally): first
   verify the House Clerk and Senate XML formats and the `unitedstates/congress` vote task against the live
   sites; join on BioGuide (House), LIS (Senate; every senator since 2003 has one) and ICPSR (Voteview). Spec
   with `bmad-spec` first.
4. Parquet benchmark story (size): compare Postgres and Parquet for `stage.fec_row` and ACS; adopt only as a
   derived layer if it wins.
5. Then, one Connector each: GovInfo BILLS text and PLAW, Congress.gov amendment detail and committee
   reports, typed CBO estimates and committee reports (from the stored records), committee membership.
6. v1.1 order stays FEC, disclosures, elections, crime; the review's extra domains wait for the operator's ranking.
7. **Skills and MCP review (not yet read):** `docs/research/2026-09-19-chatgpt-skills-mcp-review.md`, supplied by the
   operator; evaluate which skills or MCP servers are worth adding to the project, record the decision in an ADR.

**To resume in a fresh session:** "Resume OpenDiscourse. Read `docs/PROJECT-STATE.md` (start at 'Sources review,
backup risk and branch cleanup')."

## Large tables and database sizing (measured 2026-09-19)

Nothing is partitioned. Disk is not the constraint (2.0 TB free of 2.9 TB); speed is.
Static loaded sources (ACS, CBP, TIGER, PEP, DHC) stay as they are: no rewrite, no wipe.
`fact.acs_bulk_estimate` 36 GB heap + 63 GB indexes (usage unknown: counters are empty),
`stage.fec_row` 66 GB + 8.6 GB, `stage.cbp_row` 19 GB, `fact.business_pattern` 5.9 GB +
6.2 GB, `stage.tiger_feature` 10 GB, `core.geography_boundary` 10 GB. Stage copies that
duplicate loaded data (cbp, tiger, acs, about 37 GB) are rebuildable but not worth wiping.

Two clusters share this 125 GB / 40-core host: PostgreSQL 16 on port 5432 (`mlb`,
`govdata`; already tuned: `shared_buffers` 40 GB, `maintenance_work_mem` 4 GB,
`work_mem` 128 MB, 10 autovacuum workers) and PostgreSQL 17 on port 5434
(`opendiscourse`, `openstates`; still on defaults: `shared_buffers` 128 MB,
`maintenance_work_mem` 64 MB, autovacuum scale factor 0.2). Memory settings belong to a
cluster, not a database. The 17 cluster's `pg_wal` is on `/` (122 GB free), so
`max_wal_size` is capped at 16 GB. Proposed values, a dry-run memory budget and an
apply/revert path are in `scripts/ops/tune_postgres_17.sh` (dry run by default; only ever
writes to the 17 cluster; needs sudo to apply; `shared_buffers` and `max_worker_processes`
need a restart, the rest a reload). Not applied yet. The budget shows the 16 cluster alone
can theoretically exceed RAM if all 10 autovacuum workers use 4 GB at once; a
`autovacuum_work_mem='1GB'` on the 16 cluster would cap that (reload only; not changed).

Design points for ADR-0003 (Story 9.1), before the next large load: partition new large
tables by their natural slice (cycle/year/congress) so reload-one-slice is drop and
attach; stage rows are keyed jsonb at about 600 bytes each, too wide for the remaining
FEC volume, so use a compact layout.

**FEC staging is not the pas2 pilot the progress register describes.** `stage.fec_row`
holds `pas2` all 13 cycles (5.6M rows), `oppexp` all 11 (18M), `oth` all 13 (40.9M; 2024
alone 18.7M) and `indiv` only 2000-2016 (39M); **`indiv` 2018, 2020, 2022, 2024 are not
staged.** All 50 FEC artifacts are `downloaded`, none `loaded`, and no ledger detail
exists, so this staging is unattributed (possibly written by reverted code). Treat as
unverified: Story 9.3 must count it, and it may be wiped and re-staged (operator policy).

## What is already on disk (measured 2026-09-19)

Two lakes. The warehouse's own (`~/workspace/data-lake/opendiscourse`, 131 GB;
`config.data_root`) holds Census and OpenStates raw files. The legacy lake
(`/mnt/storage/data-lake/government`, 692 GB) is referenced by `inventory/` as
`legacy_cache_unverified`: usable only after verification against official sources.

| Need | On disk | Missing |
|---|---|---|
| Legislators / BioGuide | `congress/congress-legislators/` current + `legislators-historical.yaml` | nothing: Story 3.1 can start now |
| Bills, amendments | `congress/congress-data/<N>/` (unitedstates/congress layout) for Congresses 93-113 (108: 10.7k files, 112: 12.3k, 113: 8.5k, likely partial); GovInfo BILLSTATUS cache 108-119 per inventory | 114-117 in that layout; 119th BILLSTATUS incomplete (2,831 XML) |
| Roll-call votes | only the 118th (`congress/congress/data/118/votes`) | **108-117 votes are not on disk** (`congress_historical/*/votes` are empty); fetch with `unitedstates/congress` (both chambers) |
| FEC | `fec_bulk_data/`: `indiv` 13 cycles, `oth` 13, `pas` 13, `oppexp` 11 | no `cm`/`cn`/`ccl` (candidate/committee masters) found there; needed to link money to candidates |

Bills and votes are loaded together: bills are the parent that votes and
sponsorships attach to. The earlier "start with the votes table" only meant which
table to benchmark for the load strategy (Story 9.1), not to load votes alone.
Story 9.3 must inventory the lake the same way it inventories the database and
official manifests, so "have it" vs "need it" is a report, not a guess.

## Live database reconciliation (done 2026-09-19)

The live `opendiscourse` DB was stamped `b8c2f1d4e390` (a revision from the
reverted OpenStates promote, #22) and was physically at `a4f8c2e9b176`: it also
lacked the Story 1.6 evidence checks and Story 1.7's `artifact_version`.
Operator approved the reconciliation. Done in one transaction after read-only
pre-checks (all reverted objects empty; no rows violated the 1.6 checks):
dropped `core.membership.ocd_id` and `membership_ocd_id_idx` (0 rows had a value),
restored `identity_exception_kind_check` to `kind = 'voter'` (0 `membership`
rows), stamped `a4f8c2e9b176`, then `init-db` applied `b1e5c8a3d942`,
`d9e4f1a7b632`, `a3c7e9b1d254`. Live head is now `a3c7e9b1d254`;
`ingest.artifact` still has 2,555 rows.

## Story 3.1 live load (done 2026-09-19)

`research-db load-legislators` at upstream commit `8a3c7e6987f8`: 12,770
legislators, 12,045 new people, 89,527 new identifiers, 0 conflicts, 0 possible
duplicate people. Pre-existing rows verified unchanged by fingerprint (9,841
identifiers, 726 people). Rerun created 0 rows and no new artifact versions.
People now 12,771 (12,770 with a BioGuide id; 1 baseline person has none).
Every new identifier carries `source_artifact_id` and `source_run_id`.
The first load stored the two artifact `local_path` values as relative paths
(bug, fixed in code: paths are now absolute like other loaders). Operator approved
correcting the two rows to absolute paths; done, checksums re-verified, and a rerun
from another working directory reused them (still 2 artifact versions, 0 rows
created). Files live under `data-lake/opendiscourse/raw/congress/legislators/`
in the repo checkout (gitignored), the same root the other loaders use.

## Data completion plan and estimates (2026-09-19; estimates, not measurements)

What "complete" means for v1 and where each piece stands. Compute is cheap; the calendar time is
building Connectors, verifying against official manifests, and Story 9.3's coverage report.

| Area | Have | Need | Rough effort |
|---|---|---|---|
| Bills, actions, sponsors, Congresses 108-119 | **Done (Story 9.5):** downloaded from GovInfo, verified against its manifests, loaded | member terms (`core.membership` is still empty) | n/a |
| Roll calls and member votes, 108-117 | only the 118th on disk and loaded (1,827 roll calls, 473K votes) | fetch both chambers via `unitedstates/congress` (about 20K small files, polite rate: hours), Connector, 9.1 harness | hours to download, about 5M member-vote rows |
| FEC | all 50 archives downloaded (20 GB); staging holds pas2/oppexp/oth complete, indiv 2000-2016 | indiv 2018-2024 (largest cycles; not before compact layout and partitioning), `cn`/`cm`/`ccl` linkage files (small, not on disk), a reviewed join contract | about 40K rows/s measured, so 200M rows is roughly 1.5 hours once staged compactly; v1.1 |
| Epstein files | 794K files, 658 GB in `/mnt/storage/data-lake/government/epstein` (legacy, HOLD, inventory only) | its own spec first: sensitivity and access rules, no entity claims, phased (checksum registry, then text extraction, then search); HDD makes hashing 658 GB a multi-hour job | after the Congress core; needs operator decisions |

Downloads and loads can run in the background (`run_in_background`), one Connector at a time,
each passing the 9.1 harness, and only after the 17 cluster is restarted with the tuned settings.

## Next steps when resuming

1. Operator: `sudo systemctl restart postgresql@17-main` (applies `shared_buffers`,
   `max_worker_processes`, `pg_stat_statements`); then `CREATE EXTENSION pg_stat_statements`
   in `opendiscourse`. Optional: cap `autovacuum_work_mem` on the 16 cluster.
2. Rerun `scripts/bench/benchmark_load_strategies.py` (about 8 minutes) and refresh the ADR-0003
   tables with the tuned-settings numbers.
3. Story 9.3 coverage comparator: built (see "Coverage report"); use it after every backfill.
4. Bills, actions, sponsors, and (9.5b) full records, summaries, laws, related bills, amendments: done. Member terms and posts: done (Story 3.3). Next: votes (wrap `unitedstates/congress`), bill text, amendment detail, then typing the CBO estimates and committee reports already in the record. Each through a Connector with the harness. Full source list: `docs/data-source-map.md`.
4b. Remove the old fixed-path BILLSTATUS loaders listed under "Known debt" (move `coverage.py`'s `_bill_details` and the `congresshealth` check first).
5. Then: FRED/OpenStates redo (2.2, 2.3, 8.2), Treasury and FRED failures, FEC promotion.
6. Decide the `fact.acs_bulk_estimate` redesign (docs/performance-audit-2026-09-19.md) when Epics 5-6
   define real queries.

## Roadmap (also in `epics.md`, "Suggested next build")

1. Merge Story 1.7 (after the operator sees the review).
2. Story 9.1 load contract + harness, then 9.2 run ledger.
3. Story 3.1 BioGuide identity: **done and loaded live** (branch
   `feat/3-1-bioguide-identity`, spec `spec-3-1-bioguide-identity.md`); independent
   review fixes applied. Merged (#30).
3b. Story 3.2 politician-join gate: merged (#32). `person_join` gates on `fec.campaign_finance`,
   `disclosures.financial`, `elections.results`; all `blocked`. Identity is no longer
   the blocker: 1,532 people carry an FEC candidate id. Open: a reviewed join
   contract per source, and FEC cn/cm/ccl linkage files for committee-only rows.
   `research-db person-join-status` shows the gates.
3c. Story 9.2 run ledger: merged (#33) and applied live (2026-09-19): Alembic head
   `c8e2a4f6d915`, `person_join` gates synced to `catalog.dataset`. `research-db loaded`
   shows the legislators load (a rerun populated the ledger: 0 created, 12,770 people /
   97,319 identifiers already present; baseline rows re-verified unchanged). `ingest.run_target`
   + `ingest.loaded_coverage` view, `IngestionRun.record_target`, `code_version` = git SHA
   (`-dirty` for tracked edits) on every new run, `research-db loaded [--dataset]`.
   Only the legislators Connector records targets so far; migrate each loader as it is
   touched. The 286 existing runs stay unattributed (`code_version` NULL): not invented.
   Finding for 9.1: no table is partitioned; `fact.acs_bulk_estimate` 99 GB/281M rows,
   `stage.fec_row` 74 GB/102M, `stage.cbp_row` 22 GB. Reload-by-slice on those means big
   deletes and bloat unless new large tables are partitioned; ADR-0003 must decide.
4. Story 9.3 coverage comparator (merged); bills for Congresses 108-119 via the BILLSTATUS
   Connector, Story 9.5 (passes the 9.1 harness). Votes and terms still to do.
5. Redo 2.2 -> 2.3 (FRED) and 8.2 (OpenStates); fix Treasury and FRED failures.
6. FEC promotion after 3.1.

## Working rules for any agent

- Use `uv run` / `just check-fast` / `just check-db` (serial, no `-n`). A change is
  not done until both pass. Independent review before the operator merges.
- New sources are Connectors. No `if/elif` in `cli.py`, `plans.py`, `registry.sync`.
- Read artifacts via `repositories/artifacts.py` (`ingest.current_artifact`).
- No name-matching people; federal joins use BioGuide.
- `dlt` writes `stage` only. Bound SQL parameters only. No secrets in git.
- Tests ship with the change, including failure, idempotency, resume, provenance.

## Open questions

- Storage grows with every changed refresh (all versions retained). Need a safe rule
  to prune superseded versions no `core`/`fact` row references.
- Are the large fact/stage tables partitioned by year/cycle? Decides how cheap
  "reload one Congress" is.
- Portability: `inventory/` hard-codes local paths (`/mnt/storage/data-lake/...`);
  move to config and add a one-command bootstrap for outside users.
- Vote "impact" needs a methodology before any scorecard (part of the CAP-9 spec).
- Verify Story 1.6 and the data written by reverted code before building on them.
