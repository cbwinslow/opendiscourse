# Storage and backup plan (decided and implemented, 2026-09-19)

Status: **the operator decided; the backup is built, scheduled and proven** (see "What is in place").
Facts marked (measured) were read from the live server on 2026-09-19. Items marked (not verified) are
inferences. Server layout and sizes come from `docs/data-inventory-2026-09-19.md` and
`docs/performance-audit-2026-09-19.md`.

## Decisions (operator, 2026-09-19)

1. **One backup copy only**, because the database will keep growing. The database is rebuilt from the
   downloaded raw files rather than backed up in full: keep the schema plus the small hard-to-rebuild data.
   An off-machine copy (for example Google Drive through `rclone`) is welcome but optional and needs the
   operator to sign in once (`rclone config`); not done.
2. **No point-in-time recovery.** "Rebuild `fact` and `stage` from raw" is acceptable.
3. **Fix the backup job**, keeping one copy and keeping the root disk in mind. Done, see below.
4. **Rebuildable duplicates in `stage` may be dropped** once the backup is proven (done: the drill passed)
   **and** there are scripts that make re-downloading and re-ingesting easy. The second condition is not met
   yet (see "Still to do"), so nothing has been dropped.

## What is in place

- **`scripts/ops/backup_opendiscourse.sh`**: dumps the whole schema plus the rows of everything hard to rebuild
  (identities, bills, terms, the artifact registry, the run ledger, small fact tables). It leaves out the rows
  (not the empty tables) of `stage.*`, `fact.acs_bulk_estimate`, `fact.business_pattern` and
  `core.geography_boundary`, which loaders rebuild from raw. Result: **about 0.75 GB instead of 238 GB**, in about
  2 minutes. It writes to `/mnt/storage/data-lake/backups/opendiscourse/` (a different volume from the
  workspace, on the same RAID pool, 817 GB free), refuses any target on the root disk, uses the right `pg_dump`
  version (the default one on this machine is older than the server), and holds **exactly one copy**: the new
  dump is written beside the old one, checked, then renamed over it, so a failed run keeps the old backup.
  Files are readable only by their owner.
- **Nightly at 03:30** from the operator's crontab (log: `~/workspace/data-lake/opendiscourse/meta/backup.log`).
  The older infra jobs (`validated_backup.sh`) still cover PostgreSQL 16 only and were not touched.
- **`scripts/ops/restore_drill.sh`**: restores the dump into a throwaway PostGIS container and compares row counts
  with the manifest. **Passed 2026-09-19** (172,709 bills, 172,703 records, 45,535 memberships, 12,771 people,
  99,368 identifiers, 2,655 artifacts, 301 runs; migration head matches). It is also the recipe for restoring on a
  new machine.

## Power cuts and restarts (measured 2026-09-19)

PostgreSQL 17 is set up to survive a sudden power loss: `fsync`, `synchronous_commit` and `full_page_writes` are
on, so after a cut it replays its write-ahead log and starts clean. The cluster starts automatically at boot
(`start.conf` = auto), and systemd mounts local disks before regular services. The RAID 5 array is healthy (5 of 5
disks, write-intent bitmap on), the filesystems are ext4, and WAL is capped at 16 GB (`max_wal_size`) on a root disk
with 120 GB free. What remains, in order of value:

- **A UPS** is the real protection. Without one, a cut during heavy writes can leave a RAID 5 stripe inconsistent
  (the "write hole"); it only matters if a disk also fails before the next resync, but it is why hardware
  matters more than settings. (not verified whether a UPS is present)
- **Optional hardening, needs sudo (not applied):** tell systemd explicitly that PostgreSQL 17 needs the workspace
  mount (its data is on it), by adding a drop-in `RequiresMountsFor=/home/cbwinslow/workspace` for
  `postgresql@17-main`. The default ordering already mounts it first, so this is belt and braces.
- `data_checksums` is off, so silent disk corruption would go unnoticed; turning it on needs the cluster stopped and
  is a maintenance-window job, not urgent.
- Keep watching the root disk (77% used); it holds the WAL. A full root disk stops the database (no corruption; free
  space and it restarts).

## What we found (before the fix)

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

## How the tiers were decided

Tier A (small, hard to rebuild: `core`, `ingest`, `catalog`, small `fact` tables) is what the nightly dump holds.
Tier B (big and rebuildable: `fact` and `stage`) is deliberately not dumped; the raw files and the registry are its
backup, and reloading is the restore. Tier C (physical backup with WAL archiving for point-in-time recovery) was
declined by the operator.

## Ways to make the database smaller (measure first; nothing dropped yet)

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

## Still to do

1. **A rebuild kit**, which is the condition for dropping the `stage` duplicates: one documented command sequence
   that downloads and ingests every loaded source on a fresh machine (`research-db sync-billstatus`,
   `load-legislators`, the Census `*-bulk-*` commands, and so on), tested from an empty `DATA_ROOT`. A project skill
   (`opendiscourse-rebuild`) can then point agents at it. Until this exists and works, `stage` stays.
2. Optional off-machine copy of the 0.75 GB dump (Google Drive via `rclone`; needs the operator to sign in once).
3. Optional: the systemd mount drop-in above; a UPS if none is present.
4. Re-measure the dump size each month; if it passes about 5 GB, revisit the exclusion list.
