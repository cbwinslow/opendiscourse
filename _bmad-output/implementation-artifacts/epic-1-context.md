# Epic 1 Context: Development substrate

<!-- Compiled from planning artifacts. Edit freely. Regenerate with compile-epic-context if planning docs change. -->

## Goal

Lock the **development substrate** so agents and the operator change the warehouse the same way: a short constitution, ADRs as files, project skills, and optional GitHub protection. Software SDD is BMAD Method + TEA; data SDD stays `inventory/`. Later product epics inherit that hierarchy of truth instead of competing process kits. Most of this already landed on `main`; remaining stories still matter.

## Stories

- Story 1.1: AGENTS.md constitution
- Story 1.2: ADR-0001 Postgres system of record
- Story 1.3: OpenDiscourse skills
- Story 1.4: GitHub ruleset (optional solo)

## Requirements & Constraints

- Single software SDD: BMAD Method v6 + TEA. Change class: XS/S → `bmad-build`; M → `bmad-spec` then Build; L/XL → PRD / architecture spine / epics. Do not add OpenSpec or Spec Kit.
- Data SDD stays `inventory/` (`sources.yaml`, `plans.yaml`, `contracts/`). BMAD does not clone sources into PRDs.
- Fast CI is `ruff check src` plus non-DB pytest. Warehouse tests are pytest + PostGIS (markers `unit`/`db`/`integration`/`slow`/`live`/`e2e`); DB tests stay serial — no xdist, no Playwright-first TEA.
- Constitution must be adopted by `bmad-project-context` from existing `AGENTS.md`; `CLAUDE.md` is a stub; no `GROK.md` fork.
- Hierarchy of truth (highest wins): current code+tests → migrations/schema → accepted ADRs / architecture spine → active BMAD spec/story → GitHub → agent memory → old chats → model guesses. Lower never overrides higher.
- Do not restart the repository. Do not treat Letta/Supermemory/Mem0/Graphiti as authority over Git + ADRs + BMAD.

## Technical Decisions

- Postgres 17 + PostGIS is the system of record; database name `opendiscourse` (CI: `opendiscourse_test`). DuckDB, PostgREST, and Parquet are derived. Another durable store needs a new architecture decision. ADR-0001 lives in `docs/adr/` and must match this rule; `AGENTS.md` points at it.
- BMAD is software SDD; inventory is data SDD. Connector is the only way to add a source (no new `if/elif` in `cli.py` / `plans.py` / `registry.sync`). Provenance is required; capacity gate fails closed. Wrap maintained upstream; do not rewrite scrapers. Federal identity is BioGuide before money/crime. Persistence: Alembic for catalog/core/fact/ingest/stage; raw psycopg only for COPY, set-based promotion, OpenStates FDW, and caller-supplied legislative transactions.
- Agent skills (connector, schema-change, provenance, testing) live under `.agents/skills/` or `_bmad/custom`, each with when-to-use, discoverable by Grok.
- Python 3.12. Bound parameters only. Long work uses the shared `feedback` module. `dlt` writes `stage` only. OpenStates dump is read-only FDW, never merged. Embeddings stay derived (`real[]` until a later ADR). Do not make `censusdis` a required dependency.

## Cross-Story Dependencies

- 1.1 and 1.2 are done; constitution points at `docs/adr/0001-postgres-system-of-record.md`.
- 1.3 skills must follow the constitution and AD-1..AD-7 (especially Connector, provenance, schema/persistence, and test lanes).
- 1.4 is optional for a solo operator: `main` requires PR + CI, no force-push, squash; no extra human approver. Architecture defers GitHub ruleset / extra reviewers; document and apply only if permissions allow.
- This epic covers the development-system requirements. Suggested next product work is Epic 2 (Connector protocol, FRED). Epic 7 (money/elections/crime) stays blocked on identity (Epic 3).
