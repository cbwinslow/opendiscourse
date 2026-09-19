#!/usr/bin/env bash
# Prove the backup works: restore it into a throwaway PostGIS container and compare row counts
# with the manifest written by backup_opendiscourse.sh. Nothing touches the real database.
#
#   scripts/ops/restore_drill.sh [path/to/opendiscourse.dump]
#
# Needs docker. Exit 0 = every count matches; 1 = a mismatch or an unexpected restore error.
# This is also the recipe for restoring on a new machine: create a database, run
# `pg_restore --no-owner --no-acl -d <db> opendiscourse.dump`, then rebuild the left-out large
# tables by rerunning their loaders from the raw files (see docs/storage-and-backup-plan.md).
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
IMAGE="${DRILL_IMAGE:-postgis/postgis:17-3.5}"
env_value() { [ -f "$REPO/.env" ] && sed -n "s/^$1=//p" "$REPO/.env" | tail -1 | tr -d "\"'" || true; }

DUMP="${1:-}"
if [ -z "$DUMP" ]; then
  dir="${OPENDISCOURSE_BACKUP_DIR:-$(env_value OPENDISCOURSE_BACKUP_DIR)}"
  [ -n "$dir" ] || { echo "give the dump path, or set OPENDISCOURSE_BACKUP_DIR" >&2; exit 1; }
  DUMP="$dir/opendiscourse.dump"
fi
MANIFEST="${DUMP%.dump}.manifest.json"
[ -f "$DUMP" ] && [ -f "$MANIFEST" ] || { echo "missing $DUMP or $MANIFEST" >&2; exit 1; }
command -v docker >/dev/null || { echo "docker is required for the drill" >&2; exit 1; }

NAME="od-restore-drill-$$"
LOG="$(mktemp)"
cleanup() { docker rm -f "$NAME" >/dev/null 2>&1 || true; rm -f "$LOG"; }
trap cleanup EXIT

echo "starting $IMAGE ..."
docker run -d --name "$NAME" -e POSTGRES_PASSWORD=drill -e POSTGRES_DB=drill "$IMAGE" >/dev/null
# The image starts a temporary server for its init scripts, stops it, and starts the real one:
# the message "ready to accept connections" appears twice, and only the second is the real server.
for _ in $(seq 1 120); do
  [ "$(docker logs "$NAME" 2>&1 | grep -c 'ready to accept connections')" -ge 2 ] && break
  sleep 1
done
docker exec "$NAME" pg_isready -U postgres -d drill >/dev/null || { echo "container did not become ready" >&2; exit 1; }

docker cp "$DUMP" "$NAME:/tmp/od.dump"
echo "restoring $(du -h "$DUMP" | cut -f1) ..."
# Some errors are expected here: an extension the throwaway image does not ship (pgvector).
docker exec "$NAME" pg_restore --no-owner --no-acl -j 4 -U postgres -d drill /tmp/od.dump 2>"$LOG" || true

status=0
echo "restore messages: $(grep -c 'error:' "$LOG" || true) error line(s)"
grep 'error:' "$LOG" | grep -v -i -E 'extension "vector"|vector\.control|type "vector"' | sort | uniq -c | head -5 || true

echo "comparing with the manifest ($MANIFEST):"
python3 - "$MANIFEST" "$NAME" <<'PY' || status=1
import json, subprocess, sys
manifest, container = json.load(open(sys.argv[1])), sys.argv[2]
ok = True
for table, expected in manifest["counts"].items():
    out = subprocess.run(
        ["docker", "exec", container, "psql", "-U", "postgres", "-d", "drill", "-Atc", f"select count(*) from {table}"],
        capture_output=True, text=True,
    )
    got = int(out.stdout.strip()) if out.returncode == 0 and out.stdout.strip() else None
    flag = "ok  " if got == expected else "FAIL"
    ok &= got == expected
    print(f"  {flag} {table}: backup {expected:,}  restored {got if got is None else format(got, ',')}")
head = subprocess.run(
    ["docker", "exec", container, "psql", "-U", "postgres", "-d", "drill", "-Atc", "select version_num from alembic_version"],
    capture_output=True, text=True,
).stdout.strip()
print(f"  {'ok  ' if head == manifest['alembic_head'] else 'FAIL'} alembic head: backup {manifest['alembic_head']}  restored {head}")
ok &= head == manifest["alembic_head"]
sys.exit(0 if ok else 1)
PY
[ "$status" = 0 ] && echo "DRILL PASSED: the backup restores and matches." || { echo "DRILL FAILED" >&2; exit 1; }
