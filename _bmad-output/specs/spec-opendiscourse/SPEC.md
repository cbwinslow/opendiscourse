---
id: SPEC-opendiscourse
companions:
  - reuse.md
  - v1-scope.md
  - schema-invariants.md
  - resolved-questions.md
  - ../../planning-artifacts/architecture/architecture-opendiscourse-2026-09-14/ARCHITECTURE-SPINE.md
  - ../../planning-artifacts/prds/prd-opendiscourse-2026-09-14/prd.md
  - ../../../docs/adr/0002-schema-invariants.md
sources:
  - ../../../docs/research/2026-09-14-chatgpt-review.md
  - ../../../docs/research/2026-09-14-chatgpt-engineering-plan.md
  - ../../../docs/research/2026-09-14-chatgpt-bmad-context-plan.md
  - ../../../docs/research/2026-09-15-chatgpt-architecture-rereview.md
  - ../../../docs/research/2026-09-17-chatgpt-schema-review.md
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
so agents can implement without re-reading the ChatGPT essays. The
2026-09-17 schema review **keeps this warehouse and refines it**; it does
not authorize a redesign.

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
    politician joins to FEC/disclosure/elections stay gated (`person_join` in
    `inventory/sources.yaml`, enforced by `identitygate`) until a reviewed,
    approved contract opens them through an identifier, never a name.
- **CAP-5**
  - **intent:** Researcher can start from named research packs and dbt marts
    instead of assembling `fact.measurement` joins.
  - **success:** At least place-year and legislator-vote marts documented and
    buildable.
- **CAP-6**
  - **intent:** Researcher can query reviewed data via SQL, PostgREST `api`,
    or DuckDB/Parquet without loading unbounded `fetchall()` exports.
  - **success:** Reviewed read-only views in `api` cover loaded v1 spine
    tables with no `ingest`/`stage` exposure; one export path streams or
    chunks. (`api` schema already exists; views are Epic 6.1.)
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
- Internal UUID primary keys; external IDs (BioGuide, OCD, congress keys,
  roll-call ids) live in identifier tables or unique columns, never as the
  physical PK (AD-10).
- Schema support is not authorized ingest (AD-10). `stage.fec_row` and
  empty market tables do not open Epic 7 or stock-bar loads.
- Typed grains; do not collapse bills, votes, GIS, ACS, or money into one
  generic JSON facts table. `fact.measurement` is scalar series only.
- Source-derived `core`/`fact` rows need direct evidence; identity/reference
  exceptions are listed in `schema-invariants.md`.
- `core.bill` / `core.roll_call` text `jurisdiction` + `legislative_session`
  are compatibility columns; canonical session is `legislative_session_id`.
- Alembic owns catalog/core/fact/ingest/stage; dbt owns `mart`; Epic 6 owns
  `api` views; `leg` is compatibility.
- Do not expand v1.1 sources until a Connector→evidence→stage→core/fact→mart
  slice is proven (FRED e2e and/or legislator-vote). Keep-and-refine; do not
  redesign from ChatGPT schema reviews.
- FEC (Epic 7, after CAP-4): candidate/committee masters by `(id, cycle)`;
  itemized facts by FEC `sub_id`+cycle; lake keeps all cycle zips; hot
  `fact` default is current cycle + previous two. Details:
  `resolved-questions.md`.
- `core.division` is its own entity (OCDEP 2); never a `geography_id` FK
  on division.
- Keep empty `core.instrument`; never ingest `fact.market_bar`; do not
  move tables to CFA until a CFA repo exists.
- Story 8.3 session unique keys wait until `legislative_session_id` is
  non-null on every bill and roll_call.

## Non-goals

- Restarting the repository.
- News, stocks, or Epstein as schema domains.
- Integrity/corruption scores as a schema domain, or any opaque single composite
  score. Politician scorecards are permitted later as derived `mart` outputs
  built only from provenance-backed `core`/`fact` rows, each indicator linked to
  its evidence and methodology. That work needs its own capability and spec
  before it starts; it is not part of the v1 ingest spine.
- OpenSpec, Spec Kit, or a second planning system.
- Physically copying the OpenStates database into `opendiscourse`.
- Adopting the OpenStates Django dump as the canonical schema.
- Rewriting the Connector protocol or legislative schema on the FRED
  (Story 2.3) branch.
- Ripping `core.instrument` / `fact.market_bar` in v1, or loading market
  bars because those tables exist.
- Adding `core.geography_relationship` before the first longitudinal mart
  that needs Census relationship files (resolved-questions.md §6).
- Promoting `core.embedding.vector_values` to pgvector before chunks exist
  and a kNN/search story needs HNSW (resolved-questions.md §2).
- Promoting `stage.fec_row` jsonb into `core`/`fact`, or joining FEC donors
  to people by name (resolved-questions.md §1).
- Another architectural rewrite from `docs/research/2026-09-17-chatgpt-schema-review.md`.

## Success signal

A later session can ship Stories 2.2/2.3 and 8.1 from `_bmad-output/`
without opening ChatGPT files, without opening Epic 7, and without treating
text session columns or `stage.fec_row` as canonical product.

## Assumptions

- Operator Fast-path authorized this distill (2026-09-14).
- Vendor clones from `scripts/bootstrap_upstream.sh` are the wrap targets.
- Operator accepted keep-and-refine from the 2026-09-17 schema review
  (absorb into BMAD; do not replace epics).
- Operator asked to close kernel open questions with researched best
  options (2026-09-17); see `resolved-questions.md`.
