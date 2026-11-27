---
title: Voting-first repair and redesign
status: approved (operator, 2026-11-27)
created: 2026-11-27
---

# Voting-first repair and redesign

## Intent

The operator wants to understand bills, see how every politician voted, and later connect
that to money and trades. Voting comes first. The warehouse already holds most federal
votes but offers no way to use them. Keep the existing project, and redesign whatever is
broken or inefficient (operator, 2026-11-27).

## Goals

1. A House or Senate roll call that names a bill is linked to that bill.
2. One member's full voting history is returned in under 0.5 s (warm cache).
3. Federal data refreshes on a schedule and says plainly when it fails.
4. Every House and Senate member has a profile whose numbers drill down to the official vote.
5. Every fault in the register below is fixed or has a recorded decision to leave it.

## Non-goals (this spec)

Campaign finance, disclosures and trades, bill explanations, state legislators, Census and
district work (Epic 10 paused). Each gets its own spec, in the 2026-11-27 order.

## Anti-goals

- No rewrite, no new database.
- No opaque score and no verdict label.
- No joining people by name.
- No retained source file overwritten or deleted.
- A vote on an amendment or procedure is never shown as a vote for or against the bill.

## Constraints

`AGENTS.md` applies: Alembic for schema, bound parameters, SQL in `sql/query/`, provenance on
every derived row, capacity gate fails closed, tests ship with changes.

## Approaches

| Approach | Trade-off | Result |
|---|---|---|
| Keep and repair in place | Some untidiness remains for a while | **Chosen** (operator, 2026-11-27) |
| New slim repository, copy voting parts | Re-testing and rewiring before anything new appears | Not chosen |
| Full rebuild | Highest cost; repeats solved problems | Not chosen |

## Fault register

Measured 2026-11-27 on the live warehouse unless stated. The review was targeted, not
line by line; work item R0 extends it.

| ID | Fault and evidence | Redesign | Done when |
|---|---|---|---|
| R0 | Only a targeted review exists | Read the voting path (acquire, parse, load, link, report) end to end for correctness and speed; add findings here | Findings recorded |
| R1 | 0 of 15,185 House roll calls have `bill_id`. 14,651 of 15,148 with `legislative_number` match a loaded bill; the other 497 are JOURNAL, ADJOURN, MOTION, QUORUM | `sql/query/votes/link_house_roll_call_bills.sql` beside the Senate query, run by `sync-votes`; match Congress, bill type and number only | All bill-naming votes linked; rerun changes nothing; difference from Voteview's 14,652 explained |
| R2 | 603 Senate amendment votes are unlinked; all carry a parent document number | Link where the parent is a loaded bill; vote kind stays "amendment" | Each linked or listed with a reason |
| R3 | No stored vote kind | Versioned rule from official question text: passage, amendment, procedural, nomination, treaty, election, other | Every roll call classified; unmatched text lands in "other" and is reported |
| R4 | `fact.member_vote` has no index leading on `person_id`: 4.4 s, 0.14 s on an indexed temporary copy (417 MB) | Alembic index `(person_id, roll_call_id) INCLUDE (position)`, built concurrently; index `core.roll_call(bill_id)` | Goal 2 met on live data |
| R5 | 63 House roll calls (117th-119th): yes/no agree, total positions differ by one. One 116th Senate roll call: yes/no agree, 100 positions beyond the totals. Five House roll calls have zero totals and no positions | Check each cause against the chamber source; fix parser if ours, otherwise record as a known publisher difference | None unexplained |
| R6 | Newest votes 2026-09-17, newest bill action 2026-09-21; no scheduled refresh | One `refresh-congress` command running the existing syncs in dependency order, then links and checks; resumable; systemd timer; visible failure | Two unattended runs succeed |
| R7 | `load-legislators` alone depends on a manual `vendor/` clone | It acquires its own files like other syncs | Refresh needs no manual step |
| R8 | Congress 120 starts 2027-01-03; commands default to 108-119 | Open 120 with manifest and capacity preview, with operator approval | New members and votes load |
| R9 | 119th is behind the publisher: 1,231 bills, 1,661 text versions, 41 Senate votes (live check; counts grow) | Closed by R6; reconcile after first refresh | Coverage report matches or names each gap |
| R10 | Coverage report took several minutes | Profile first; likely cache publisher counts | Cause recorded; under 1 minute or reason kept |
| R11 | A run from 2026-10-01 still says "running"; 286 of 350 runs are unattributed | Mark dead runs failed; voting loaders record targets | No stale runs; refresh runs fully attributed |
| R12 | DB tests error locally: test server setup took 109 s against a 60 s limit. With 420 s the two affected files tried pass (55 tests). CI on `main` passes. Full local DB suite not completed | Give server startup its own limit, or reuse a running test server | `just check-db` completes locally |
| R13 | Backup, database and raw files share array `md0` | Second copy off this array | Restore drill from that copy passes |
| R14 | `.agent`, `.agents`, `.claude` hold about 2,900 tracked files, largely the same skills | Operator names tools in use; remove unused copies | One source per tool in use |
| R15 | `cli.py` 1,989 lines, `repositories/legislation.py` 1,525 | Split by area when touched, behaviour unchanged, tests first | New voting code lands in focused modules |
| R16 | Lint covers `src` only; 36 findings with tests, 137 files unformatted; `ty` 1,015 diagnostics, unreviewed | Format and lint tests in a separate mechanical change; decide on `ty` after sampling | Gate covers `src` and `tests` |
| R17 | `pg_stat_statements` approved, not enabled; TOAST compression `pglz`; 20 GB swap in use | Enable at a quiet restart; set `lz4` for new data; find swap user | Applied or declined with reason |
| R18 | `AGENTS.md` and `epics.md` state the old order; Epic 10 status stale; `PROJECT-STATE.md` is about 1,400 lines | Update order; shorten state file, move history to an archive file | Documents agree |
| R19 | An OpenStates load could overwrite official votes and left 62 votes crediting a member not yet serving | Official file wins (#147) | Done 2026-11-27; 62 rows wiped |
| R20 | The restore drill passed while a link failed to restore | Leave out `core.division_boundary` rows; drill fails on unexpected errors (#145) | Done; drill passed 2026-11-27 |
| R21 | The Clerk moved its files; House sync failed | Read `/evslegacy/` (#149) | Done 2026-11-27; the address may be retired by the publisher |
| R22 | `sync-committee-membership` was fixed to the publisher's 2026-09-03 commit, so a refresh could not change anything | Follow the latest commit and record it on the run, as `load-legislators` now does | A run records the commit it read |
| R23 | A corrected start date added a second term and kept the old one: 42 members showed two overlapping terms after the 2026-11-27 load | Remove an unlisted term only when a listed term of the same member and chamber overlaps it, and name it on the run | A load leaves no unlisted overlapping term |

Known inefficiency deliberately deferred: about 398 GB of staging (raw JSON census and
finance rows). Finance is redesigned in its own spec; the 2026-10-10 PUMS decision stands.
The two schema paths (numbered `sql/` bootstrap, then Alembic) stay unless R0 finds harm.

## Profiles

Built in the existing dbt project as `mart` models over `core` and `fact`, rebuilt after
each refresh.

- **Identity and service:** name, official ids, party, state, district or class, terms.
- **Vote history:** date, chamber, question, vote kind, position, bill, official source link.
- **Attendance:** share of recorded roll calls in which the member has a position other than
  "not voting". "Present" counts as attending. Only roll calls listing the member count.
- **Party agreement:** share of the member's yes/no votes matching the majority of their
  party's yes/no votes on that roll call. Ties and elections excluded. No figure where there
  is no party majority to compare with (for example a lone independent).
- **Split-party agreement:** the same, only where the two major parties' majorities differ.
- **Legislation:** sponsored and cosponsored bills, with subjects and latest action.
- **Committees:** current seats, labelled current only.

Each metric carries a version, its definition, its denominator and the data date. Missing
coverage is shown as missing: no full text before the 113th Congress, partial summaries for
the 118th and 119th.

**Viewing (proposed, not yet confirmed):** static web pages generated from the marts, with a
searchable member list and one page per member. They open locally with no server and can be
published later. A live web application is more work and not needed to read profiles.

## Order

1. Safety and footing: R13, R12.
2. Voting correctness and speed: R0, R1-R5.
3. Freshness: R6-R11.
4. Profiles and pages.
5. Tidy-up: R14-R18, in small separate changes. R18's order update comes first.

## Left to the builder

Table and module names beyond those given, page layout, timer frequency (suggested daily
while Congress sits), and how failures are shown.

## Needed from the operator

1. Approval of this design, including the page format.
2. A destination for the second backup (another machine, drive or cloud).
3. Which AI coding tools are in use (R14).
4. Approval of a size limit for unattended refresh downloads (R6), after a preview.

## Status, 2026-11-27 (end of first repair session)

Done: R1, R4, R12, R13, R19, R20, R21. R5: 64 disagreeing roll calls fell to 2 (117th 2021 roll 1, one unresolved
member; Senate 2020 roll 216, publisher totals 0). R9: votes current (House to 2026-11-19, Senate to
2026-11-20); bills and text not refreshed. R18: order update done in `AGENTS.md` and `epics.md`; the rest
open. Open: R0, R2, R3, R6-R8, R10, R11, R14-R17. Detail: `docs/SESSION-HANDOFF-2026-11-27-VOTING-REPAIR.md`.
