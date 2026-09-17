# Schema snapshot

Captured **2026-09-17T04:29:52+00:00** from the live operator cluster
(`opendiscourse`, PostgreSQL 17.11 (Ubuntu 17.11-1.pgdg24.04+2),
234 GB of data).

This directory is a **review artifact**: schema-only DDL and catalogs so an
external model can inspect the warehouse as it stands. It is **not** a
migration path, bootstrap script, or restore kit.

| File | What it is |
|---|---|
| `opendiscourse.schema.sql` | `pg_dump --schema-only` of `opendiscourse` |
| `openstates-opencivicdata.schema.sql` | OCD tables only from the `openstates` provider DB |
| `catalog.md` | Columns, constraints, indexes, views, sizes |
| `openstates-inventory.md` | All OpenStates dump tables + OCD column lists |
| `related-files.md` | In-repo SQL, Alembic, models, inventory, specs |
| `spec-8-1-post-division-membership.md` | Copy of Story 8.1 (BMAD impl artifact is gitignored) |
| `epic-8-context.md` | Copy of Epic 8 context for the same reason |
| `metadata.json` | Capture metadata |

Regenerate (needs the live DSN, default `postgresql:///opendiscourse?port=5434`):

```bash
uv run python scripts/export_schema_snapshot.py
```

Rules for reviewers:

- Hierarchy of truth: current code+tests → migrations/schema → architecture
  spine/ADRs → active BMAD spec/story.
- Do not copy OpenStates Django tables into `core`.
- Federal person joins need BioGuide; do not name-match people.
- `dlt` writes `stage` only.
- `core.embedding.vector_values` stays `real[]` until a later ADR.
