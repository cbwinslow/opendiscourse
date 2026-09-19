# Database performance audit (2026-09-19)

Read-only measurements of the PostgreSQL 17 cluster (port 5434: `opendiscourse`, `openstates`)
on a 125 GB / 40-core host that also runs PostgreSQL 16 (port 5432: `mlb`, `govdata`).
Everything below was measured, not assumed; queries are listed so it can be rerun.

## The hardware fact that shapes every recommendation

`lsblk -d -o NAME,ROTA`: **all six physical disks are spinning HDDs** (ROTA=1). Random reads
are expensive, sequential reads are cheap. Consequences:

- Keep `random_page_cost` at 4 and `effective_io_concurrency` at 1. Lowering them (advice
  written for SSDs) would make the planner choose index scans it cannot afford.
- Memory is the lever: `shared_buffers` plus the OS page cache turn random reads into RAM hits.
- Every extra index is a random write per inserted row, and every random-UUID key scatters
  those writes across the whole index. Fewer, smaller, ordered indexes pay off more here.
- Bulk work should be sequential: load a table, then build its index; swap partitions instead
  of deleting rows (ADR-0003).

## Settings (cluster-wide, not per database)

The 16 cluster is tuned. The 17 cluster ran on defaults (`shared_buffers` 128 MB,
`maintenance_work_mem` 64 MB, `work_mem` 4 MB). `scripts/ops/tune_postgres_17.sh` proposes values
sized against both clusters, prints a worst-case memory budget, applies with `ALTER SYSTEM`,
and reverts. Applied 2026-09-19 except the restart-only settings (`shared_buffers`,
`max_worker_processes`, and `shared_preload_libraries` for `pg_stat_statements`), which take
effect after `sudo systemctl restart postgresql@17-main`.

Risk on the 16 cluster (not changed): 10 autovacuum workers x `maintenance_work_mem` 4 GB can
theoretically reach 40 GB; capping `autovacuum_work_mem` at 1 GB is a reload-only fix.

`pg_stat_*` usage counters were empty for every big table (no index scan counts, no vacuum
times), so index usage cannot yet be judged. `pg_stat_statements` and `track_io_timing` are in
the script so the next audit is evidence-based.

## Data types: what the two biggest fact tables cost

`fact.acs_bulk_estimate`: 281M rows, 36 GB heap, **63 GB of indexes**.

| column | type | avg bytes | distinct | note |
|---|---|---:|---:|---|
| acs_bulk_estimate_id | uuid | 16 | unique | primary key; **no table references it** (0 foreign keys) |
| geography_id | uuid | 16 | 3,278 | could be a 4-byte key |
| table_id | text | 7 | 373 | derivable from field_id |
| field_id | text | 12 | 19,450 | dimension candidate (4 bytes) |
| measure | text | 12 | **2** | should be smallint/enum (2 bytes) |
| value | numeric | 5 | | fine |
| source_artifact_id | uuid | 16 | 1,298 | repeated on every row |

Indexes: `pkey (uuid)` 11 GB, natural-key unique `(source_artifact_id, source_ordinal, field_id)`
29 GB, lookup `(release_year, geography_id, table_id, field_id)` 22 GB. Three indexes on the
same rows, one of them a random-UUID key nothing uses.

Estimated saving from a redesign (estimate, verify uniqueness first): drop the unreferenced
UUID key and its 11 GB index, make the lookup index the unique natural key
`(release_year, geography_id, field_id, measure)` and drop the 29 GB one, store `measure` as
smallint: **about 45 GB of the 99 GB**, three indexes to maintain on load instead of one, and
partitioning by `release_year` would make each new ACS vintage a partition swap.
`fact.business_pattern` (5.9 GB heap + 6.2 GB indexes) has the same unreferenced UUID key and a
45-value `source_member text` repeated per row.

Not done: both tables are static and disk is not constrained (2.0 TB free), so this is a speed
and cache-efficiency win, not an urgent one. It needs an ADR-0002 amendment (facts may use
natural composite keys; UUID keys stay for referenced entities) and a benchmark on real ACS
queries once Epics 5-6 define them.

`stage.fec_row` and `stage.cbp_row` store each row as keyed jsonb: 526-600 bytes/row, 35% of
which is repeated column names (measured). Compact arrays or typed columns are ~35% smaller
and load with 35% less WAL (ADR-0003).

## Rules of thumb for this warehouse

1. Low-cardinality text (codes, measures, flags): `smallint`, `"char"`, or an enum, not text.
2. Counts and codes: `integer`/`bigint`, not `numeric`. Use `numeric` only where exactness at
   scale matters (money, estimates with margins).
3. Timestamps: `timestamptz`; dates that are only dates: `date` (4 bytes, not 8).
4. Do not put a random UUID primary key on a large fact table; use a composite natural key or
   a `bigint` identity. UUIDs are fine for referenced entities (person, bill, roll call): tens
   of thousands of rows, not hundreds of millions.
5. Put fixed-width columns (uuid, bigint, timestamptz) before variable-width ones to reduce
   alignment padding.
6. Index only what a real query needs; one unique natural key that also serves lookups beats
   three overlapping indexes.
7. Stage tables are transient: partition by slice, compact rows, truncate a partition after
   promotion.
8. Large tables partitioned by their arrival slice; reload by partition swap (ADR-0003).

## Reproduce

```sql
-- sizes and index cost
select relid::regclass, pg_size_pretty(pg_table_size(relid)) heap, pg_size_pretty(pg_indexes_size(relid)) idx
from pg_stat_user_tables order by pg_total_relation_size(relid) desc limit 15;
-- column widths and cardinality
select attname, avg_width, n_distinct from pg_stats where schemaname='fact' and tablename='acs_bulk_estimate';
-- unreferenced keys
select count(*) from pg_constraint where confrelid = 'fact.acs_bulk_estimate'::regclass;
```
