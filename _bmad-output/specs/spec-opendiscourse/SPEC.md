---
id: SPEC-opendiscourse
companions:
  - reuse.md
  - v1-scope.md
  - ../../planning-artifacts/architecture/architecture-opendiscourse-2026-09-14/ARCHITECTURE-SPINE.md
  - ../../planning-artifacts/prds/prd-opendiscourse-2026-09-14/prd.md
sources:
  - ../../../docs/research/2026-09-14-chatgpt-review.md
  - ../../../docs/research/2026-09-14-chatgpt-engineering-plan.md
  - ../../../docs/research/2026-09-14-chatgpt-bmad-context-plan.md
  - ../../../docs/research/2026-09-15-chatgpt-architecture-rereview.md
---

> **Canonical contract.** Read `companions:` with this file. ChatGPT markdown
> is archived under `docs/research/`; do not re-ingest it unless updating
> this spec.

# OpenDiscourse warehouse and development system

## Why

Public-policy research needs joined, provenance-backed facts across
identities, geography, and time. The repo already has the warehouse
foundation; organic growth produced god modules and no executable SDD.
This spec exists to **narrow the product**, **standardize ingestion behind
Connectors**, **wrap community tools**, and **make BMAD the software process**
so agents can implement without re-reading the ChatGPT essays.

## Capabilities

- **CAP-1**
  - **intent:** Operator can ingest only reviewed, budgeted selections and
    trace every fact to source evidence.
  - **success:** Spot-check of loaded facts resolves to `ingest.run` + URL +
    checksum; capacity gate exits non-zero on unknown size.
- **CAP-2**
  - **intent:** Operator can add or migrate a source through a Connector
    without editing central dispatchers.
  - **success:** FRED runs as a Connector; `plans.py` HANDLERS if/elif is not
    required for that path.
- **CAP-3**
  - **intent:** Researcher can use House and Senate roll calls produced by
    wrapped upstream tools.
  - **success:** Senate votes exist; no new first-party floor-XML scraper.
- **CAP-4**
  - **intent:** Researcher can join people across sources on BioGuide (and
    preserved OCD IDs), never display name.
  - **success:** `core.person_identifier` populated from congress-legislators;
    politician joins to FEC/disclosure blocked until this exists.
- **CAP-5**
  - **intent:** Researcher can start from named research packs and dbt marts
    instead of assembling `fact.measurement` joins.
  - **success:** At least place-year and legislator-vote marts documented and
    buildable.
- **CAP-6**
  - **intent:** Researcher can query reviewed data via SQL, PostgREST `api`,
    or DuckDB/Parquet without loading unbounded `fetchall()` exports.
  - **success:** `api` schema exists; one export path streams or chunks.
- **CAP-7**
  - **intent:** Agents can implement changes through BMAD sized to the work,
    with inventory remaining the data contract.
  - **success:** `AGENTS.md` constitution points at this spec; XS changes skip
    PRD; no second SDD framework.
- **CAP-8**
  - **intent:** Researcher can join a person to a seat/post and a political
    division over time, not only to a chamber, without querying the
    OpenStates dump as the public schema.
  - **success:** Owned `core` has post (or equivalent) and division (or
    equivalent) distinct from Census geography; membership can reference a
    post; FDW remains read-only; Congress.gov/GovInfo/clerk rows are not
    written into database `openstates`.

## Constraints

- Database name is `opendiscourse`. Postgres/PostGIS is system of record (AD-1).
- OpenStates dump stays a separate DB; warehouse uses read-only FDW (AD-8).
  FDW is an internal reader, not the researcher contract. Combine other
  legislative sources in `core` by identifier.
- Default acquisition: bulk/archive for history, API/feed for freshness
  (AD-9).
- dlt never writes `core`/`fact`.
- TEA execution target is pytest + PostGIS, not Playwright-first.
- Grok/Claude/Codex/Cursor share `.agents/skills/` (plus Claude `.claude/skills`).
- Do not require `censusdis`.
- Lower context (chats, memory) never overrides code, tests, migrations, or
  this spec.

## Non-goals

- Restarting the repository.
- News, stocks, or Epstein as schema domains.
- Integrity/corruption scores as a product.
- OpenSpec, Spec Kit, or a second planning system.
- Physically copying the OpenStates database into `opendiscourse`.
- Adopting the OpenStates Django dump as the canonical schema.
- Rewriting the Connector protocol or legislative schema on the FRED
  (Story 2.3) branch.

## Success signal

A later session can implement Epic 2–3 from `_bmad-output/` without opening
the ChatGPT files, and FRED-as-Connector plus an `AGENTS.md` constitution
merge without expanding ingest scope.

## Assumptions

- Operator Fast-path authorized this distill (2026-09-14).
- Vendor clones from `scripts/bootstrap_upstream.sh` are the wrap targets.

## Open Questions

- FEC grain/retention after CAP-4.
- When to switch embeddings from `real[]` to pgvector columns.
- `core.division` as its own entity vs extending `core.geography` (default:
  separate division, linked to TIGER vintages).
- When to physically move `instrument` / `market_bar` to CFA (default:
  deprecate in docs first).
