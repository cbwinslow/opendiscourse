---
title: 'Resume an ACS/AHS archive run from its saved checkpoint'
type: 'feature'
created: '2026-09-30'
status: 'done'
route: 'dispatch'
review_loop_iteration: 0
baseline_commit: 'fe2c726df003fa629eda44fde4939d056ab9ef1a'
context:
  - '{project-root}/_bmad-output/specs/spec-housing-microdata-archive/SPEC.md'
  - '{project-root}/_bmad-output/implementation-artifacts/spec-acs-archive-run-ledger-reconciliation.md'
  - '{project-root}/docs/PROJECT-STATE.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** The archive ledger saves completed files and CSV members when a run stops, but an operator has no safe command to use that saved progress. Re-running the normal command makes the operator rely on implicit idempotency rather than an explicit, auditable resume.

**Approach:** Add a separate, explicit resume command that takes one prior archive run ID, validates its saved manifest and checkpoint, and starts a replacement run that skips already reconciled source members while retaining the original evidence and recording its relationship to the earlier run.

## Boundaries & Constraints

**Always:** require an explicit prior run ID and fresh `--approve-transfer`; rebuild the selection only from the saved approved manifest; use immutable current artifacts; preserve the old run and its checkpoint; record a new run with the prior run ID in its parameters; reconcile each resumed member before publication.

**Never:** alter, stop, or attach to the active managed archive service; accept a running, successful, wrong-dataset, missing-manifest, or malformed-checkpoint run; delete evidence or stage rows; infer a checkpoint from aggregate row counts; create a new dispatcher branch outside the existing archive module.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|---|---|---|---|
| Resume an interrupted run | Failed or partial ACS archive run has a saved manifest and completed members | New run names its predecessor, reuses retained artifacts, and stages only unfinished members | Existing rows remain unchanged |
| Unknown or ineligible run | ID is absent, another dataset, running, successful, or lacks a usable manifest/checkpoint | Refuse before network transfer or stage work | Explain which eligibility rule failed |
| Corrupt checkpoint | Completed member is not in the saved selected manifest | Refuse before transfer or publication | Preserve both the bad ledger record and evidence |
| Resume reaches completion | Remaining members reconcile | Publish only the fully reconciled selection | New run succeeds and retains predecessor link |

</frozen-after-approval>

## Code Map

- `src/opendiscourse_research/ingestion/acs_archive.py` -- owns the standalone command, manifest construction, per-member staging, validation, and archive-only checkpoint behavior; extend it rather than adding a central CLI dispatcher route.
- `src/opendiscourse_research/ingestion/base.py` -- owns durable run creation, parameters, checkpoints, and target evidence; reuse it for the replacement run.
- `src/opendiscourse_research/models/ingest.py` -- defines the existing run/target contracts; no schema change is expected if the predecessor link remains run parameters.
- `src/opendiscourse_research/repositories/source_status.py` -- must continue exposing the latest run and its checkpoint without confusing predecessor evidence with the resumed run.
- `tests/test_acs_archive.py` -- add command-level refusal and argument coverage without live transfer.
- `tests/test_persistence_foundation.py` -- add database-backed interruption, resume, idempotency, lineage, and cleanup coverage.

## Tasks & Acceptance

**Execution:**
- [x] `acs_archive.py` -- add a named resume entry point and validated checkpoint-to-archive reconstruction; stage only members proved complete in the prior run and record `resumed_from_run_id` in the replacement run.
- [x] `acs_archive.py` -- make member staging accept a bounded completed-member set without weakening header, checksum, capacity, or reconciliation checks.
- [x] `test_acs_archive.py` -- prove refusal happens before work for invalid run IDs and malformed saved state.
- [x] `test_persistence_foundation.py` -- prove an interrupted PUMS/AHS fixture resumes without duplicate source identities, retains both runs, and publishes only after every member reconciles.

**Acceptance Criteria:**
- Given a failed archive run with one completed member, when the operator explicitly resumes it, then the replacement run records its predecessor and does not re-stage that member.
- Given a valid but incomplete checkpoint, when remaining members finish, then the replacement run reconciles the full saved selection before publication.
- Given an invalid resume target, when the command is invoked, then it creates no new run, downloads no bytes, and stages no rows.
- Given the active managed archive service, when this code is developed and tested, then its process and live rows are not changed.

## Implementation Notes

## Spec Change Log

## Review Triage Log

- `medium, patch` — Member ledger lookup matched only the member-name suffix, so equal names in two artifacts can reject a valid checkpoint. Match the exact artifact ID embedded in the coverage key.
- `high, patch` — The validated current artifact can change before `evidence()` resolves it again, allowing completed members from old bytes to be skipped for new bytes. Carry and re-check the validated artifact ID and checksum through the replacement run.
- `high, patch` — Duplicate edge-case finding: the second current-artifact lookup must not silently replace the validated immutable artifact snapshot.
- `false` — Multiple replacement runs are not prohibited by the approved intent; each retains its own predecessor link and idempotent publication, so the claimed ambiguity is not a demonstrated defect.
- `medium, patch` — Saved manifest reconstruction did not revalidate its fields through the normal archive-selection rules. Revalidate it and require the reconstructed stable keys to agree with the saved selection.
- `medium, defer` — A zero-row member is accepted by ordinary staging but rejected as resumable. This is real, but whether an empty selected source member is a completed member or an invalid source needs an explicit publisher/data policy; retain the existing artifact-level nonempty guard.
- `false` — An absent completed member causes staging to fail before publication, and a known-member failure overwrites its replacement ledger row; the review did not demonstrate a published misleading replacement.
- `low, patch` — The success fixture could pass if completed rows were re-read as conflicts. Add a focused unit test proving a supplied completed member is not iterated.
- `low, patch` — Immutable-artifact drift has implementation guards but no direct refusal test. Add a focused test that makes the current artifact differ and proves no replacement run is created.
- `low, patch` — Missing retained stage rows has implementation guards but no direct refusal test. Add a focused test that proves the resumed checkpoint is rejected before replacement creation.

## Design Notes

The command requires `--resume-run UUID` rather than silently selecting a previous failure. An explicit identifier makes the restart reviewable and prevents an old, unrelated checkpoint from becoming the default. A new run preserves the original failed/partial run as evidence instead of rewriting history.

## Verification

**Commands:**
- `uv run pytest tests/test_acs_archive.py -q` -- expected: archive command and refusal tests pass.
- `just check-fast` -- expected: lint and fast tests pass.
- `just check-db` -- expected: database-backed resume and provenance tests pass without xdist.
