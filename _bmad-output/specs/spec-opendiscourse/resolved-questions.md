# Resolved open questions (2026-09-17)

Companion to `SPEC.md`. Sources: FEC bulk docs, OCDEP 2, Census
relationship files, NHGIS crosswalks, pgvector production guidance, live
snapshot. These close the kernel Open Questions; they do not open Epic 7
or change 8.1.

## 1. FEC grain and retention (after CAP-4)

**Decision:** Typed FEC bulk grains, not `fact.measurement`, not name
joins, not “promote `stage.fec_row`.” Still v1.1 / Epic 7.

Official bulk files are the wrap target
(`https://www.fec.gov/data/browse-data/?tab=bulk-data`), 2-year cycles
(AD-9). Community loaders (`fec-gov-postgres` and similar) match that
shape; we wrap, we do not invent a generic money table.

| Layer | Grain | Key |
|---|---|---|
| Identity (needs CAP-4) | Person ↔ FEC candidate | `core.person_identifier` namespace `fec` / BioGuide via congress-legislators `fec_ids`. Never name-match. |
| Dimension | Candidate master | `(cand_id, cycle)` |
| Dimension | Committee master | `(cmte_id, cycle)` |
| Dimension | Candidate–committee linkage | `(cand_id, cmte_id, fec_election_year)` |
| Fact (itemized) | Individual contrib, committee-to-candidate, committee-to-committee, operating exp | FEC `sub_id` + `cycle` (file family as classification). Typed tables, not `fact.measurement`. |
| Stage today | `stage.fec_row` `(family, cycle, raw jsonb)` | Leftover dump (~102M). Replaceable. Do not COPY jsonb into `core`/`fact`. |

**Retention:** Immutable cycle zips stay in the lake. Postgres `fact`
default is **current cycle + previous two cycles** (six years), capacity
gated. Older cycles: DuckDB/Parquet export (CAP-6), not unbounded hot
tables. Expanding retained cycles is a reviewed plan, not a silent
backfill.

**Not in grain:** donor-as-`core.person`; stock prices; corruption
scores. A later disclosure may reference `core.instrument` without FEC
itemized rows.

## 2. When to switch embeddings from `real[]` to pgvector

**Decision:** Keep `real[]` until there is a real kNN workload.

`vector` 0.8.5 is already on the cluster; `core.embedding` is empty;
ADR-0001 forbids a side vector store. pgvector is the right in-cluster
ANN type once we search, not while the column is unused. Portable
`real[]` plus `cardinality = dimensions` stays until:

1. `core.document_chunk` rows exist and at least one embedding model
   version is loaded, **and**
2. A researcher/search story needs `<=>` / HNSW (not exact equality).

Then a **new ADR** (not this file) promotes `vector_values` to
`vector(n)` with an HNSW index, text remaining source of truth. Do not
migrate the empty table on FRED or 8.1.

## 3. `core.division` vs extending `core.geography`

**Decision:** Separate entity. Closed; 8.1 already implements this.

OCDEP 2: a Division is a political identity that **may have many
boundaries** over its life; the spec **does not** define boundary
storage. Census GEOIDs are vintage-specific. Putting `geography_id` on
division collapses redistricting onto one polygon. Spatial attach is a
later `division`↔`geography_boundary` junction, not a FK on division.

## 4. When to move `instrument` / `market_bar` to CFA

**Decision:** Do not move. This repo never ingests market bars.

CFA is a product-scope boundary, not a live sibling database today.
`core.instrument` stays an empty stub so v1.1 STOCK Act / PTR filings
can name a security without becoming Bloomberg. `fact.market_bar` stays
empty; no price Connector. Physical move only if a CFA repo exists and
takes market-bar ownership; until then deprecate ingest in docs only.

## 5. When bill/roll_call unique keys drop text session columns

**Decision:** Story 8.3, after a backfill gate. Not 8.1.

Live snapshot: ~36k bills and ~1.8k roll calls; `core.legislative_session`
is empty, so `legislative_session_id` cannot be the unique key yet.

Gate (all must be true):

1. Every `core.bill` and `core.roll_call` has non-null
   `legislative_session_id`.
2. Unique keys exist on
   `(legislative_session_id, bill_type, bill_number)` and
   `(legislative_session_id, external_id)` (or equivalent).
3. `sql/query/legislation/upsert_bill.sql` and roll-call upserts use the
   FK.
4. Dual-write period with no unique-key violations.

Then drop **uniqueness** on text `jurisdiction` + `legislative_session`.
Columns may remain as denormalized cache until a later drop. New loaders
must not treat the text pair as identity (AD-10).

## 6. When to add `core.geography_relationship`

**Decision:** Wrap Census relationship files when the first longitudinal
mart needs vintage comparability. Not 8.1. Not a generic parent tree.

Census publishes two official kinds
(`https://www.census.gov/geographies/reference-files/time-series/geo/relationship-files.html`):

- same geography type **over time** (comparability)
- two geography types **same vintage** (containment / overlay)

NHGIS crosswalks add interpolation weights; evaluate as wrap-optional
when area-weighted allocation is required. Do not hand-roll weights.

Trigger: Epic 5 `district_year` (or a CD redistricting pack) must compare
two TIGER vintages. Load typed rows with `source_artifact_id`; keep
`parent_geoid` as a loose string until then. Division↔TIGER remains the
separate later junction from 8.1 (C later).
