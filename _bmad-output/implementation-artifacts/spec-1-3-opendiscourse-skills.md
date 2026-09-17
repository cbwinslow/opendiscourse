---
title: 'Story 1.3 — OpenDiscourse skills'
type: 'chore'
created: '2026-09-14'
status: 'done'
route: 'oneshot'
review_loop_iteration: 0
context:
  - '{project-root}/AGENTS.md'
  - '{project-root}/_bmad-output/planning-artifacts/epics.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Agents have a constitution but no project skills for connector, schema-change, provenance, or testing, so they re-derive those rules from AGENTS.md or invent process.

**Approach:** Add four skills under `.agents/skills/` with when-to-use descriptions Grok can discover. Point at existing constitution and code; do not duplicate ADRs or implement the Connector protocol.

</frozen-after-approval>

## Implementation Notes

- Names: `opendiscourse-connector`, `opendiscourse-schema-change`, `opendiscourse-provenance`, `opendiscourse-testing`.
- Home: `.agents/skills/<name>/SKILL.md`. Grok scans `.agents/skills/`. Mirror pg-graph with symlinks in `.grok/skills/` and `.claude/skills/`.
- Connector protocol is Story 2.1 (not in code yet). Connector skill forbids HANDLERS/cli/registry if/elif anyway.
- Pointers: `AGENTS.md`, SPEC CAP-2, AD-2..AD-7, `ingestion/base.py` `IngestionRun`, `just check-fast` / `check-db`.
- Review patches: inventory as data SDD; wait on protocol unless story 2.1; `run_plan()` elif named; sibling skills; models/migrations/sql split; CAP-1 path; capacity/`store_payload`; narrower testing trigger. Symlinks in `.grok/skills`, `.claude/skills`, `.agent/skills`.
- This session already listed the four skills in the harness skill roster (Grok discovery).

## Review Triage Log

- Missing inventory/scaffold pointers — medium — true; connector skill now names `inventory/` and stale `docs/adding-a-provider.md`.
- HANDLERS vs `run_plan()` elif — medium — true; named `run_plan()`.
- Unbounded “implement or wait” — medium — true; wait unless active story is 2.1.
- Schema paths incomplete — medium — true; models, migrations, `sql/query/` vs `sql/NNN_*.sql`.
- Provenance missing APIs — medium — true; `store_payload`, capacity, lake.md, SPEC path.
- Testing trigger too broad / recipe details — medium — true; narrowed description; extras and worksteal noted.
- `.claude` copies vs wrappers — false — they are symlinks to `.agents/skills/`.
- Mark 1.3 done before merge — low — same as 1.2; epics land with the PR.
- No existence test — low — rejected; Grok already discovered the skills; a pytest would add little.
