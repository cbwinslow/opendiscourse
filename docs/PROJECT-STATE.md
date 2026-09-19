# Project state and handoff

Last updated: 2026-09-19 (Stories 3.1, 3.2, 9.1, 9.2 merged; 9.3 built (PR pending); 3.1 and 9.2 live; performance audit done). Read this first when resuming, then `AGENTS.md`,
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
| Congress bills | 118th, 119th only (37,373) | 10 more Congresses needed (108-117) |
| Roll calls / member votes | 118th-119th only (1,827 / 473,490) | 108-117; Senate source is "idea" |
| People | 12,771 (12,770 with BioGuide; loaded 2026-09-19, Story 3.1) | 1 baseline person has no BioGuide; politician joins still gated (Story 3.2) |
| FEC | 102M rows in `stage.fec_row` (pas2, oppexp, oth complete; indiv 2000-2016 only; unattributed, see above) | staging only; not promoted; person join gated (3.2): needs reviewed contract + cn/cm/ccl files; v1.1 |
| GovInfo BILLSTATUS cache | Congresses 108-119, unverified legacy | 119th missing 2,831 XML; re-fetch from official source |
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
not extend): `legvalidate.BILLSTATUS_ROOT` and its users (`legarchive`, `govbackfill`,
`legload`, `legreconcile`, `govplan`), `audit.py` `ROOTS`, `ingestion/fec_bulk.py`
`LEGACY_ROOT`. `research-db coverage` now finds downloaded zips through the artifact
registry instead of a fixed path.

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
| Bills, actions, members, Congresses 108-117 | GovInfo BILLSTATUS legacy cache 108-119 (`/mnt/storage`, unverified); 118-119 loaded (37K bills) | verify against GovInfo manifests, fetch the 119th's 2,831 missing XML (28 MB), load 10 Congresses | loads about 3 min per Congress at the measured ~110 bills/s; verification and Connector work dominate |
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
4. Backfill Congress bills/actions/members, then votes, through Connectors with the harness.
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
4. Story 9.3 coverage comparator; backfill Congresses 108-119 via Connectors, each
   passing the 9.1 harness.
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
