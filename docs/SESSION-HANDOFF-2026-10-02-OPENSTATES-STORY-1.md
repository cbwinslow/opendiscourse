# OpenStates Story 1: operator-requested stopping point

## Resume location

Worktree: `/home/cbwinslow/workspace/opendiscourse-story-1`.
Branch: `feat/openstates-audit-story-1`.
Base: `a6baee74d391742a73c6c3b1645fc5edf7c925d4`.
Issue: https://github.com/cbwinslow/opendiscourse/issues/100 under parent #99.

The operator requested a stopping point during implementation. Story 1 is **not
complete**. Resume this branch rather than starting again from the main checkout.
The main checkout has unrelated Congress/FEC and skill changes owned by another
session; preserve them. No source database, FDW, warehouse schema, canonical row,
FEC-transfer or person-link changes were performed in this work.

## Read first

1. `AGENTS.md` and `docs/PROJECT-STATE.md`.
2. `_bmad-output/specs/spec-fec-reproducible-ingest/stories/1-openstates-snapshot-audit.md`.
3. `_bmad-output/specs/spec-openstates-political-core/source-mapping.md`.
4. `docs/audits/openstates/2026-10-02/README.md` and `run-02/report.md`.

## Evidence retained

The read-only pass inventoried 84 tables, four extension views and 41 key-allocation
sequences: 129 relations, 761 scalar columns and 366 nested path/type entries
including supplementary classification evidence. Public civic entities number 38;
the FDW reader exposes 11 tables. Original evidence and scoped retries are retained
separately; checkpoints remain on disk and are gitignored rather than deleted.

Identity observations: 22,702 people, 722 with BioGuide, 21,980 without, zero
BioGuide values shared across different people and 659 repeated-name groups.
Missing BioGuide for state/local officials is not itself a source defect. No
cross-provider person link was created.

Executive/local evidence: 58 executive organizations, 70 Governor membership
records and 1,631 Mayor membership records. These are source record counts,
not complete nationwide coverage or distinct-officeholder counts.

The registered `data-2026-07` dump's actual streaming SHA-256 and byte count were
independently verified: `e4b8eb6d40d2da768074dab29bbf0d6949b8f24a50d75c5807669edcee5af78c`,
10,711,908,617 bytes. See `data-artifact-verification.json`. The ingest run ledger
has no `openstates.dump` restore entry; matching retained bytes do not prove
which archive produced the database. Never fabricate a restore attestation.

All four original query timeouts have later successful supplementary measurements.
The last personvote-to-voteevent check succeeded with zero unresolved references
using transaction-local `work_mem=256MB`, a 180-second statement limit and a
five-second lock limit. Host memory availability was checked first. See
`retry-personvote-event-reference-memory.json`; no persistent setting changed.
These independent observations are not a verified shared-snapshot baseline.

## Verification and review

Before the second correctness pass: `just check-fast` passed 671 tests;
`just check-db` passed 398 tests. Focused tests then passed 18 unit and four
PostgreSQL tests. Those results do not automatically verify later edits.

Three independent reviewers completed review. Every finding and its verdict is
recorded in the story's Review Triage Log. Current corrective work addresses
consistent exported snapshots, effective row visibility, recomputed/separated
fingerprints, tagged array/object paths, reader column/type coverage and aliases,
approval-evidence inputs, and actual identity/privacy tests. Check the final
stopping-point verification below before relying on current code.

## Completion gates still open

- Establish verifiable restored-artifact lineage; file integrity alone is insufficient.
- The semantic decisions were accepted on 2026-10-04 and written into
  `_bmad-output/specs/spec-openstates-political-core/source-mapping.md`.
  `mapping-review.json` is still a field proposal: `approved` is false and no
  field has a review time. Semantic acceptance is not field sign-off.
- Parent-derived coverage was measured into `parent-derived-coverage.json`
  (no query failures). It is not an approval, and a missing link is not a
  publisher zero. Jurisdiction and session groups in that file come from a
  second read-only query.
- Qualify legacy untagged nested paths; literal object keys named `[]` and array
  steps must not collapse in any approved new baseline.
- Verify baseline/resume behavior and the exact source/reader coverage contract
  on a fresh consistent tagged run. The full fast and database gates have not
  been rerun on the latest corrections.

Do not close #100, begin the schema/promotion stories, broaden reader access,
transfer FEC bytes or enable person joins based on this progress checkpoint.

## Next session

Stopping-point verification: after the review corrections, 19 focused unit tests
and eight isolated PostgreSQL tests passed. They exercise concurrent snapshot
consistency, actual identity SQL, restricted-sampling protection, tagged paths,
date precision and row filtering. Ruff and whitespace checks passed. One
disposable-container startup attempt timed out; the subsequent focused database
run passed. Full fast/database gates must run again before completion or merge
because the previous 671/398 totals precede these corrections.

The stopping-point code includes exported consistent snapshots, visibility guards,
recomputed/separate fingerprints, tagged paths, reader-column/type/alias comparison,
explicit review/restore evidence inputs, concrete mapping transformations and
precision-aware text-date profiling. These improvements have not been followed
by a new consistent/tagged live audit. No restore attestation was supplied. Semantic mapping was accepted on
2026-10-04; the field matrix is still unapproved. Parent-derived coverage has a
measured file and is not an approval.

Resume the approved Story 1 implementation, finish its corrections and coverage,
run focused checks followed by the required gates, then review the final change.
Keep immutable observations separate from newly derived/reviewed outputs.
