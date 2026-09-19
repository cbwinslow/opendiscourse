# Server data inventory and organization plan

Read-only inventory taken 2026-09-19. Sizes are allocated filesystem sizes
unless noted. This is an inventory and target layout, not authorization to move
or delete any data.

## Storage and mounts

| Mount | Backing storage | Size / free | Intended role |
|---|---|---:|---|
| `/` | `ubuntu-vg/ubuntu-lv` | 547 GB / 113 GB | OS and small runtime state |
| `/home/cbwinslow/workspace` | `vg-data/lv-workspace` on six-disk RAID/LVM | 2.9 TB / 2.1 TB | source checkouts, active evidence lake, OpenDiscourse tablespace |
| `/mnt/storage` | `vg-data/lv-sql` on the same RAID/LVM | 1.5 TB / 584 GB | PostgreSQL 16 and legacy government lake |

Both volume groups have zero unallocated LVM extents. Capacity can be
rebalanced only by moving data between these existing filesystems or by adding
storage; an in-place LV extension is not available.

## Data locations

| Location | Size | Classification | Notes |
|---|---:|---|---|
| `~/workspace/data-lake/opendiscourse/raw/census` | 121 GB | active raw evidence | Census collections used by OpenDiscourse |
| `~/workspace/data-lake/opendiscourse/raw/openstates` | 10 GB | active raw evidence | OpenStates dump artifacts |
| `~/workspace/data-lake/opendiscourse/meta` | 107 MB | operational metadata | health, plans, validation, and audit records |
| `~/workspace/data-lake/opendiscourse/pg17` | 310 GB | **active PostgreSQL tablespace** | `odspace`; not a removable lake cache |
| `/mnt/storage/data-lake/government` | 692 GB | legacy evidence lake | configured as `legacy_cache_unverified`; verify before promoting |
| `/mnt/storage/data-lake/government/epstein` | 658 GB | sensitive hold corpus | inventory only; do not process, move, or delete without its own approved plan |
| `/mnt/storage/data-lake/government/fec_bulk_data` | about 20 GB | legacy raw evidence | 50 FEC archives; person joins remain gated |
| `~/workspace/government/data` | 11 GB | legacy checkout-local data | needs source-by-source classification before consolidation |
| `~/workspace/government/epstein` | 29 GB | legacy project/output | separate from the 658 GB hold corpus |
| `~/workspace/government/openstates-monorepo` | 9.1 GB | upstream/source checkout | not an OpenDiscourse data artifact |
| `~/workspace/government/epstein_backup_20260525.tar.gz` | 1.2 GB | backup candidate | retain until its contents and backup policy are verified |

The `government` checkout already links `congress`, `courtlistener`,
`fec_bulk_data`, and `financial-disclosures` to the legacy lake. Keep those as
compatibility links while consumers are migrated; do not copy their targets
into the checkout.

## PostgreSQL inventory

### PostgreSQL 17 (active OpenDiscourse cluster)

- Service: `postgresql@17-main`, local-only port `5434`.
- Control directory: `/var/lib/postgresql/17/main` (58 MB), on `/`.
- WAL: `/var/lib/postgresql/17/main/pg_wal` (16 GB), on `/`.
- Tablespace: `odspace` at
  `~/workspace/data-lake/opendiscourse/pg17` (310 GB).
- Databases: `opendiscourse` 234 GB; `openstates` 38 GB;
  `openstates_stage_202607` 38 GB; minor utility/test databases.
- `opendiscourse` is chiefly `fact` (180 GB), `stage` (123 GB), `core` (11 GB),
  and TOAST (20 GB). It uses PostGIS, pgvector, pg_trgm, pgcrypto,
  `postgres_fdw`, and unaccent.
- `openstates_stage_202607` is a 38 GB potential duplicate/candidate for
  retirement, but must be reconciled against `openstates` and all FDW/client
  references before any action.

### PostgreSQL 16 (active legacy/service cluster)

- Service: `postgresql@16-main`, port `5432`, listening on all interfaces;
  PgBouncer also listens on `6432`. Cloudflared and monitoring services are
  active dependencies.
- Data directory: `/mnt/storage/postgres-data` (128 GB), including 11 GB WAL.
- Largest databases: `govdata` 62 GB, `mlb` 58 GB, `promscale` 5 GB.
- `govdata` contains 47 GB `epstein` and 39 GB `openstates` schemas. `mlb`
  contains 51 GB `raw`, 8.6 GB `core`, and 3 GB `gold`.
- Migration requires PostgreSQL 17-compatible versions and post-restore tests
  for TimescaleDB, Apache AGE, pg_cron, PostGIS, pgvector, pgagent, and related
  extension-dependent jobs.

## Target organization

Use a single documented namespace with separate *roles*, rather than copying
large files merely to make paths look uniform:

```text
~/workspace/
  opendiscourse/                         # versioned code and specifications
  government/                            # legacy code/upstream checkouts only
  data-lake/
    opendiscourse/
      raw/                               # immutable official evidence
      meta/                              # manifests, checksums, run/audit data
      hold/                              # approved restricted material only
      curate/ and stage/                 # explicitly rebuildable local outputs
    legacy-government/                   # logical alias to /mnt/storage/data-lake/government

/mnt/storage/
  postgresql/
    16/main/                             # temporary, until retirement
    17/main/                             # control files and WAL after relocation
    17/tablespaces/odspace/              # OpenDiscourse database pages after relocation
  data-lake/legacy-government/           # physical legacy evidence location
```

`legacy-government` should initially be a documented compatibility alias (or a
bind mount), not a 692 GB copy. The active `odspace` directory is currently
under the lake only because it is a PostgreSQL tablespace; its target name
belongs under `postgresql/`, distinct from raw artifacts. Never place database
pages, backups, or WAL below `raw/`.

## Recommended sequence

1. Adopt this inventory as the path registry; add source-level manifests and
   checksums before classifying legacy data as usable evidence.
2. Keep `~/workspace/government` code-only. Replace any future data writes there
   with a registered active-lake or legacy-lake path; retain existing symlinks
   while needed.
3. In a scheduled maintenance window, back up and validate PostgreSQL 17, then
   relocate its **active** tablespace and control/WAL directories to the
   `/mnt/storage/postgresql/17/` role paths. This is a database operation, not a
   file move; it requires a tested stop/copy/symlink-or-recreate/verify runbook.
4. After 17 is stable on its final paths, migrate PostgreSQL 16 database by
   database using a tested logical dump/restore or a separately validated
   `pg_upgrade` plan. Inventory extensions, roles, jobs, FDWs, PgBouncer, and
   Cloudflared routes first. Stream dumps where practical so the 584 GB free on
   `/mnt/storage` is not consumed by duplicate dump files.
5. Cut clients over only after row-count/checksum/application verification;
   preserve PostgreSQL 16 read-only for an agreed rollback period. Remove its
   cluster and files only after the rollback decision is documented and a
   verified backup exists.

## Explicit non-actions

- Do not delete or overwrite retained evidence, the active `odspace` tablespace,
  the 38 GB OpenStates staging database, or any Epstein data based on this
  inventory.
- Do not move the legacy lake wholesale merely for cosmetic path consistency.
- Do not change PostgreSQL ports, mounts, or service definitions before a
  maintenance plan and dependency cutover checklist are approved.
