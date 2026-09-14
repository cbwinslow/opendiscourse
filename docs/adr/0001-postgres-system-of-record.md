# ADR-0001: Postgres is the system of record

- Status: Accepted
- Date: 2026-09-14
- Spine: AD-1 (ADOPTED) in `_bmad-output/planning-artifacts/architecture/architecture-opendiscourse-2026-09-14/ARCHITECTURE-SPINE.md`

## Context

OpenDiscourse is a provenance-first public-policy warehouse. Facts must remain
joinable across identities, geography, and time, with a single durable catalog.
Access engines (DuckDB, PostgREST, Parquet) are useful but must not become a
second authority. Numbering is `docs/adr/NNNN-slug.md` aligned to spine AD-N;
do not resume unused ChatGPT sequences such as `0012` / `0014`.

## Decision

PostgreSQL 17 with PostGIS is the system of record. The application database
name is `opendiscourse` (CI: `opendiscourse_test`).

DuckDB, PostgREST, and Parquet are derived from Postgres. They are not
catalogs. Qdrant and Weaviate are not in the stack, including as caches or
vector indexes. Another store as durable authority — or any side vector store
— requires a new ADR. In-cluster pgvector columns remain a later ADR;
embeddings stay derived `real[]` until then.

## Alternatives considered

| Option | Why not |
|---|---|
| DuckDB as catalog | Local/analytical; not the shared multi-writer geospatial system of record |
| Lake / Parquet as authority | Evidence store only; cannot replace joinable Postgres facts |
| Qdrant / Weaviate | Extra ops; pgvector on the cluster is enough if embeddings are promoted later |

## Consequences

- The catalog is Postgres. Curated researcher-facing facts live in `core` /
  `fact` / `mart` / `api`. `ingest` and `stage` are also Postgres, not a
  second store; they are not the curated layer (see AD-3).
- Silent dual-writes that treat DuckDB, files, Qdrant, or Weaviate as
  authority are forbidden.
- Lake files may hold immutable raw evidence; they do not replace the catalog.
- Agents follow this file from `AGENTS.md`; spine AD-1 is the short form of
  the same rule.
