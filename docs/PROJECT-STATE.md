# Project state and handoff

Last updated: 2026-09-21 (official House and Senate votes are loaded and coverage-complete for Congresses 108-119), see "Session handoff" below (Stories 3.1, 3.2, 9.1, 9.2, 9.3, 9.5 merged; 9.5b lossless BILLSTATUS records and typed summaries, laws, related bills, amendments loaded live; 3.3 member terms, posts and divisions loaded live; sources review evaluated, ADR-0004; backup risk found, see "Stop-and-fix items"). Read this first when resuming, then `AGENTS.md`,
`_bmad-output/specs/spec-opendiscourse/SPEC.md`, and
`_bmad-output/planning-artifacts/epics.md`. If this file and code disagree, the
code and tests win (hierarchy of truth in `AGENTS.md`). Update this file when a
decision or story status changes.

## Session handoff (2026-09-19, end of day)

Done this session (all merged): folder and naming audit (#51, tests no longer write to the real lake, 109 fixture
strays moved to `<lake>/hold/test-fixture-strays-2026-09-19/`); rebuild-kit spec (#52); rebuild proofs (#53, #54:
Congress 108 bills, people, population estimates rebuild identical to live); ADR-0005 (#55, #56: order-independent
identity and names, reviewed by Fable and Codex). Codex review works again (`/codex:setup` shows ready).

State of things to know:
- **Nothing in the live warehouse was changed** by the proofs or ADR. The Stutzman duplicate is recorded in
  `inventory/identity_exceptions.yaml` (`applied: false`).
- **ADR-0005 progress (2026-09-19, later):** spec written (`_bmad-output/specs/spec-order-independent-identity/`, #58).
  Story 1 (identity fix, lock, Stutzman merge; spec `_bmad-output/implementation-artifacts/spec-10-1-identity-fix.md`,
  ignored by git) built: all three person writers resolve by any identifier under one lock
  (`repositories/people.py::resolve_person`, set-based in `promote_legislators`), conflicts go to
  `ingest.identity_conflict`, reviewed exceptions are read by loaders (`identity_merge.py`) and applied by
  `research-db merge-people [--dry-run]` (audit in `ingest.person_merge`). Live merge done, see the next bullet.
  **Story 2 built (2026-09-20, spec `_bmad-output/implementation-artifacts/spec-10-2-assertions-precedence-resolver.md`,
  applied to live 2026-09-20):** migration `b7e4c2a19d63` (expand only): `core.person_name_source`,
  `core.geography_name_source` (unique on entity, kind, dataset, vintage, `NULLS NOT DISTINCT`; evidence check: artifact
  OR payload, plus run), `catalog.attribute_precedence`, `catalog.name_display`, `name_source_id` pointers on
  `core.person` and `core.geography`, and guard triggers. `inventory/precedence.yaml` (synced by `init-db`,
  `precedence.py`) ranks the sources; `research-db resolve [--dry-run] [--entity person|geography]`
  (`repositories/names.py`, `sql/query/names/`) is the only writer of the displayed names and fails closed on an
  unranked dataset, kind or geography type. **Operator decision (2026-09-20): `core.person.full_name` shows the common
  name** (`display: [common, official]`); official is kept as an assertion and is the fallback. Guard scope is a
  decision, not an omission: the trigger applies to every role including the owner (it stops accidental writes, not a determined
  one: any session can `SET LOCAL opendiscourse.resolver = 'on'`). It has two rules: a change to `name_source_id` is always
  refused outside the resolver, and a change to the name columns is refused only for a row that already has a
  `name_source_id`, because the three geography writers still overwrite `name` until story 3 (which makes that rule
  unconditional). To delete assertions a resolved row points at, the wipe transaction sets that flag and nulls the
  pointer first. ADR-0005's column `UPDATE` revoke was not done: the app role owns the tables and no role can be
  created without a superuser. `merge_person` repoints a duplicate's assertions (colliding keys dropped and counted in
  `ingest.person_merge.counts`). No loader, no live data and no backfill changed: the tables are empty, so `resolve`
  changes nothing until stories 3 and 4 make loaders write assertions. Vintage is text ordered `COLLATE "C"`: loaders
  write zero-padded ISO forms (`2024`, `2024-09`). **Live apply (2026-09-20, operator approved):** `research-db init-db` at `a4d9e1c7b356` -> `b7e4c2a19d63`; people (12,770) and geography (49,742)
  fingerprints identical before and after, new tables empty, precedence synced (14 rank rows, 4 display rows), `resolve --dry-run` 0 changes;
  a nightly backup from 03:32 the same day exists. **Next:** story 3 (geography loaders, six writers incl. ACS `ingestion/census.py`), person loaders, backfill by rerunning
  loaders, kit verify.
- **Next, in order (original list):** (1) `bmad-spec` for ADR-0005 (done); (2) identity fix (done, see above); (3) then the rebuild kit
  (`_bmad-output/specs/spec-rebuild-kit/`), FEC as its last phase (needs a downloader; its 20 GB and 16 BILLSTATUS
  rows are registered under `/mnt/storage`); (4) OpenStates restore proof (10 GB retained dump) which also unlocks
  legislator terms (terms need OpenStates organizations).
- **Live change (2026-09-19, identity story):** migration `a4d9e1c7b356` applied to live (three new tables, expand only). The
  Stutzman exception was rehearsed with `merge-people --dry-run` on live (rolled back: 1 identifier, 0 sponsorships, 0
  memberships, 0 votes, as recorded), then applied: OCD id `ocd-person/21f03982-...` now belongs to `67e9e162...`;
  duplicate `b8b58549...` (Marlin Stutzman, OpenStates placeholder, metadata `canonical_baseline: openstates`, no other
  rows) deleted; audit row in `ingest.person_merge`. `core.person` is 12,770 and every person has a BioGuide id (this
  answers the "one person without BioGuide" open point). Nothing else in the warehouse changed.
- **Decided by the operator (2026-09-20):** `core.person.full_name` shows the common name ("Mike Lawler"); the official
  name ("Michael Lawler") is kept as an assertion beside it (`inventory/precedence.yaml`, person `display`).
  Reversing the choice is a precedence-file change (CAP-7), not a schema change.
- **Open, small:** `docs/data-inventory-2026-09-19.md` is untracked (written by an earlier session; commit or drop);
  `.agent/` is a tracked Antigravity copy of the skills (proposal: untrack); `data-lake/rebuild-proof/` (gitignored,
  42 MB scratch lake) can be deleted; the scratch Docker container `od-rebuild-proof` is stopped.
- Useful, saved: `sql/query/verify/*_fingerprint.sql` (`psql -v congress=108 -f ...`) compares a rebuild with live;
  proof method and results in `docs/rebuild-proof-2026-09-19.md`.
- Operator working style (stated this session): plain language, advice and a recommendation with every question,
  no jargon-heavy multiple choice; do routine engineering without asking; consult other models when unsure
  (Codex works; Fable reviewed ADR-0005).

**Resume prompt (after the identity story, 2026-09-20):** "Resume OpenDiscourse. Read `docs/PROJECT-STATE.md` (Session
handoff, bullet 'ADR-0005 progress'). Story 1 of ADR-0005 is merged and applied live. Story 2 (assertion tables,
`inventory/precedence.yaml`, resolver, write guard) is built; apply migration `b7e4c2a19d63` to live once merged. Next: story 3,
geography loaders write assertions (spec `_bmad-output/specs/spec-order-independent-identity/`, CAP-4). Use `bmad-build`.
`full_name` is decided: common name."
Working notes from story 1: run DB tests against one fresh throwaway container per full run
(`docker run ... postgis/postgis:17-3.5`, `OPENDISCOURSE_TEST_DATABASE_URL`), because reusing a database leaves
artifact history that breaks the downgrade tests; a change to `models/ingest.py` needs the migration head in three places in
`tests/test_persistence_foundation.py`; the `bmad-build` step files are rendered by
`uv run _bmad/scripts/render_skill.py`; three-reviewer review (blind, edge-case, verification-gap) found real bugs, keep it
for changes that touch live data.

## Operator backlog and priorities (2026-09-20)

Stated by the operator; work them in this order. Plain-language replies are mandatory (`AGENTS.md`, "Talking to the operator").

1. **Ingest data.** Votes for Congresses 108-119 first (wrap `unitedstates/congress`, both chambers; the Senate source is still an
   "idea", confirm its format), then bill text, committee membership, FEC. Every source: take **every field it offers**
   (rules and per-source checklists: `inventory/DATA-SPEC.md`, `inventory/fields/`). Unaudited sources are assumed incomplete
   (the operator says fields were dropped in the past without a reason); audit the loaded ones after votes.
2. **Names work, stories 3-5 of ADR-0005** (geography loaders, person loaders, backfill) only affect which name shows; do after votes.
3. **SQL out of Python strings.** Audit 2026-09-20 found about 186 lines of SQL in Python under `src/` (geography loaders about 85, `repositories/coverage.py` 57,
   `openstatesstage.py` and `votereconcile.py` about 33; migrations, tests and one-liners are fine). The geography part goes with story 3; then a small
   clean-up story plus a test that fails on new multi-line SQL strings. Also consider Postgres functions and triggers where they simplify.
4. **Later, on real data:** index placement (load first, index after, keep the indexes), data types, and benchmarks (`scripts/bench/`).
5. **Reusable installation and agent guidance:** every completed source must be runnable by a new user from an empty `DATA_ROOT`, using tracked commands and project skills. The shared skills already exist (`opendiscourse-connector`, `opendiscourse-provenance`, `opendiscourse-schema-change`, and `opendiscourse-testing`); the rebuild-kit spec requires the missing `opendiscourse-rebuild` skill. Add narrow source skills only where their upstream format has recurring traps (starting with GovInfo BILLS and FEC), and keep an install/source matrix. Evaluate MCP servers alongside skills: use MCP only for agent discovery, schema inspection, spot checks, and troubleshooting; deterministic Connectors remain the production downloader and loader. Congress and FEC MCP helpers may talk to those APIs. Do not run the official Census MCP: it requires its own Docker Postgres (`mcp_db`), which is not the warehouse. Census rows already in `opendiscourse` on port 5434 stay the source of truth. Trial community OpenStates MCP only in a sandbox with least-privilege credentials. Do not rely on unreviewed third-party skills or MCPs as the source of truth: a 2026-09-21 scan found no credible maintained source-specific skill set covering GovInfo, FEC, Census, and OpenStates.

## Votes loaded live: Congresses 108-119, both chambers (2026-09-21)

Migrations `d5a1f8c37e26` and `c8e2a5f1b937` applied to live (expand only); fingerprints of `core.roll_call` (1,827), `fact.member_vote`
(473,490) and `core.person` (12,770) were identical before and after, and the totals afterwards were exactly the old rows plus the new ones.
`research-db sync-votes --chamber house|senate --congress N ...` (repeat `--congress`; one flag per Congress) then loaded, from the official
Clerk and Senate.gov XML, each file kept whole as a retained artifact (19,854 files, 1,215 MB under `DATA_ROOT`):

| | Roll calls | Individual votes |
|---|---|---|
| House 108-117 | 13,268 | 5,735,595 |
| Senate 108-117 | 6,586 | 658,258 |

On 2026-09-21, the official 118th and 119th loads completed and enriched the partial OpenStates rows in place:

| Congress | House roll calls / member votes | Senate roll calls / member votes |
|---|---:|---:|
| 118 | 1,241 / 539,642 | 691 / 69,096 |
| 119 | 676 / 292,310 | 897 / 89,688 |

`research-db coverage --congress 118 --congress 119 --json` at 2026-09-21T08:35Z confirms all four roll-call counts equal their current official indexes, with no roll call lacking individual votes. The House run remains `partial` only because of the pre-existing 117th Letlow exception below; the 118th and 119th House coverage is complete. The 118th and 119th Senate run succeeded.

Known, all reported by the run and not hidden:
- One House entry is not a person we hold: `L000555` "Letlow" is listed Not Voting on the opening roll call of the 117th (Luke Letlow died
  before he was sworn in). The vote is kept whole in `core.roll_call_source_record`; the roll reads 6 typed of 7 Not Voting. It keeps the
  117th House run at "needs a look" (exit 2) until a reviewed-exception mechanism exists (deferred; this is its first real case).
- Senate roll 2003-262: the vote menu dates it 27 June, its own file 26 June (an upstream discrepancy).
- Senate roll 2020-216: the file's totals are blank but it lists 100 Not Voting entries.
- Speaker elections and procedural outcomes have no plain pass/fail: `result` is empty, the exact word is in `vote_result` (10 House in 109-117, 44 Senate).
- The full 108-117 House load took a bit over an hour (faster than the 5-hour estimate).

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
| Roll calls / member votes | 108th-119th both chambers, official Clerk and Senate XML (see "Votes loaded live") | 117th House Letlow `L000555` exception; committee votes are a later source |
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

This snapshot is 2026-09-19. Bills (Story 9.5) and memberships (Story 3.3) were
completed later that day. Official House and Senate roll calls for 108-119 were
completed 2026-09-21; see "Votes loaded live". Do not use the roll-call,
membership, or 108-117 bill figures below as current warehouse state.

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
- **Roll calls (superseded 2026-09-21):** this snapshot had only partial OpenStates
  118th/119th rows. Official Clerk and Senate XML for 108-119 are now loaded;
  see "Votes loaded live".
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

## Story 11.1: House roll-call votes from the Clerk's XML (built 2026-09-20, loaded live 2026-09-20/21)

Spec `_bmad-output/implementation-artifacts/spec-11-1-house-votes.md` (git-ignored). Command:
`research-db sync-votes --chamber house [--congress N ...] [--download-only] [--batch-size N] [--pace S]` (exit 0 clean, 1 failed and a rerun resumes,
2 loaded but something needs a look). The Senate (Story 11.2, next section) is the second entry of `ingestion/votes.py::VOTE_CONNECTORS`.

- **Code:** `providers/clerk.py` (listing and HEAD, paced), `ingestion/house_votes.py` (Connector, dataset `congress.house_votes`),
  `ingestion/house_vote_parse.py` (XML to the lossless record and typed rows; reuses `billstatus_record`, which gained an optional
  `list_tags`), `repositories/votes.py` + `sql/query/votes/`, migration `d5a1f8c37e26` (expand only; downgrade refuses while official
  rows exist), field checklist `inventory/fields/congress.house_votes.yaml`. `unitedstates/congress` was read for URLs and formats only.
- **Shape:** one retained artifact per XML file (`house-roll-<year>-<NNN>.xml`, about 15,600 files, roughly 1.3 GB). `core.roll_call_source_record`
  holds the whole record (one row per artifact; a row means fully loaded, plus `unresolved_bioguide_ids`, so a rerun retries unknown ids).
  `core.roll_call` gained the typed header and totals; `core.roll_call_party_total`; `fact.member_vote` gained `position_raw` and the party,
  state and printed name at the vote. New keys are `us-<year>-lower-<n>`, the form OpenStates rows already use, so an existing row is
  enriched in place (same `roll_call_id`); official time, question and result replace the provider's, and provider votes for people the
  file does not list stay (count differences are in the run result, not hidden).
- **Verified against the real Clerk (2026-09-20, disposable database, not the live warehouse):** the OpenStates key mapping holds on 5 of 5
  samples (same time, question and result). The whole 108th Congress loaded: 1,221 files (101 MB), 529,406 member votes, 0 unknown
  BioGuide ids, 0 count disagreements; stored records equal their XML (0 mismatches, `tests/test_house_votes_record_corpus.py`); a rerun
  downloaded and loaded nothing. Measured: about 13.5 minutes for that Congress (about 7 for the origin check, 4 to download, 8 to load, at 0.1 s
  pace; the origin check took about 0.34 s per file), so 108-119 is about 3 hours at 0.1 s and about 5 hours at the default 0.25 s.
  **Rerun cost:** every rerun still makes one paced HEAD per file (to see a refresh) and hashes each retained file, even when nothing
  changed; from those measurements a full 108-119 rerun at 0.25 s is about 2 hours (an hour or so at 0.1 s), and loading nothing.
  Use `--congress N` to rerun one Congress (about 10 minutes).
- **Findings:** (1) OpenStates' House votes are incomplete: for `us-2024-lower-28` it holds 340 of the 431 members the Clerk lists; the official load
  fills the gap. (2) With gzip accepted the Clerk answers HEAD with a 20-byte length; the client asks for `identity` (tested).
  (3) 2 of 286 sampled files have an action date in a different year than their folder, so the year comes from the URL. (4) Speaker elections
  have candidate names as votes and candidate tallies (kept as `position_raw`, position `other`, tallies in the record).
- **Live run:** done 2026-09-20 (108-117) and 2026-09-21 (118-119). Counts and the Letlow
  exception are under "Votes loaded live". `plans.yaml` was not changed because a plan needs a
  `plans.py` handler and the spec forbids touching `plans.py`. `research-db coverage` expects
  the Clerk's highest roll number per year, so a roll the Clerk lists but does not serve would
  show as a gap (it is also in the run result under `not_published`).

## Story 11.2: Senate roll-call votes from senate.gov's XML (built 2026-09-20, loaded live 2026-09-20/21)

Spec `_bmad-output/implementation-artifacts/spec-11-2-senate-votes.md` (git-ignored). Command: `research-db sync-votes --chamber senate`
(same options and exit codes as the House). It is the House Connector's base, not a copy: `ingestion/roll_call_votes.py` now holds the ten stages,
the ledger, resume, lock and result once; `house_votes.py` and `senate_votes.py` are small subclasses (listing, file naming, parser, save, member
identifier). What changed in the House tests and SQL: the migration head pin (four test files), the capacity-gate patch target (now the shared module), one new House test (the official `result` replaces a stale provider one), and in `roll_call_count_disagreements.sql` (Guilty / Not Guilty counted as yea / nay, any letter case) and `upsert_house_roll_call.sql` (`result` is now replaced by the official value, NULL included, no longer kept when the official word is not a plain pass or fail).

- **Code:** `providers/senate.py` (menus and per-file origin state), `providers/remote_roll.py` (shared `RemoteRoll` and error types; `clerk.py`
  re-uses them), `ingestion/senate_vote_parse.py`, `ingestion/senate_votes.py` (dataset `congress.senate_votes`), `repositories/votes.py`
  (`save_senate_roll_call`, shared `_save_roll_call`), `sql/query/votes/*senate*`, `lis_people.sql`, `link_senate_roll_call_bills.sql`,
  migration `c8e2a5f1b937` (expand only: 19 nullable `core.roll_call` columns for the document, amendment, tie-breaker and long-text fields, 3 on
  `fact.member_vote`; downgrade refuses while Senate detail exists), checklist `inventory/fields/congress.senate_votes.yaml`.
- **Shape:** 8,174 files for 108-119 (the 24 menus; about 0.2 GB), one retained artifact each (`senate-roll-<year>-<NNN>.xml`, saved as
  `<DATA_ROOT>/congress/senate_votes/<year>/vote_<C>_<S>_<NNNNN>.<sha>.xml`). The whole record is in `core.roll_call_source_record` (same table as
  the House). Senators join on the LIS member id through `core.person_identifier` namespace `lis` (328 senators loaded by `research-db load-legislators`, which reads the legislators YAML), never on names. A senator
  entry with a missing or unknown LIS id is not created, is listed in the result (`unresolved_lis_member_ids`, `(no lis_member_id) <printed name>`
  for a missing one) and the run is `partial`; no exceptions mechanism was built (none is needed so far: every id in a 287-file sample across all
  24 sessions resolves). The Vice President's tie-break is `core.roll_call.tie_breaker_by/_vote`, never a member vote. Guilty, Not Guilty and
  Present keep their word in `position_raw` with `position` = `other`. `core.roll_call.bill_id` is set from the document block when it names a
  bill (H.R., S., H.Res., S.Res., H.Con.Res., S.Con.Res., H.J.Res., S.J.Res.) that `core.bill` holds, by Congress, type and number; older files
  with no `document_congress` use the roll call's own Congress. It is re-run at the end of each sync so a bill loaded later gets linked.
  The column `core.roll_call_source_record.unresolved_bioguide_ids` also holds LIS ids for the Senate (kept the name; it has a column comment).
- **OpenStates match:** all 427 existing Senate roll calls (`us-<year>-upper-<n>`) equal the official menu's roll number of that calendar year, same
  day (checked 2026-09-20 against all 24 menus), so they are enriched in place. **Finding:** the OpenStates Senate times are 12 hours early for
  afternoon votes (it dropped the PM: `us-2023-upper-196` is 09:34 UTC, the official vote was 5:34 PM Eastern = 21:34 UTC); the official time
  replaces it for the 427 matched rows; other OpenStates Senate rows (any it adds later, until a file is loaded for them) keep the wrong time. Existing OpenStates member votes that the file also has are replaced by the official ones (evidence, party, state and name at the vote).
- **Origin quirks found live:** (1) senate.gov HEAD gives no `Content-Length` (identity) or the gzip length, so the client reads the size from an
  identity GET whose body it does not read; (2) 13 of the first 1,588 files (the largest, 60 KB and up) are served chunked with no length, so the
  client reads the body once and uses its length; (3) a missing file or menu is a 301/302 to an HTML "not available" page, so redirects are not
  followed and mean "not published". The size is checked again after download.
- **Verified against the real Senate (2026-09-20, disposable database, not the live warehouse):** the 118th and 119th Congresses: 1,588 files
  (46.5 MB), 158,784 senator votes, 0 unknown LIS ids, 0 disagreements with the menu, 0 count disagreements, 5 copied OpenStates rows enriched in
  place, 14 roll calls linked to the 4 copied bills; `research-db coverage` shows loaded equals the menu (118: 691 of 691, 119: 897 of 897);
  `tests/test_senate_votes_record_corpus.py` on all 1,588 files: 0 mismatches. The first run stopped `partial` on the 13 chunked files, the fix was
  tested, and the rerun downloaded exactly those 13 and reused the other 1,575. Time: about 19 minutes at 0.1 s pace for the first run (the origin
  check about 8, download and load the rest); a full 108-119 run is roughly 2 hours at the default 0.25 s pace, a rerun about 1 hour.
  15 of the 1,575 roll calls have a result that is not a plain outcome (Point of Order Well Taken, Veto Sustained, Decision of the Chair
  Sustained): `result` is NULL and `vote_result` holds the word, listed under `parse_problems`.
- **Result mapping:** `normalize_result` maps a positive ending (agreed to, confirmed, passed, adopted) to `pass` unless "not" stands directly before it (`fail`); rejected, failed, defeated are `fail`; anything else is NULL. Every `vote_result` in 1,883 files (the loaded 118th/119th and a 287-file all-era sample) was classified on purpose; the odd ones: Veto Sustained, Veto Overridden, Point of Order (Not) Well Taken, Decision of Chair (Not) Sustained, Objection Not Sustained, Not Guilty stay NULL (their meaning is not a plain pass or fail); Bill/Joint Resolution Defeated and Motion to Table Failed are `fail`; 15 rolls have no result at all.
- **Live run:** done 2026-09-20 (108-117) and 2026-09-21 (118-119). Counts are under "Votes loaded live".
  `plans.yaml` was not changed, as in 11.1 (a plan needs a `plans.py` handler and the spec forbids
  touching it). No party totals are stored (the Senate file has none and none are derived).

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
0b. **Order-independent identity and names (ADR-0005, accepted with changes; must precede the kit's verify step).**
   Rebuild proof found that people and geography names depend on which loader runs first, and that person identity
   does too (OpenStates matches by OCD id only, so loading legislators first would create up to ~722 duplicate
   people; live already has one, Marlin Stutzman, `b8b58549…` beside `67e9e162…`). Stories, in order: identity fix,
   lock and duplicate merge; assertion tables, precedence file, resolver, trigger; geography loaders (six writers,
   including ACS in `ingestion/census.py`); person loaders; backfill by rerunning loaders; kit verify. `full_name` shows the common name (operator, 2026-09-20). Stories 1 and 2 built.
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
4. Bills, actions, sponsors, and (9.5b) full records, summaries, laws, related bills, amendments: done. Member terms and posts: done (Story 3.3). Official House and Senate votes for 108-119: done (Stories 11.1 and 11.2). Next: GovInfo BILLS text (and PLAW), then amendment detail, then typing the CBO estimates and committee reports already in the record. Each through a Connector with the harness. Full source list: `docs/data-source-map.md`.
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
   Connector, Story 9.5 (passes the 9.1 harness). Member terms (3.3) and official votes
   108-119 (11.1, 11.2) are loaded. Next ingest: GovInfo BILLS text.
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
