# PRD addendum — mechanisms (not requirements)

## Stack (seed)

PostgreSQL 17 + PostGIS system of record; database name `opendiscourse`.
pgvector extension already present (0.8.5); Python client extra `search`.
DuckDB extra `analytics`. PostgREST Compose profile `api`. dlt = staging
only. dbt = marts. Optional Prefect extra `ops`, not required.

## Rejected alternatives

| Option | Why not |
|---|---|
| OpenSpec / Spec Kit | Operator chose BMAD+TEA as the single SDD |
| Restart repo | Foundation is sound; god modules are the bug |
| Copy OpenStates into `opendiscourse` | FDW `openstates_source` is the reader; dump stays refreshable |
| Adopt OpenStates Django dump as `core` | OCD language in owned tables; dump is a replaceable snapshot |
| Qdrant / Weaviate | Extra ops; pgvector is enough at this scale |
| Playwright-first TEA | Warehouse is pytest + PostGIS |

## Hierarchy of truth

1. Current code + tests  
2. Migrations/schema  
3. Accepted ADRs / architecture spine  
4. Active BMAD spec/story  
5. GitHub issue/PR  
6. Agent memory  
7. Old chats  
8. Model guesses  

Lower never overrides higher.

## ChatGPT 12-story process epic (status)

Stories 1, 5, 7 (partial), 8–9, 11 (partial) landed as commits on `main`
(BMAD/TEA install, pytest/CI/Repomix/Serena, extras, Dependabot). Remaining
process: `bmad-project-context` / AGENTS.md constitution, ADRs as files,
OpenDiscourse-specific skills, GitHub ruleset. Product: Connector (story 12).
