# Voting repair: implementation plan

Spec: `SPEC.md` (this folder) (approved by the operator 2026-11-27).
Execution: one agent, in order, test first, one commit per task, PR, merge on green CI.

## Global constraints

- Alembic for schema; runtime SQL in `sql/query/`; bound parameters.
- Links come from official identifiers only (Congress, bill type, number). Never names or titles.
- A loader never deletes or overwrites a retained file.
- Gates: `just check-fast`; affected DB tests without `-n`; full suite in CI.

## Review focus

- A refreshed roll call whose official bill number changed keeps a stale link.
- A bill loaded after its roll call stays unlinked.
- A procedural label (JOURNAL, ADJOURN, MOTION, QUORUM) or another Congress's bill gets linked.
- An index build blocks writes on a live table.
- A failed backup mirror destroys the previous good copy.

## Batch 1

- [x] T1 (R12): `tests/conftest.py` gives database tests their own 300 s timeout.
      Proof: `tests/test_artifact_versioning.py` passes with no `--timeout` flag.
- [x] T2 (R1): `sql/query/votes/link_house_roll_call_bills.sql`, `link_house_bills()`,
      House `_finish`, `research-db link-vote-bills` (no network), upsert clears a link when
      the official number changes. Tests in `tests/test_house_votes_connector.py`.
- [x] T3 (R4): revision adds `member_vote_person_idx` and `roll_call_bill_idx` concurrently;
      same indexes in `models/core.py`. Check `scripts/render_baseline_ddl.py --check`.
- [x] T4 (R13): backup script keeps a second copy in `OPENDISCOURSE_BACKUP_MIRROR_DIR`.
      Operator decision: the server is the backup location.
- [x] T5: apply to the live warehouse (backup first), measure, record in `PROJECT-STATE.md`.

## Later batches (plan each when reached)

2. R2 Senate amendment links (read the parent-document fields; parent may not be a bill),
   R3 vote kind, R5 mismatches (the comparison in `roll_call_count_disagreements.sql`
   already counts Guilty/Not Guilty; start there), R0 review.
3. R7, R6, R9, R8, R11, R10. The unattended timer needs an operator-approved size limit.
4. Profiles and static pages.
5. R14-R18. R14: tools in use are Antigravity/Gemini, Claude, Codex, OpenCode; confirm from
   each tool's documentation which folders it reads before removing any.
