# Storage and backup plan (proposal, 2026-09-19)

Status: **proposal; nothing here has been changed.** Facts marked (measured) were read from the
live server on 2026-09-19. Items marked (not verified) are inferences. Decisions marked
*Operator* need the operator's answer before anything is built. Server layout and sizes come
from `docs/data-inventory-2026-09-19.md` and `docs/performance-audit-2026-09-19.md`.

## What we found

1. **The OpenDiscourse database appears to have no working backup.** (measured, from the script and
   the monitor log; not run by us) The cron job `~/workspace/infra/scripts/validated_backup.sh`
   (daily, weekly, monthly) calls `pg_dump` and `pg_dumpall` with `-h localhost -U postgres` and no
   port, so it reaches PostgreSQL 16 on port 5432 (`mlb`, `govdata`), not PostgreSQL 17 on port 5434
   (`opendiscourse`). It writes to `/srv/backups/postgres/` on the root disk. The monitor
   (`sys_mon/logs/backup_status.log`) reports `backup_status: stale`, last backup 4.7 GB.
2. **The root disk is the wrong place for a large backup.** (measured) `/` is 547 GB, 77% used, 120 GB
   free. `opendiscourse` is 238 GB (schemas: `stage` 111 GB, `fact` 111 GB, `core` 14 GB, `ingest` 13 MB).
   Even compressed, a full dump is unlikely to fit beside what already lives there.
3. **Where new data goes is right.** (measured) Raw files land under
   `~/workspace/data-lake/opendiscourse/raw/` on the six-disk RAID volume (2.9 TB, 2.1 TB free). The
   database's default tablespace is `odspace`, also on that volume, so every new table lands there too
   (checked for `bill_source_record`, `bill_summary`, `membership`). Only PostgreSQL 17's control files and
   its WAL (write-ahead log) sit on `/`.
4. **RAID is not a backup.** (not verified whether anything copies it elsewhere) A six-disk RAID
   survives a disk failure. It does not survive an accidental delete, a corrupted table, a bad
   migration or losing the whole array. `/home/cbwinslow/workspace` and `/mnt/storage` are on the same
   RAID/LVM pool. *Operator: is there a copy of this pool outside the machine?*

## What is hard to rebuild and what is not

| Layer | Size | If lost |
|---|---:|---|
| Raw files under `raw/` (bill zips, legislators YAML, Census, FEC, OpenStates) | 0.6 GB congress; 121 GB Census; 10 GB OpenStates | re-downloadable from the publisher, but slow (Census 121 GB) and sources revise or remove data |
| `core` (people, bills, terms, records) and `ingest` (artifact registry, run ledger) | 14 GB | **rebuildable only from raw files that are still present**; the registry is what proves what each file is, so keep it |
| `fact` (mostly ACS 99 GB) and `stage` (mostly FEC 74 GB, CBP, TIGER) | 222 GB | rebuildable from raw by rerunning the loaders (hours to days); AGENTS.md already allows wiping and reloading derived rows |
| Legacy lake `/mnt/storage/data-lake/government` | 692 GB | unverified copy; `epstein` (658 GB) is a hold corpus, not ours to move or delete |

## Proposal (in order of value per byte)

**Tier A: small and important, back up nightly to the RAID pool and off the machine.** Logical dumps of
the `core`, `ingest` and `catalog` schemas (about 15 GB, compresses well), the `raw/congress` and
`raw/openstates` folders, and `~/workspace/data-lake/opendiscourse/meta/`. Target
`/mnt/storage/backups/opendiscourse/` (817 GB free), never `/`. Keep the last seven daily and four
weekly. *Operator: choose an off-machine target (an external disk, or an encrypted cloud bucket) for
at least the weekly copy; without one this is protection against mistakes, not against losing the array.*

**Tier B: big and rebuildable, do not dump.** `fact` and `stage`. Protect them by keeping the raw
files and the registry safe (Tier A), and by keeping loaders idempotent, which the load contract
(ADR-0003) already tests. Reloading is the backup.

**Tier C: whole-cluster recovery, only if point-in-time recovery is wanted.** A physical backup with WAL
archiving (a tool such as pgBackRest, compressed and incremental) to the RAID pool. It covers all
238 GB and lets us roll back to any moment, but costs disk and setup. *Operator: is roll-back to a
moment in time worth it, or is "rebuild from raw" enough for `fact` and `stage`?*

## Ways to make the database smaller (measure first; none is authorized yet)

- `stage` holds copies of data already loaded into `fact`/`core` (about 37 GB across CBP, TIGER and ACS
  staging, per `PROJECT-STATE.md`). They are rebuildable and duplicate loaded data.
- `fact.acs_bulk_estimate` carries 63 GB of indexes whose usage counters are empty; check which are used before
  dropping any.
- `stage.fec_row` (74 GB, keyed jsonb) has a compact-layout and partitioning decision pending (ADR-0003).
- A Parquet side cache (ADR-0004: a derived, rebuildable cache, never an authority) may hold the very
  large sources in a fraction of the space. Benchmark before adopting.
- Move PostgreSQL 17's WAL and control files off `/` (planned in the inventory note; a database
  operation with its own runbook).

## Rules going forward

- Every source estimated over 50 GB names its target volume and its backup tier in its spec (ADR-0004).
- Raw files always go to `DATA_ROOT` on the RAID volume; never to `/`.
- Before a large backfill, check free space (`storage_preview` does this for downloads) and the
  backup status (`docs/runbook.md`).
- Do not delete `stage` copies, indexes or old artifact versions to save space without the
  operator's approval and a measured reason; retained artifact files are never deleted.

## Open decisions for the operator

1. Off-machine target for Tier A (which device or service).
2. Is point-in-time recovery (Tier C) wanted, or is "rebuild `fact` and `stage` from raw" acceptable?
3. May we fix or replace the infra backup job so it covers port 5434 and writes to the RAID pool?
   (It lives outside this repository, in `~/workspace/infra`.)
4. Approval to drop rebuildable duplicates in `stage` once Tier A exists.
