# Project state and handoff

Last updated: 2026-09-19 (Story 3.1 built, not yet applied to the live DB). Read this first when resuming, then `AGENTS.md`,
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
| People | 726 | BioGuide load (Story 3.1) not done; blocks politician joins |
| FEC | 102M rows in `stage.fec_row` | staging only; not promoted; blocked on 3.1; v1.1 |
| GovInfo BILLSTATUS cache | Congresses 108-119, unverified legacy | 119th missing 2,831 XML; re-fetch from official source |
| OpenStates | 10 ok, 5 partial, 3 failed runs | coverage unmeasured; promotion reverted |
| FRED | 135 ok, 6 failed (HTTP 400/500) | some series missing |
| Treasury yields | 29 ok, 24 failed | parser broke ("no recognizable rate table") |
| Census ACS/CBP/TIGER/PEP/DHC | loaded (ACS 281M rows) | no coverage check; most complete area |

No coverage measurement exists anywhere; Story 9.3 creates it.

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

## Live database drift (found 2026-09-19, blocks applying any migration)

`alembic_version` on the live `opendiscourse` DB is `b8c2f1d4e390`, a revision from
the reverted OpenStates promote (#22) that no longer exists in `migrations/`, so
`research-db init-db` fails with "Can't locate revision". The physical schema
also disagrees with the stamp: `core.membership.ocd_id` and the widened
`identity_exception_kind_check` (from `b8c2f1d4e390`) are present, but
`ingest.artifact` has no `artifact_version` column and still has the old
`(dataset_id, artifact_key)` unique key, i.e. the reverted Story 1.7 migration
`c5e2d1a4f783` is stamped but its changes are absent (its downgrade deletes
superseded artifact rows, so do not run it). Both reverted objects are empty
(0 memberships, 0 `membership` exceptions). Nothing was changed by the failed
attempt (fingerprints of `core.person` and `core.person_identifier` verified).
**Needs an operator-approved reconciliation before Story 3.1 can load live:**
drop the empty `ocd_id` column/index, restore the voter-only check, `alembic
stamp b1e5c8a3d942`, then `init-db` (applies `d9e4f1a7b632`, `a3c7e9b1d254`).
Record what is dropped here when done.

## Roadmap (also in `epics.md`, "Suggested next build")

1. Merge Story 1.7 (after the operator sees the review).
2. Story 9.1 load contract + harness, then 9.2 run ledger.
3. Story 3.1 BioGuide identity: **built and green on a fresh DB** (branch
   `feat/3-1-bioguide-identity`, spec `spec-3-1-bioguide-identity.md`); needs
   independent review, the live-DB reconciliation above, then `research-db
   load-legislators`.
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
