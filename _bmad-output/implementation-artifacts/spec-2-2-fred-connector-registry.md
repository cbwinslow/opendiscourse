---
title: 'Story 2.2 — Registry without HANDLERS if/elif'
type: 'feature'
created: '2026-09-14'
status: 'done'
route: 'oneshot'
review_loop_iteration: 0
context:
  - '{project-root}/.agents/skills/opendiscourse-connector/SKILL.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** FRED still runs through `plans.py` `run_plan()` `if handler == "fred_core"` and the `HANDLERS` set, so adding a source still means editing a god module.

**Approach:** Add a Connector handler registry. Register FRED there. `run_plan` looks up Connectors by handler; `fred_core` leaves `HANDLERS` and the elif chain. Do not remap discover/index vs observations (Story 2.3). No schema change.

</frozen-after-approval>

## Implementation Notes

- `ingestion/connectors.py`: `register` / `get` / `handlers`. Builtin load registers `FredCoreConnector`.
- `FredCoreConnector` in `ingestion/fred.py`: passthrough stages; `publish` calls existing `ingest_manifest`.
- `plans.py`: `HANDLERS` without `fred_core`; `validate_plans` accepts `HANDLERS | connectors.handlers()`; `run_plan` uses `get(handler)` then remaining elifs.
- Tests: FRED not in HANDLERS; validate_plans empty; `run_plan` source has no `fred_core` elif; connector satisfies Protocol; publish uses ingest_manifest (mocked).
