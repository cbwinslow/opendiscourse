# ChatGPT review packet — 2026-09-17

Use this as the starting map for a review of OpenDiscourse **as it stands
right now**. The live warehouse schema is checked in under
`docs/schema-snapshot/`. Prior essays in this folder are research; they are
not the current epic list.

## What this is

OpenDiscourse is a provenance-first U.S. public-policy research warehouse.
PostgreSQL 17 / PostGIS is the system of record. Database name:
`opendiscourse`. Software SDD is BMAD; data SDD is `inventory/`.

The operator cluster this snapshot was taken from also holds a separate
`openstates` provider dump (read-only). That dump is **not** the researcher
contract.

## Read in this order

1. `AGENTS.md` — constitution and pitfalls
2. `_bmad-output/specs/spec-opendiscourse/SPEC.md` — product contract
3. `_bmad-output/planning-artifacts/architecture/architecture-opendiscourse-2026-09-14/ARCHITECTURE-SPINE.md`
4. `_bmad-output/planning-artifacts/epics.md`
5. `docs/adr/0001-postgres-system-of-record.md`
6. `docs/schema-snapshot/README.md` then `catalog.md`
7. `docs/schema-snapshot/opendiscourse.schema.sql`
8. `docs/schema-snapshot/openstates-inventory.md` and
   `openstates-opencivicdata.schema.sql` (provider snapshot, especially
   `opencivicdata_post` / membership / division)
9. `docs/model.md` and `docs/openstates-integration.md`
10. `docs/persistence-migration-status.md`
11. `docs/schema-snapshot/spec-8-1-post-division-membership.md`
12. `docs/schema-snapshot/related-files.md` — SQL, Alembic, models, inventory

## Live warehouse facts (this snapshot)

- PostgreSQL 17.11, database `opendiscourse`, tablespace `odspace`
- Alembic head at capture: see `docs/schema-snapshot/metadata.json`
- Owned schemas: `catalog`, `core`, `fact`, `ingest`, `stage`, `mart`, `leg`,
  `api` (empty HTTP surface), `openstates_source` (FDW)
- Extensions: PostGIS, pgvector, postgres_fdw, pg_trgm, unaccent, pgcrypto
- `core.membership` is still person → organization. Story 8.1 adds owned
  `core.division` / `core.post` and nullable `membership.post_id`. Those
  tables are **not** in this live dump until 8.1 is implemented.
- OpenStates `public.opencivicdata_post` already exists in the provider dump
  and is **not** currently imported through `openstates_source` FDW.

## Do not

- Treat `docs/research/2026-09-15-chatgpt-architecture-rereview.md` as a
  replacement epic list or implement its strangler reboot.
- Recommend writing OpenStates Django tables into `opendiscourse`.
- Name-match people. Federal joins need BioGuide.
- Invent news, stocks, or corruption-score domains.
- Start Epic 7 (FEC-native/crime staging, elections) in v1.
- Promote `core.embedding.vector_values` from `real[]` to pgvector without a
  new ADR.

## How the snapshot was produced

```bash
uv run python scripts/export_schema_snapshot.py
```

Schema-only. No table data. USER MAPPING passwords are redacted if present.
This is not a restore kit.
