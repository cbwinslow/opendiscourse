---
title: 'Story 2.3 — Migrate FRED end-to-end'
type: 'feature'
created: '2026-09-17'
status: 'done'
route: 'oneshot'
review_loop_iteration: 0
context:
  - '{project-root}/.agents/skills/opendiscourse-connector/SKILL.md'
  - '{project-root}/.agents/skills/opendiscourse-provenance/SKILL.md'
  - '{project-root}/.agents/skills/opendiscourse-testing/SKILL.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** FRED observations already run as a Connector, but discover/index still goes through `registry.sync`'s `if "fred"` branch and CLI source gates, so the e2e migration is incomplete and agents still copy that dispatcher.

**Approach:** Wire existing FRED metadata functions into `FredCoreConnector.discover`. Route `registry.sync` FRED catalog/index/full through `run_connector` instead of a source elif. Keep discover/index vs observations split; observations stay gated by plan `fredcore` + `core_fred_series.yaml`. No schema change. No Connector v2.

</frozen-after-approval>

## Implementation Notes

Landed: `FredCoreConnector.discover` calls `index_batch` / `sync_fred` / `sync_fred_full` / `preview_fred_full` when extras request it; sets `phase=discover` so `publish` skips `ingest_manifest`. `registry.sync` FRED path uses `run_connector` and no longer imports those functions. Plan `fredcore` still observations-only. Review patches: skip publish when `discovery` is present; per-path counts; `adding-a-provider.md` Connector wiring; extra no-db tests. `just check-fast` 128 passed.

## Review Triage Log

- registry.sync still has `if "fred"` — false — source fan-out remains for acs/census/bls too; FRED provider calls moved into the Connector; generic registry is not Story 2.3.
- adding-a-provider.md still said add `if` in registry.sync — medium — true; rewrote step 6 to register a Connector.
- full/preview/refresh/current-snapshot untested — medium — true; added no-db tests.
- epics/README still listed 2.3 as next — low — true; marked done.
- `_discovery_count` ranking — low — true on hypothetical payloads; set count per discover branch from the field that path means.
- registry index test mocked `run_connector` so extras drift could ingest — medium — true; added real-connector + `index_seconds` + discover-failure tests.
- `phase == "discover"` magic skip — low — true; skip also when `discovery` is in extras.

Reuse, do not rewrite: `providers.fred.index_batch`, `browser.sync_fred` / `sync_fred_full` / `preview_fred_full`, `ingestion.fred.ingest_manifest` / `ingest_series`. Provenance stays `IngestionRun` inside `ingest_series`.

- Discover-only extras (`index_pages` / `index_seconds` / `full` / catalog refresh) set `extras["phase"]="discover"` and `extras["count"]` so `publish` must not call `ingest_manifest`.
- Plan/bootstrap path has no those extras: `discover` no-ops; `publish` still `ingest_manifest` (priority/category from `parameters`).
- Preserve `registry.sync` return shape and the early return when FRED indexing is requested (other sources skipped). Keep CLI flags; do not add `if "fred"` in `cli.py`.
- Do not ingest indexed series. Do not add `fred_core` to `HANDLERS`. Leave `ingest fred` (single series) as-is.
- Tests: extend `tests/test_fred_connector.py` (no db) for discover vs publish split and `registry.sync` without a FRED elif to `index_batch`. Existing FRED tests must pass.
