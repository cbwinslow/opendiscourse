# ADR-0003: Load strategy by grain

- Status: Accepted
- Date: 2026-09-19
- Spine: AD-3 (provenance), AD-10; Story 9.1
- Evidence: `scripts/bench/benchmark_load_strategies.py` (rerunnable; drops its scratch schema)

## Context

Nothing in `opendiscourse` is partitioned. The large tables are `fact.acs_bulk_estimate`
(281M rows, 99 GB incl. 63 GB of indexes), `stage.fec_row` (102M rows, 74 GB), `stage.cbp_row`
(29M), `fact.business_pattern` (31M). The finished sources (ACS, CBP, TIGER, PEP, DHC) are
static; the open volume is FEC (`indiv` 2018-2024 unstaged, the largest cycles) and the
Congress backfill. Operator policy: derived rows may be wiped and reloaded; retained artifact
bytes never are. We need one rule per kind of table, and a test every loader must pass.

## Measurements

Real `pas2` rows from `stage.fec_row`, 7 cycles (3.95M rows), scratch schema, PostgreSQL 17 on
its default 128 MB `shared_buffers` (the tuned settings need a restart and are being applied;
a rerun is recorded below when done). A = today's layout (one table, keyed jsonb, PK + index);
B = same rows, LIST-partitioned by cycle; C = compact `text[]` values, partitioned by cycle.

Initial load:

| layout | seconds | WAL MB | size MB | bytes/row |
|---|---:|---:|---:|---:|
| A flat jsonb | 142.7 | 3026 | 2642 | 701 |
| B partitioned jsonb | 95.5 | 2824 | 2660 | 706 |
| C partitioned compact | 97.4 | 1956 | 1721 | 457 |

Reload one cycle (703,597 rows), mean of 3:

| strategy | seconds | WAL MB | size growth MB | dead tuples |
|---|---:|---:|---:|---:|
| A delete + insert in one transaction | 20.5 | 704 | +427 | 703,597 |
| B partition swap | 9.7 | 452 | -9 | 0 |
| C partition swap, compact | 6.2 | 297 | -9 | 0 |
| A upsert, source unchanged | 12.0 | 42 | 0 | 0 |
| A upsert, 1% of rows changed | 11.1 | 44 | +4 | 7,035 |

After three reloads of one cycle, A had grown from 2,642 MB to 3,935 MB (+49%) and a plain
`VACUUM` returned none of it. The partitioned tables did not grow. All variants reproduced a
byte-identical slice (digest of the reloaded cycle). The layout numbers held at a smaller
scale (2 cycles). Row width: 22 column names repeated in every jsonb row is 35% of the bytes.

## Decision

1. **Bulk facts and stage tables that arrive by a natural slice** (FEC cycle, Census year,
   Congress) are **partitioned by that slice from creation**; the partition key is part of the
   primary key. A reload builds the slice as a standalone table, loads it, adds its primary
   key and a `CHECK (slice = X)`, then in one transaction detaches and drops the old
   partition and attaches the new one. No delete, no dead tuples, no bloat, and half the time
   of delete-and-insert. The `CHECK` lets `ATTACH` skip its validation scan.
2. **Entities other tables reference** (person, bill, roll call, organization) keep their
   UUIDs and are loaded by **set-based upsert from a temp table**
   (`ON CONFLICT ... DO UPDATE ... WHERE row IS DISTINCT FROM excluded`). An unchanged
   rerun writes 16x less WAL than delete-and-insert and adds no dead tuples. Wiping would
   change UUIDs and break foreign keys.
3. **Raw bytes are never wiped** and are reused unless the remote checksum changed
   (unchanged; Story 1.7).
4. **Stage rows are compact.** New stage tables store a family's values as an ordered array
   (or typed columns when the schema is stable), not keyed jsonb. The remaining FEC volume
   (`indiv` 2018-2024, the largest) is not staged until this layout and partitioning exist.
5. **Existing loaded tables are left as they are.** They are static and disk is not
   constrained (2.0 TB free); retrofitting partitions is a full rewrite with no benefit.
   Their bulk-refresh, if ever needed, uses strategy 1 on a new partitioned copy.
6. **Every loader passes the shared harness** (`tests/idempotency_harness.py`): running twice
   changes nothing, a load killed at each point then rerun equals a clean load, and
   wipe-and-reload reproduces the rows. Snapshots digest natural keys and content, never
   surrogate ids or timestamps. The legislators Connector is the first user.

## Consequences

- New large tables need partition DDL in their Alembic revision; a partition per slice is
  created by the loader before the swap.
- Delete-and-insert on a large unpartitioned table is not used for bulk slices.
- Compact stage rows need a per-family column list; that list is part of the contract.
- The benchmark is rerunnable and records the Postgres settings in force.
- Not decided here: typed-column vs array for each new family (decide per contract); index
  review for `fact.acs_bulk_estimate` (63 GB of indexes, usage counters empty; revisit once
  query patterns exist in Epics 5-6).

## Alternatives considered

| Option | Why not |
|---|---|
| Delete + insert everywhere | +43% table growth per cycle reload, 703K dead rows, no space returned by plain `VACUUM` |
| `VACUUM FULL` / repack after reloads | Rewrites the whole table under lock; partitioning avoids the need |
| Upsert for bulk facts | Cheap when little changes, but reads and compares every row and still leaves dead tuples on change; right for entities, wrong for slices |
| Partition the existing 99 GB tables | Full rewrite for static data; no gain now |
