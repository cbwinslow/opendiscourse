#!/usr/bin/env bash
# Back up the OpenDiscourse database: ONE copy, small, and never on the root disk.
#
#   scripts/ops/backup_opendiscourse.sh             write the backup (replaces the previous one)
#   scripts/ops/backup_opendiscourse.sh --dry-run   show what would happen; write nothing
#
# What is in it: the whole schema (every table, index and view) plus the rows of everything that is
# hard to rebuild: identities, bills, terms, the artifact registry and run ledger, small fact tables.
# What is left out (rows only; the empty tables stay): the large tables that a loader rebuilds from
# the raw files in DATA_ROOT. See docs/storage-and-backup-plan.md.
#
# One copy only: the new dump is written beside the old one, checked, and only then renamed over it.
# A failed run leaves the previous backup untouched. Raw files are not copied (they are immutable,
# checksummed in ingest.artifact, and re-downloadable); protect DATA_ROOT separately if wanted.
#
# Configuration (environment, or the same names in the repo's .env):
#   OPENDISCOURSE_BACKUP_DSN          default postgresql:///opendiscourse?port=5434
#   OPENDISCOURSE_BACKUP_DIR          default <parent of DATA_ROOT>/backup
#   OPENDISCOURSE_BACKUP_EXCLUDE_DATA space-separated table patterns to leave rows out of
#   ALLOW_ROOT_BACKUP=1               permit a target on the same disk as / (refused by default)
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DRY_RUN=0
[ "${1:-}" = "--dry-run" ] && DRY_RUN=1

env_value() { [ -f "$REPO/.env" ] && sed -n "s/^$1=//p" "$REPO/.env" | tail -1 | tr -d "\"'" || true; }
say() { printf '%s\n' "$*"; }
die() { printf 'backup failed: %s\n' "$*" >&2; exit 1; }

DSN="${OPENDISCOURSE_BACKUP_DSN:-postgresql:///opendiscourse?port=5434}"
DATA_ROOT="${DATA_ROOT:-$(env_value DATA_ROOT)}"
BACKUP_DIR="${OPENDISCOURSE_BACKUP_DIR:-$(env_value OPENDISCOURSE_BACKUP_DIR)}"
if [ -z "$BACKUP_DIR" ]; then
  [ -n "$DATA_ROOT" ] || die "set OPENDISCOURSE_BACKUP_DIR, or DATA_ROOT, in the environment or .env"
  BACKUP_DIR="$(dirname "$DATA_ROOT")/backup"
fi
# Rows we do not dump: rebuildable from raw files by their loaders (sizes measured 2026-09-19).
EXCLUDE_DATA="${OPENDISCOURSE_BACKUP_EXCLUDE_DATA:-stage.* fact.acs_bulk_estimate fact.business_pattern core.geography_boundary}"

# pg_dump must be at least as new as the server; the default one on PATH may be older.
SERVER_NUM="$(psql "$DSN" -X -Atc 'show server_version_num' 2>/dev/null)" || die "cannot connect to $DSN"
MAJOR=$((SERVER_NUM / 10000))
PG_DUMP=""
for candidate in "/usr/lib/postgresql/$MAJOR/bin/pg_dump" "$(command -v pg_dump || true)"; do
  [ -x "$candidate" ] || continue
  have="$("$candidate" --version | sed -E 's/[^0-9]*([0-9]+).*/\1/')"
  if [ "$have" -ge "$MAJOR" ]; then PG_DUMP="$candidate"; break; fi
done
[ -n "$PG_DUMP" ] || die "no pg_dump >= $MAJOR found (install postgresql-client-$MAJOR)"
PG_RESTORE="$(dirname "$PG_DUMP")/pg_restore"

# Never on the root disk: it is small and holds the database's write-ahead log. Judge by the
# nearest directory that exists, so a dry run creates nothing.
probe="$BACKUP_DIR"
while [ ! -d "$probe" ]; do probe="$(dirname "$probe")"; done
root_dev="$(stat -c %d /)"
target_dev="$(stat -c %d "$probe")"
if [ "$root_dev" = "$target_dev" ] && [ "${ALLOW_ROOT_BACKUP:-0}" != "1" ]; then
  die "$BACKUP_DIR is on the root filesystem; choose a directory on the RAID volume (or set ALLOW_ROOT_BACKUP=1)"
fi
free_gb=$(( $(df --output=avail -B1G "$probe" | tail -1 | tr -d ' ') ))
[ "$free_gb" -ge 10 ] || die "only ${free_gb} GB free for $BACKUP_DIR (need 10)"

FINAL="$BACKUP_DIR/opendiscourse.dump"
MANIFEST="$BACKUP_DIR/opendiscourse.manifest.json"
PARTIAL="$FINAL.partial"

say "database : $DSN (PostgreSQL $MAJOR)"
say "tool     : $PG_DUMP"
say "target   : $FINAL (${free_gb} GB free; one copy, replaced only after a verified new dump)"
say "rows left out (tables kept): $EXCLUDE_DATA"
[ "$DRY_RUN" = 1 ] && { say "dry run: nothing written"; exit 0; }

umask 077  # the dump holds the foreign-server definitions for the OpenStates connection
mkdir -p "$BACKUP_DIR"
exec 9>"$BACKUP_DIR/.lock"
flock -n 9 || die "another backup is running"
trap 'rm -f "$PARTIAL" "$MANIFEST.partial"' EXIT
rm -f "$PARTIAL" "$MANIFEST.partial"

excludes=()
for pattern in $EXCLUDE_DATA; do excludes+=(--exclude-table-data="$pattern"); done

started="$(date -u +%FT%TZ)"
"$PG_DUMP" "$DSN" --format=custom --no-owner --no-acl --no-tablespaces "${excludes[@]}" --file="$PARTIAL"
"$PG_RESTORE" --list "$PARTIAL" >/dev/null || die "the new dump does not read back; the previous backup was kept"

# What a restore must reproduce, for restore_drill.sh to compare.
psql "$DSN" -X -Atq -c "select json_build_object(
  'started_at', '$started'::text,
  'finished_at', to_char(now() at time zone 'utc', 'YYYY-MM-DD\"T\"HH24:MI:SS\"Z\"'),
  'server_version', current_setting('server_version'),
  'alembic_head', (select version_num from alembic_version),
  'rows_left_out', '$EXCLUDE_DATA',
  'counts', json_build_object(
    'core.bill', (select count(*) from core.bill),
    'core.bill_source_record', (select count(*) from core.bill_source_record),
    'core.bill_action', (select count(*) from core.bill_action),
    'core.membership', (select count(*) from core.membership),
    'core.person', (select count(*) from core.person),
    'core.person_identifier', (select count(*) from core.person_identifier),
    'ingest.artifact', (select count(*) from ingest.artifact),
    'ingest.run', (select count(*) from ingest.run)))" >"$MANIFEST.partial"

mv -f "$PARTIAL" "$FINAL"
mv -f "$MANIFEST.partial" "$MANIFEST"
trap - EXIT
say "done: $(du -h "$FINAL" | cut -f1) at $FINAL (previous copy replaced; manifest $MANIFEST)"
