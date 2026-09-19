# ADR-0004: Source catalog, tool matrix and scope gates

- Status: Accepted
- Date: 2026-09-19
- Spine: AD-10 (schema support is not ingest scope); `v1-scope.md` sequencing
- Input: `docs/research/2026-09-19-chatgpt-sources-review.md` (research, not authority)

## Context

The operator asked for a review of the data sources and tools we use and for a plan to know every
source available, without limiting ourselves. A ChatGPT review proposed a catalog of about 26 domains
(legislation through disaster and transport data) and a standard Python stack. It is a good review: most
of it is sound and is adopted below. Its claims about external sources are checked one source at a time
when that source's story begins (a few minutes each, recorded as `verified_on`); that is normal
engineering care, not doubt. `AGENTS.md` ranks any model's summary below code, specs and ADRs, so the
review guides the plan and the code and tests settle the facts.

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

**4. The catalog is broad; the build order is `v1-scope.md`.** Every source in the review goes into the
catalog: we do not limit what we track. Only the order of building is gated, by the operator's own spec. Sequencing
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
| `censusdis` | Not a *required* dependency, because of the project's rule about its Hippocratic licence (`AGENTS.md`); usable as an optional convenience. If the operator lifts that rule we can use it freely |
| `pygris` (TIGER), `datamade/census` | **Evaluate when the source's story starts**; adopt if the licence and maintenance are fine. Our current Census loaders keep working meanwhile |
| `fredapi` | Already an optional extra; our FRED client stays |
| Disclosure and trading repos (`congress-trading-pipeline`, PoliTracker, Quantgress, `us-congress-stock-transactions-retrieval`), `pyCFR` | **Evaluate when the source's story starts**: try them, keep what is maintained and correct, wrap behind provenance. Official House, Senate and eCFR sources stay canonical |
| Prefect | Not needed yet, and not because it is a poor tool: idempotent commands plus cron cover today's needs. The review's claim that we already use it is wrong (an optional extra no code imports). Revisit when many sources need scheduling. No second orchestrator |
| Pandera | **Adopt** when the first loader needs frame validation |
| Polars, DuckDB, PyArrow | Already optional (`analytics` extra); use where a loader benefits |
| `dlt` | REST to `stage` only (unchanged) |
| Parquet "normalized lake" | **Plan a benchmark story soon**, because database size is a real constraint (see the storage plan). If it wins, adopt it as a derived, rebuildable layer for the largest sources. Postgres stays the system of record (ADR-0001); Parquet is never the authority |
| Data.gov | Discovery only; ingest from the publisher's endpoint |
| Disclosures keep the reported range (no invented midpoint) | **Accepted** |
| Crime: store agency participation alongside counts | **Accepted** as a design rule when crime opens |
| Do not write another Congress scraper | **Accepted**; votes wrap `unitedstates/congress` |

**6. Size is a gate.** Every catalog entry carries an estimated size; the capacity gate stays fail-closed on
unknown size; any candidate estimated above 50 GB needs a storage line in its spec that names the
target volume and how it is backed up (`docs/storage-and-backup-plan.md`).

## Consequences

- One artifact (the catalog) answers "what exists and what do we do about it", and it can be
  audited against the Connectors.
- We track every source but do not build 26 domains at once. The review's best idea, a source registry plus a
  community-tool inventory, is adopted; the build order stays the operator's `v1-scope.md`.
- Facts in the review are checked one source at a time when that source's story begins, and the
  result is written into the catalog (`verified_on`).
- Deferred or conditional items are recorded here with their trigger, so no later session re-litigates them
  without new evidence. Revised 2026-09-19 (same day) after the operator asked for less caution about tools:
  the tool decisions above moved from "reference only" to "evaluate and adopt if good".
