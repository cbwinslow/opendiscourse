---
title: 'Story 1.2 — ADR-0001 Postgres system of record'
type: 'chore'
created: '2026-09-14'
status: 'done'
route: 'oneshot'
review_loop_iteration: 0
context:
  - '{project-root}/AGENTS.md'
  - '{project-root}/_bmad-output/planning-artifacts/architecture/architecture-opendiscourse-2026-09-14/ARCHITECTURE-SPINE.md'
  - '{project-root}/_bmad-output/planning-artifacts/epics.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** AD-1 (Postgres/PostGIS is the system of record; database name `opendiscourse`) lives only in the architecture spine. There is no `docs/adr/` file, so agents cannot follow the constitution's "accepted ADRs" rung.

**Approach:** Add ADR-0001 matching AD-1 and point `AGENTS.md` at it. Do not restated later ADs and do not change runtime code.

</frozen-after-approval>

## Implementation Notes

- Filename: `docs/adr/0001-postgres-system-of-record.md` (MADR `NNNN-slug`; title inside is ADR-0001). `docs/adr/` does not exist yet.
- Source of truth for content: AD-1 in `_bmad-output/planning-artifacts/architecture/architecture-opendiscourse-2026-09-14/ARCHITECTURE-SPINE.md` lines 39–44. Bind: all durable facts. Prevents silent dual-writes to Qdrant/DuckDB/files as authority. Rule: DB name `opendiscourse`; DuckDB/PostgREST/Parquet are derived; another store requires a new AD.
- Do not copy ChatGPT archive ADR numbering (`docs/adr/0012-…`); those files were never created. Do not write AD-2..AD-7 in this story.
- `AGENTS.md` managed `<!-- bmad:context -->` block: add `docs/adr/` (ADR-0001) under Where things are; hierarchy already says ADRs. Edits inside the block are the constitution (same as Story 1.1).
- Out of scope: epics status rewrite beyond optional `_bmad-output/README.md` next-story line; no schema, no tests, no Connector work.
- Verify: file exists; `AGENTS.md` contains a path to the ADR; content restates AD-1 without contradicting SPEC.md constraint "Postgres/PostGIS is system of record (AD-1)".
- Wrote `docs/adr/0001-postgres-system-of-record.md` (Accepted, spine AD-1). Pointed `AGENTS.md` at the ADR file. Spine AD-1 links back. Marked Story 1.2 done in `epics.md` and `_bmad-output/README.md`.
- Review patches: alternatives table; Qdrant/Weaviate out of stack including caches; embeddings/`real[]` vs side vector store; `ingest`/`stage` not the curated layer.

## Review Triage Log

- Missing alternatives considered — medium — true; added table from PRD addendum.
- `AGENTS.md` pointed at directory not file — medium — true; now points at `docs/adr/0001-postgres-system-of-record.md`.
- Spine AD-1 had no back-link — medium — true; added **ADR:** path.
- Qdrant as derived index loophole — medium — true; Decision forbids side vector stores without a new ADR.
- Context vs `real[]` embeddings — medium — true; Decision states pgvector promotion is a later ADR.
- Consequences listed `ingest`/`stage` as durable curated facts — medium — true; clarified catalog vs curated layer.
- Stale “Suggested next build” / spec still in-progress / epic context — medium — true for the epics next-build line; patched. Spec status set `done` in finalize.
