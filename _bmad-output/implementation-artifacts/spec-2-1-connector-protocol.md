---
title: 'Story 2.1 — Connector Protocol'
type: 'feature'
created: '2026-09-14'
status: 'done'
route: 'oneshot'
review_loop_iteration: 0
context:
  - '{project-root}/AGENTS.md'
  - '{project-root}/.agents/skills/opendiscourse-connector/SKILL.md'
  - '{project-root}/_bmad-output/planning-artifacts/epics.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Adding a source still means growing `plans.py` `run_plan()` / HANDLERS. There is no typed Connector for the 10-stage lifecycle.

**Approach:** Add a `typing.Protocol` plus tests for discover → select → plan → extract → evidence → stage → normalize → validate → publish → checkpoint. Do not change schema, do not migrate FRED, do not add dispatcher branches.

</frozen-after-approval>

## Implementation Notes

- New module: `src/opendiscourse_research/ingestion/connector.py`. Do not edit `plans.py`, `cli.py`, or `registry.py`.
- `STAGES` tuple is the spine order. `Connector` is `@runtime_checkable`. `ConnectorContext` carries `source_id` plus adapter `extras`.
- `run_connector()` walks `STAGES` so tests prove order; FRED adapter is Story 2.2/2.3.
- Tests: `tests/test_connector.py` (no db marker). Incomplete objects are not Connectors; stages run in order; context is threaded.
- Public module docstring required.
- Review patches: typed context fields; checkpoint in finally; new-context threading tests; isinstance gate; Protocol `...` bodies; export from `ingestion/__init__.py`; spine CAP-2 path.

## Review Triage Log

- Untyped extras-only context — medium — true; added selected_ids, plan_id, artifacts, checksums, run_id, cursor, error.
- checkpoint skipped on failure — medium — true; finally always calls checkpoint.
- No feedback module in runner — low — rejected; in-process protocol walk is not long operator work.
- In-place mutation hid discarded returns — medium — true; recorder returns a new context.
- Import test first path segment — medium — true; now records full module names.
- Missing TypeError / source_id / STAGES alignment tests — medium — true; added.
- Protocol docstring bodies vs `...` — low — true; switched to `...`.
- No isinstance at runner boundary — medium — true; TypeError on non-Connector.
- Stale adding-a-provider.md — low — deferred; skill already calls it stale; spine now points at connector.py.
- Spec still in-progress / no package export — medium — true; exported; spec set done.
