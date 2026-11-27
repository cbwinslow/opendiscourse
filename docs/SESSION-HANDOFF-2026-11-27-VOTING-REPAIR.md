# Session handoff: voting repair (2026-11-27)

For the next agent session (Claude, Codex, Antigravity/Gemini or OpenCode). Read this whole file, then the
operating contracts in section 1, before changing anything.

## 1. Read first (operating contracts)

In this order:

1. `AGENTS.md` (`CLAUDE.md` only includes it). Includes the **mandatory reply style** for the operator.
2. `docs/PROJECT-STATE.md`, at least the top entries.
3. This file.
4. `_bmad-output/specs/spec-voting-first-redesign/SPEC.md` (approved design and fault register R0-R21) and
   `plan.md` beside it.
5. `_bmad-output/specs/spec-opendiscourse/SPEC.md` with `legislative-north-star.md`, `schema-invariants.md`,
   `v1-scope.md`, `reuse.md`.
6. `_bmad-output/planning-artifacts/epics.md` and
   `_bmad-output/planning-artifacts/architecture/architecture-opendiscourse-2026-09-14/ARCHITECTURE-SPINE.md`.
7. `docs/adr/0001` to `0006`.
8. Project skills: `.agents/skills/opendiscourse-{connector,schema-change,provenance,testing,rebuild}`.
9. `CONTRIBUTING.md`, `docs/download-congress.md`, `docs/storage-and-backup-plan.md`.

Precedence, highest first: current code and tests, migrations and schema, architecture and ADRs, active spec,
GitHub, agent memory, old chats, guesses.

## 2. What the operator wants (their words, 2026-11-27)

- "a database for all of the house and senate bills along with votes so we can track and build profiles on
  poliicians", plus all bills and OpenStates data synced, bill analysis (what each bill means and how it affects
  people), membership and votes for all politicians, campaign finance and donations, and investments (trades made
  before legislation passes).
- "ok yea lets do 1 [keep and repair] ... i want you to redesign everything that is broken and inneffecient."
- "dont worry about the backups. use the server for any backup needs. we may not need a big backup either"
- Tools in use: Antigravity/Gemini, Claude, ChatGPT Codex, OpenCode.
- "keep working and do what you want and improve things and fix all of this stuff.... and lmk when i can compact
  or start a fresh session."

## 3. Approved work order

1. Link House votes to bills, refresh federal data, automate the refresh.
2. Federal politician voting profiles.
3. Campaign finance.
4. Disclosures and trades, small trial first.
5. Bill explanations. State data after that.

This lifts the 2026-10-10 rule that money and disclosure work wait for Story 10.6. Epic 10 is paused, not
dropped. The identity gate (`person_join` in `inventory/sources.yaml`), a written source contract and a capacity
preview still apply to every new source.

## 4. Rules that are easy to break

- Never fabricate sources, citations or data. Say plainly when something is unverified.
- Never read, print or copy secret values. Refer to keys by name.
- Retained artifact files are evidence: never overwrite or delete one. Wiping untrustworthy derived rows is
  authorized; record what was wiped.
- No name matching of people. Federal joins use BioGuide. FEC, disclosure and election joins stay gated.
- OpenStates dump tables are read-only (FDW `openstates_source`).
- No market prices, no news product, no verdict words ("bribed", "insider trading", "lie"), no single score.
- Do not delegate to Antigravity/Gemini ("AGY"). The operator uses it themselves; agents do not hand it work.
- Merge your own PRs when CI is green (squash, subject ending `(#N)`).
- Do not spawn subagents unless the operator asks.
- Unattended (scheduled) downloads need an operator-approved size limit after a preview.
- Replies to the operator: plain answer first, explain terms, options with a recommendation, what happens next,
  never drop a risk or failed check.

## 5. Done this session

| PR | What |
|---|---|
| #145 | House roll calls link to bills (`sql/query/votes/link_house_roll_call_bills.sql`, `research-db link-vote-bills`); indexes `fact.member_vote_person_idx` and `core.roll_call_bill_idx` (revision `c7e2b94d5a13`, current head); second backup copy; DB tests get a 300 s timeout; restore drill fails on unexpected errors; backup leaves out `core.division_boundary` rows too |
| #146 | Dependency upgrades; no open Dependabot alerts afterwards |
| #147 | The official roll-call file wins over OpenStates copies; `research-db prune-provider-votes` |
| #149 | House sync reads the Clerk's new address `clerk.house.gov/evslegacy/` |

A further PR commits this file and updates `AGENTS.md`, `epics.md`, the spec, the plan and `PROJECT-STATE.md`.

Applied to the live warehouse (port 5434) and checked:

- Migration `c7e2b94d5a13`.
- 14,651 House roll calls linked before the refresh, all agreeing with Voteview's bill number (0 disagree).
  The other loaded roll calls name no bill (procedural or blank labels). The one Voteview row without a match
  (2023 roll 649) was the missing file below. After the refresh: House 14,662, Senate 2,046.
- Busiest member's full vote history (15,399 votes): 35 ms (a member history took 4.4 s before the index). Index size 417 MB.
- **Wiped 62 derived rows** from `fact.member_vote` (7,384,589 to 7,384,527). They came from artifact
  `openstates.legislation` / `federal-votes-119` and credited BioGuide G000606, whose House membership starts
  2025-11-12, with "not voting" on roll calls from 2025-01-03 to 2025-03-11. The official rows name G000551.
  Why OpenStates attributed them that way is not verified.

## 6. Data state

Measured 2026-11-27 unless noted. Database 537 GB: staging 398 GB (`stage.acs_pums_record` 286 GB, operator
keeps PUMS; `stage.fec_row` 74 GB), census and business facts 116 GB, maps 11 GB, bills/votes/people 9.1 GB.

- **Bills:** 194,367 (Congresses 106-119). 108-118 match the official source; 119 had 18,989 of 20,220; 107 was
  2 short (checked 2026-10-01). Text: none for 106-112; 113 13,751 of 13,757; 114-118 full; 119 22,036 of 23,697
  versions. Summaries 118 62%, 119 30% (whether the publisher has more is unverified).
- **Roll calls:** 23,413 (House 15,198, Senate 8,215) for 108-119 after the refresh; 7,394,356 member votes.
- **People:** 12,770; memberships 45,535; committee membership is current only. 554 of 556 voters in the 119th
  have an FEC identifier (1,532 people overall). Positions: yes, no, not voting, other ("other" includes Present
  and Speaker-election names).
- **OpenStates:** July 2026 snapshot in database `openstates`; about 1.45 M state bills, 1.19 M vote events,
  about 52 M person votes (estimate), data ends 2026-06-30, 77.1% of person votes linked to a person (2% sample).
  October dump downloaded, not restored. No state data promoted to `core`. Audit issue #100 / draft PR #107 paused
  (worktree `~/workspace/opendiscourse-story-1`).
- **FEC:** 102 files 2000-2024 retained (20 GB), no 2026; about 102 M unverified staging rows. The registry lists
  only `indiv`, `oppexp`, `oth`, `pas2` under `fec.campaign_finance`; `cn`, `cm`, `ccl`, `weball` are not listed.
  Person join blocked pending a reviewed contract.
- **Disclosures and trades:** nothing loaded. Needs a filer identifier bridge. From general knowledge, unverified:
  some filings are scans, values are ranges, filing can lag 45 days, and reuse has legal limits.
- **Bill understanding:** no chunks or embeddings; 17,640 CBO estimate records.

Known data oddities. The full tally comparison now disagrees on only the first two:

- 117th Congress 2021 roll 1 ("Call By States"): one member unresolved, BioGuide `L000555`.
- Senate 116th 2020 roll 216: 100 senators listed "Not Voting", official totals 0.
- Five House roll calls with zero totals and no positions (112th #327, #484; 113th #275; 114th #44, #300).

## 7. Refresh run at the end of this session

| Chamber | Result |
|---|---|
| House, 118th and 119th | 1,930 listed; 14 downloaded (13 new 2026 votes and 2023 roll 649), 1,916 reused; 6,067 votes written; 0 tally disagreements; 11 new bill links. Newest vote 2026-11-19 |
| Senate, 119th | 938 listed and downloaded; 41 new and 2 changed roll calls loaded; 0 tally disagreements. Newest vote 2026-11-20 |

- Roll 2023-649 had an earlier failed download ("Network is unreachable") and held OpenStates votes only (338).
  It now holds the 439 official votes.
- The first House attempt failed because the Clerk had moved its files (fixed in #149). At the old `/evs/` address:
  no yearly list, HEAD refused, no change date, reformatted XML, and status 200 for missing files.
- Every Senate file was downloaded again (28 MB, 19 minutes). The publisher's change date on the sampled file is
  2026-11-02 and the file kept version 1, so a re-dating by the publisher is the likely cause (not verified for
  all files). Check that the next run reuses them.
- The syncs took about 16 minutes (House) and 20 minutes (Senate). The House run checks every listed file's size
  and date one at a time. Relevant to R6.
- Not refreshed: Voteview (2023 roll 649 will link on its next sync), bills, bill text, legislators, committees.

## 8. Not done: fault register and next steps

Full definitions are in the spec (R19-R21 were found and fixed this session). Status after this session:

| Item | State |
|---|---|
| R0 full voting-path review | Open. Targeted work has already turned up R19-R21 |
| R1 House bill links | Done |
| R2 Senate amendment links (603, all name a parent document; parent may not be a bill) | Open |
| R3 vote kind (passage, amendment, procedural, nomination, treaty, election, other) | Open |
| R4 indexes | Done |
| R5 mismatches | Down from 64 to 2 disagreeing roll calls (section 6); record a decision on those two |
| R6 one `refresh-congress` command plus a systemd timer | Open. **Needs operator approval of a size limit** |
| R7 `load-legislators` needs a manual `vendor/` clone | Open |
| R8 Congress 120 starts 2027-01-03; commands default to 108-119 | Open, **dated**. Needs operator approval and manifest |
| R9 119th behind the publisher (bills, text, Senate votes) | Votes current. Bills and text not refreshed |
| R10 coverage report takes 5-6 minutes | Open |
| R11 stale "running" run (`census.acs_housing_archive`, 2026-10-01), unattributed runs | Open. `congress.congress_gov_bills` failed 2026-09-30 on a column that now exists; not rerun |
| R12 DB test timeout | Fixed; the full local DB suite has still never completed (CI runs it) |
| R13 second backup | Done on the root disk (separate from the RAID array holding data and main backup). Same machine, no off-site copy |
| R14 `.agent`/`.agents`/`.claude` duplicates (about 2,900 tracked files) | Open. Check each tool's documentation before removing |
| R15 large files (`cli.py`, `models/core.py`, `repositories/legislation.py`, `browser.py`) | Open |
| R16 lint/format/type backlog in tests | Open |
| R17 `pg_stat_statements`, `lz4` for new data, swap use (20 of 31 GB) | Open. Needs a quiet restart |
| R18 documents | Order updated in `AGENTS.md` and `epics.md`, Story 10.3 marked done. Open: close issue #118 after checking it, shorten `PROJECT-STATE.md`, roadmap gates in `inventory/dataset-roadmap.yaml` |

After R2-R11: profiles (dbt `mart` models for attendance, party agreement and split-party agreement, then static
HTML pages; definitions are in the spec), then campaign finance.

Recommended next action: R7 and R6 so data stays current (including a bill and text refresh), then R3 because
profiles depend on it.

Needs the operator: a size limit for unattended downloads (R6, after a preview); approval for Congress 120 (R8,
due 2027-01-03). Optional: an off-site backup copy; turning off the `debuggai` check.

## 9. Open GitHub items

PRs: #148 (Dependabot dev group), #129 (pre-commit update), #128 and #123 (docs, likely stale: compare with
`main` before merging), #107 (paused audit draft). Issues: #99-#105, #116, #118-#121.
The external check `debuggai/build_failed` fails on every PR because it builds a `web/` folder this repository
does not have. It is not a gate. Turning it off is an operator setting.

Older worktrees exist beside the repository (`opendiscourse-legislator-fields`, `-main`, `-snapshot-refresh`,
`-story-1`, `-test-db`). Their contents were not reviewed; do not delete them without checking.

## 10. How to run and verify

- `uv run research-db --help`; `just check-fast` (or `bash scripts/ci/check_fast.sh`). Check its exit code, not
  the tail of a pipe.
- DB tests: `uv run pytest tests/<file>.py` without `-n`; the throwaway server takes about 90 s to start.
- Baseline check: `uv run python scripts/render_baseline_ddl.py --check`.
- Votes: `research-db sync-votes --chamber house|senate --congress 119`, then `link-vote-bills` if needed.
- Backup `scripts/ops/backup_opendiscourse.sh` (cron 03:30, runs whatever is checked out in
  `~/workspace/opendiscourse`, so leave `main` checked out); drill `scripts/ops/restore_drill.sh <dump>`.
  Mirror folder is set by `OPENDISCOURSE_BACKUP_MIRROR_DIR` in `.env`.
- Nothing else is scheduled: **no data refresh runs by itself.**
- Server: 40 cores, 125 GB RAM, PostgreSQL 17.12 port 5434, spinning RAID 5 `md0`; `shared_buffers` 12 GB.
  Design verdict: keep PostgreSQL; DuckDB later for heavy analysis; no ClickHouse or graph database.

## 11. Harness notes (Claude Code on this machine)

A command-rewriting hook (`rtk`) sometimes makes parallel shell calls fail with "auto mode classifier gave no
verdict". Run one shell call per response; reissue a denied call exactly as quoted. `rtk proxy psql ...` avoids
rewrites.

## 12. Review status

No independent human or subagent review of this session's code. Automated reviewers: CodeRabbit and Greptile
commented on #145, Greptile on #147 (a timing bug in the vote precedence rule); the findings were verified and
fixed. CodeRabbit did not re-review the later commits and showed "skipping" on #147 and #149. Greptile left no
comment on #149.
