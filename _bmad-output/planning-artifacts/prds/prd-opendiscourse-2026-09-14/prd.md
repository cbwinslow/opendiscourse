---
title: OpenDiscourse
status: final
created: 2026-09-14
updated: 2026-09-17
---

# PRD: OpenDiscourse

## 0. Document Purpose

For the operator and any agent implementing OpenDiscourse. Fast-path PRD from
the archived ChatGPT review/plans plus locked decisions (BMAD+TEA, Postgres as
system of record, wrap-don't-rewrite). Tech mechanism lives in the architecture
spine and spec companions, not here.

## 1. Vision

OpenDiscourse is the warehouse you query when you need to know what happened in
a place, in a year, under which lawmakers, with which votes, demographics,
housing, and (later) money — and prove where every number came from.

It exists because public data is scattered across Congress.gov, GovInfo,
OpenStates, Census, FRED, FEC, and others, each with different identifiers.
The product is the **standardizing surface**, not another one-off downloader.

## 2. Target User

### 2.1 Jobs To Be Built

- Reproduce a place-year social panel (ACS + PEP + CBP + TIGER) with MOE intact.
- Follow a bill from introduction through actions, text, and roll calls.
- Join a member to votes, districts, and (v1.1) donations/disclosures via
  BioGuide, never name-matching.
- Add a new government source without forking `cli.py` / `plans.py`.

### 2.2 Non-Users (v1)

Casual news readers, campaign operatives wanting opposition research scores,
quant traders (CFA owns markets).

### 2.3 Key User Journeys

- **UJ-1. Operator refreshes a reviewed plan.** The operator runs
  `research-db plan-due` (or browse). Capacity gate runs. Artifacts land in
  the lake with checksums. Staging is replaceable; core/fact only change
  through reviewed transforms. Failure is actionable with a resume command.
- **UJ-2. Researcher builds a district-year panel.** They hit mart views (or
  DuckDB/Parquet export), not raw `fact.measurement` joins. Geography vintages
  are explicit. They can follow a cell back to `ingest.run` + source URL.
- **UJ-3. Agent adds a source.** They search for an upstream project first,
  register in `inventory/sources.yaml`, add a disabled contract, implement a
  Connector, never a new god-module branch.

## 3. Glossary

- **Connector** — The unit that owns discover → select → plan → extract →
  evidence → stage → normalize → validate → publish → checkpoint for one
  source family.
- **Contract** — Reviewed YAML selection (grain, coverage, cadence, enabled).
- **Plan** — Exact allowed ingest (`inventory/plans.yaml`).
- **Raw / ingest / stage / core / fact / mart** — Layered data model; see
  `docs/blueprint.md`.
- **Identity crosswalk** — BioGuide-primary person keys; OCD IDs preserved.
- **Research pack** — Named, documented starting panel (not a new schema).
- **Capacity gate** — Refuse download if sizes unknown or disk budget fails.
- **System of record** — PostgreSQL 17 + PostGIS database `opendiscourse`.

## 4. Features

### 4.1 Provenance-first warehouse

**FR-1:** Every ingest run records provider, dataset, params, URL, checksum,
and raw payload or artifact.

**FR-2:** Capacity gate blocks bulk download when size is unknown or budget
fails.

**FR-3:** Staging may evolve automatically; core/fact require reviewed
transforms and stable keys.

### 4.2 Connector runtime

**FR-4:** Sources register as Connectors. Adding one must not require editing
central `if/elif` dispatchers (`cli.py`, `plans.py`, `registry.sync`).

**FR-5:** Reference migration is FRED end-to-end with no schema change.

### 4.3 Legislative and identity spine

**FR-6:** Federal bills/actions/text from Congress.gov + GovInfo with
package/version IDs retained.

**FR-7:** House and Senate roll calls come from wrapped
`unitedstates/congress` (or equivalent maintained producer), not a new
scraper. `[ASSUMPTION: vendor checkout is the wrap target.]`

**FR-8:** Person identity uses `unitedstates/congress-legislators` /
BioGuide as the federal deterministic key.

**FR-9:** OpenStates remains an isolated snapshot; warehouse reads via FDW
`openstates_source`; never write into the dump. FDW is not the researcher
contract; promote OCD-aligned rows into `core`. Combine Congress.gov,
GovInfo, and clerk votes in `core` by identifier, not inside the dump.

### 4.4 Geography, census, macro

**FR-10:** TIGER vintages are stored, never overwritten.

**FR-11:** ACS/DHC/PEP/CBP load through existing bulk contracts; housing
deltas only after capacity/health checks.

**FR-12:** FRED/ALFRED and Treasury are the macro spine; BLS/BEA only under
reviewed geography/time contracts.

### 4.5 Research access

**FR-13:** dbt marts are the researcher interface (`district_year`,
`legislator_vote`, bill timelines).

**FR-14:** Read-only PostgREST on schema `api` (reviewed views only).

**FR-15:** DuckDB/Parquet/GeoParquet exports must not `fetchall()` unbounded
result sets.

**FR-16:** Document embeddings (when added) are model-versioned rows in
`core.embedding` / pgvector; never the only retained form of text.

### 4.6 Development system

**FR-17:** Single SDD engine is BMAD Method v6 + TEA. Change class XS/S →
`bmad-build`; M → `bmad-spec` then Build; L/XL → this planning path.

**FR-18:** `inventory/*` remains the **data** SDD. BMAD does not clone
sources into PRDs.

**FR-19:** Fast CI: `ruff check src` + non-DB pytest. DB tests stay serial
against PostGIS.

### 4.7 Schema invariants

**FR-20:** Canonical schema follows AD-10: UUID PKs plus identifier tables;
source-derived evidence; typed grains; schema support is not ingest;
`mart` is dbt-owned; bill/roll-call text session columns are compatibility
only. `[SOURCE: 2026-09-17 schema review absorb.]`

## 5. Non-Goals (Explicit)

- Restart the repository.
- News, Epstein, or stocks as first-class schema domains. Existing
  `core.instrument` / `fact.market_bar` are empty compatibility tables, not
  a license to ingest prices.
- Corruption/integrity **scores** as a schema domain or opaque single score (keep
  evidence). Evidence-linked scorecards may be added later as derived marts.
- Meltano/Singer as the foundation; Qdrant/Pinecone; FastAPI CRUD.
- OpenSpec or Spec Kit beside BMAD.
- Playwright as the default test stack.
- Letta/Supermemory/Mem0/Graphiti as authority (Git + ADRs + BMAD win).
- Making `censusdis` a required dependency (Hippocratic License).

## 6. MVP Scope

### 6.1 In Scope

Operating contract + Connector + FRED reference (the proving vertical
slice); identity crosswalk; wrap congress votes; research packs for the
v1 spine; `api` schema views for what already exists; DuckDB export path.
Existing ACS/TIGER/bill loads do not replace the Connector slice.

### 6.2 Out of Scope for MVP

FEC/disclosure/elections-as-member **joins** until identity crosswalk exists.
FEC-native and crime-native staging are also v1.1 (not identity-blocked, still
not MVP). Prefect/Dagster as required runtime. Adopting the OpenStates Django
dump as the canonical schema. Connector v2 / legislative post schema on the
FRED branch.

## 7. Success Metrics

- **SM-1:** New source lands as a Connector without editing `plans.py`
  HANDLERS / `cli.py` dispatcher. Validates FR-4.
- **SM-2:** Spot-check of 10 facts traces to run + URL + checksum. Validates
  FR-1.
- **SM-3:** Senate roll calls exist without a homegrown XML scraper. Validates
  FR-7.
- **SM-4:** Bills, official votes, and members for Congresses 108–119 meet
  `specs/spec-opendiscourse/legislative-north-star.md` (SPEC CAP-10): publisher
  counts match, every offered field is on a checklist, and the live database
  agrees with `inventory/progress.yaml`. Validates the 2026-09-25 operator goal.

**Counter-metric SM-C1:** Number of datasets registered. Do not optimize
catalog size.

## 8. Open Questions

None. Closed 2026-09-17 in
`specs/spec-opendiscourse/resolved-questions.md`:

1. FEC: masters `(id, cycle)`; itemized `sub_id`+cycle; hot fact = current
   + two prior cycles; no name joins.
2. Politician investments: official STOCK Act / PTR filings only, via
   `core.instrument` stub; no market bars.
3. Embeddings: keep `real[]` until chunks + kNN story; then a new ADR.
4. Session unique keys: Story 8.3 after `legislative_session_id` backfill.

## 9. Assumptions Index

- Wrap target for votes is `vendor/unitedstates-congress`.
- Database name is `opendiscourse` (already true on port 5434).
- Fast path authorized: operator said ChatGPT files contain the plan.
