---
name: opendiscourse-connector
description: 'Add or migrate an OpenDiscourse data source through a Connector. Use when adding a provider, wrapping an upstream ingest tool, touching plans.py HANDLERS or run_plan(), cli.py dispatch, or registry.sync, or when the user mentions FRED, a new source, or CAP-2.'
---

# OpenDiscourse Connector

Read `AGENTS.md` and `_bmad-output/specs/spec-opendiscourse/SPEC.md` CAP-2 first.
Data SDD is `inventory/` (`sources.yaml`, `plans.yaml`, `contracts/`), not a new
PRD. Also load `opendiscourse-provenance` and `opendiscourse-testing`.

## When to use

- A new or migrated HTTP/source path
- Anything that would add a member to `HANDLERS` or an `elif` in `run_plan()`
  (`src/opendiscourse_research/plans.py`), `cli.py`, or `registry.sync`
- Wrapping `vendor/` instead of writing a scraper

## Do

- Search for a maintained project before writing acquisition code (`reuse.md`
  beside the spec). Wrap it; own evidence and canonical keys.
- Put provider-specific behavior in `src/opendiscourse_research/providers/`
  (HTTP only) or a Connector adapter.
- Lifecycle: discover → select → plan → extract → evidence → stage →
  normalize → validate → publish → checkpoint. Map onto existing modules:
  `providers/` HTTP, `IngestionRun` / `ingest.raw_payload`,
  `capacity.storage_preview`, stage COPY, `repositories/`, `feedback`.
- If the Connector protocol is not in code, do **not** invent it unless the
  active story is 2.1. Do not add a dispatcher branch as a shortcut.
- `docs/adding-a-provider.md` is stale where it tells you to branch
  `registry.sync`. Follow this skill and AD-2 instead.

## Do not

- Add source-specific branches to `cli.py`, `plans.py` `run_plan()` / HANDLERS,
  or `registry.sync`.
- Treat `IngestionRun` as a Connector. It is a provenance context manager in
  `src/opendiscourse_research/ingestion/base.py`.
- Write OpenStates dump tables; read `openstates_source` FDW only.
- Load FEC, disclosures, elections, or crime until BioGuide identity exists
  (Epic 3).
