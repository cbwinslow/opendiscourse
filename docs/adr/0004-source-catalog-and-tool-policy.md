# ADR-0004: Source catalog, tool matrix and scope gates

- Status: Accepted
- Date: 2026-09-19
- Spine: AD-10 (schema support is not ingest scope); `v1-scope.md` sequencing
- Input: `docs/research/2026-09-19-chatgpt-sources-review.md` (research, not authority)

## Context

The operator asked for a review of the data sources and tools we use and for a plan to know every
source available. A ChatGPT review proposed a catalog of about 26 domains (legislation through
disaster and transport data) and a standard Python stack. We are the decision maker: the review
is a map of leads, and every factual claim in it is a model's summary that we have not checked.
`AGENTS.md` ranks it below code, specs and ADRs.

What is already true: raw bytes are immutable and checksummed; the database is PostgreSQL 17
with PostGIS as the system of record (ADR-0001); each source is a Connector doing download,
inventory, ingest (CAP-2); federal legislation is loaded for Congresses 108-119 with full
BILLSTATUS records and people terms; `unitedstates/congress` and `congress-legislators` are
cloned under `vendor/`.

## Decision

**1. Architecture stands.** Immutable raw evidence, then stage, then typed `core`/`fact`, then marts.
Nothing in the review argues for changing this, and we do not.

**2. The source catalog becomes the acquisition map.** Extend `inventory/sources.yaml` (proposed
Story 9.6, to be specced with BMAD before any code) so each dataset records: publisher and
authority (primary or secondary); domain; preferred acquisition (bulk or API) and incremental
method; formats; grain; identifiers; geography; cadence; licence; **estimated size in bytes**; status
(`implemented`, `partial`, `registered`, `candidate`, `blocked`, `out_of_scope`); tool decision
(`USE`, `WRAP`, `REFERENCE`, `NONE`) and the named tool; canonical target table; scope gate (`v1`,
`v1.1`, `later`, `never`); and `verified_on`, the date someone confirmed the endpoint, licence and
size against the live source. A dataset without `verified_on` is a lead, not a plan. The same story
audits every existing Connector against the catalog.

**3. The tool inventory is `reuse.md`.** It gains a USE / WRAP / REFERENCE / NONE entry for each tool the
review names. The standing rule is unchanged: before writing acquisition, parse or export code,
check `sources.yaml` and `reuse.md`.

**4. Scope gates come from `v1-scope.md`, not from the review.** The review's list is a catalog. Sequencing
stays: identity, legislation, geography, census/economic, marts; then v1.1 in the order FEC,
disclosures, elections, crime. `v1-scope.md` also forbids expanding horizontally until a
Connector-to-mart slice is proven, and the legislator-vote slice is the named proof. So the next
build is the **votes Connector**, not a new domain. Additions proposed by the review that no spec
covers yet (lobbying via LDA.gov, federal spending via USAspending, SAM.gov, Federal Register,
Regulations.gov and eCFR, courts, and the health, education, environment, energy, agriculture,
disaster and transport outcome sources) enter the catalog as `candidate` with gate `later`; the
operator ranks them and a SPEC change opens each. SEC Form 4, 13F and market prices stay
`out_of_scope` (stocks are a non-goal).

**5. Tool decisions.**

| Tool or idea from the review | Decision |
|---|---|
| Reuse upstream acquisition (`unitedstates/congress`, `congress-legislators`, OpenStates, Census libraries) | **Accepted**; already policy |
| `censusdis` as a standard tool | **Rejected as a dependency**: Hippocratic licence (`AGENTS.md`). Optional convenience only |
| `pygris`, `datamade/census` | `REFERENCE` until licence, maintenance and fit are checked; the Census loaders we have work |
| `fredapi` | Already an optional extra; our FRED client stays |
| Disclosure and trading repos (`congress-trading-pipeline`, PoliTracker, Quantgress, `us-congress-stock-transactions-retrieval`), `pyCFR` | `REFERENCE` only: small projects, unverified. Official House, Senate and eCFR sources are canonical |
| Prefect | Not adopted: an optional `ops` extra that no code imports (the review's claim that we already use it is wrong). No second orchestrator either |
| Pandera | Candidate for validating frames before promotion; adopt when a loader needs it, not before |
| Polars, DuckDB, PyArrow | Already optional (`analytics` extra); used where a loader benefits |
| `dlt` | REST to `stage` only (unchanged) |
| Parquet "normalized lake" between raw files and Postgres | **Not adopted as authority.** ADR-0001 keeps Postgres the system of record, and the schema-change skill forbids a second source of truth. Allowed later as a derived, rebuildable side cache for very large sources, only after its own ADR with a benchmark (settle it by measurement). It is also worth testing as a fix for table size (see the storage plan) |
| Data.gov | Discovery only; ingest from the publisher's own endpoint |
| Disclosures keep the reported range (no invented midpoint) | **Accepted** (already in `sources.yaml` notes) |
| Crime: store agency participation alongside counts | **Accepted** as a design rule when crime opens |
| Do not write another Congress scraper | **Accepted**; votes wrap `unitedstates/congress` |

**6. Size is a gate.** Every catalog entry carries an estimated size; the capacity gate stays fail-closed on
unknown size; any candidate estimated above 50 GB needs a storage line in its spec that names the
target volume and how it is backed up (`docs/storage-and-backup-plan.md`).

## Consequences

- One artifact (the catalog) answers "what exists and what do we do about it", and it can be
  audited against the Connectors.
- We do not chase 26 domains at once. The review's best idea, a source registry plus a community-tool
  inventory, is adopted; its build order is not.
- Facts in the review are checked one source at a time when that source's story begins, and the
  result is written into the catalog (`verified_on`).
- Rejected or deferred items are recorded here, so no later session re-litigates them without new evidence.
