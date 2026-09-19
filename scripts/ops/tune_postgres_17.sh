#!/usr/bin/env bash
# Tune the PostgreSQL 17 cluster (port 5434, database opendiscourse) for this host.
#
#   scripts/ops/tune_postgres_17.sh              dry run: current vs proposed + memory budget
#   scripts/ops/tune_postgres_17.sh --apply      ALTER SYSTEM (needs sudo), reload, list what needs a restart
#   scripts/ops/tune_postgres_17.sh --apply --restart   ... and restart postgresql@17-main
#   scripts/ops/tune_postgres_17.sh --revert     ALTER SYSTEM RESET every value this script sets
#
# Settings belong to a CLUSTER, not a database. This script only ever writes to the
# 17 cluster. The 16 cluster on port 5432 (mlb, govdata) is read for the budget and never
# modified. Restarting 17 does not touch it.
set -euo pipefail

PORT="${TUNE_PORT:-5434}"
ADMIN="${TUNE_ADMIN:-sudo -u postgres psql -X -q -p $PORT -d postgres}"
READ="${TUNE_READ:-psql -X -At -p $PORT -d postgres}"
OTHER_PORT="${TUNE_OTHER_PORT:-5432}"
SERVICE="${TUNE_SERVICE:-postgresql@17-main}"

# name|proposed|why
SETTINGS=(
  "shared_buffers|12GB|fixed allocation; with MLB's 40GB the two clusters hold ~42% of RAM (restart)"
  "effective_cache_size|48GB|planner hint only, allocates nothing; both clusters share the OS cache"
  "maintenance_work_mem|2GB|index builds and manual VACUUM; per operation"
  "autovacuum_work_mem|1GB|caps each autovacuum worker (default would reuse maintenance_work_mem)"
  "work_mem|32MB|per sort/hash node, per parallel worker, per query; kept modest on purpose"
  "max_worker_processes|24|ceiling for all background and parallel workers (restart)"
  "max_parallel_workers|16|parallel workers cluster-wide"
  "max_parallel_workers_per_gather|4|workers per query"
  "max_parallel_maintenance_workers|4|workers per index build"
  "max_wal_size|16GB|bulk loads checkpoint less often; pg_wal is on / (122GB free), so not larger"
  "min_wal_size|2GB|avoid recycling churn during loads"
  "checkpoint_timeout|15min|spread checkpoints during bulk loads"
  "shared_preload_libraries|pg_stat_statements|records per-query cost so tuning uses evidence (restart; empty today). Then: CREATE EXTENSION pg_stat_statements"
  "track_io_timing|on|adds I/O time to EXPLAIN and pg_stat_statements; small overhead, useful on spinning disks"
)
# Deliberately NOT changed: random_page_cost stays 4 and effective_io_concurrency stays 1
# because every disk here is a spinning HDD (lsblk ROTA=1); lowering them would mislead the planner.
# Parameters that require a restart to change.
RESTART_ONLY="shared_buffers max_worker_processes shared_preload_libraries"

mode=dry; restart=0
for arg in "$@"; do
  case "$arg" in
    --apply) mode=apply ;;
    --revert) mode=revert ;;
    --restart) restart=1 ;;
    -h|--help) sed -n '2,12p' "$0"; exit 0 ;;
    *) echo "unknown option: $arg" >&2; exit 2 ;;
  esac
done

version="$($READ -c 'show server_version_num')"
if [ "${version:-0}" -lt 170000 ] || [ "${version:-0}" -ge 180000 ]; then
  echo "refusing: port $PORT is server_version_num=$version, expected PostgreSQL 17" >&2; exit 1
fi
if [ -z "${TUNE_TEST:-}" ] && [ "$($READ -c "select count(*) from pg_database where datname='opendiscourse'")" != "1" ]; then
  echo "refusing: no opendiscourse database on port $PORT (wrong cluster?)" >&2; exit 1
fi

current() { $READ -c "select setting || coalesce(unit,'') from pg_settings where name='$1'"; }
human() { $READ -c "select current_setting('$1')"; }

echo "Cluster: PostgreSQL 17, port $PORT.   Host RAM: $(free -g | awk '/^Mem:/{print $2" GB total, "$7" GB available now"}')"
echo
printf '%-34s %-12s %-12s %s\n' setting current proposed why
for row in "${SETTINGS[@]}"; do
  IFS='|' read -r name proposed why <<<"$row"
  printf '%-34s %-12s %-12s %s\n' "$name" "$(human "$name")" "$proposed" "$why"
done

echo
echo "Worst-case memory budget (theoretical peaks, GB). Rare, but it is what 'both at full tilt' means:"
python3 - "$PORT" "$OTHER_PORT" "$(printf '%s\n' "${SETTINGS[@]}")" <<'PY'
import subprocess, sys
port17, other, proposals = sys.argv[1], sys.argv[2], sys.argv[3]
def unit_kb(v):
    v = v.strip().upper()
    for suffix, mult in (("GB", 1 << 20), ("MB", 1 << 10), ("KB", 1)):
        if v.endswith(suffix):
            return float(v[:-2]) * mult
    return float(v)
def settings(port):
    q = ("select name, setting::numeric * case unit when '8kB' then 8 when 'kB' then 1 when 'MB' then 1024 "
         "when 'GB' then 1048576 else 1 end from pg_settings where name in ('shared_buffers','work_mem',"
         "'maintenance_work_mem','autovacuum_work_mem','autovacuum_max_workers','max_parallel_workers_per_gather',"
         "'max_parallel_maintenance_workers')")
    try:
        out = subprocess.run(["psql", "-X", "-At", "-F", "|", "-p", port, "-d", "postgres", "-c", q],
                             capture_output=True, text=True, timeout=15, check=True).stdout
    except Exception:
        return None
    return {k: float(v) for k, v in (l.split("|") for l in out.splitlines() if l)}
def budget(s, heavy=8):
    gb = 1 << 20
    fixed = s["shared_buffers"] / gb
    av = s["autovacuum_work_mem"] if s["autovacuum_work_mem"] > 0 else s["maintenance_work_mem"]
    autovac = s["autovacuum_max_workers"] * av / gb
    maint = (1 + s["max_parallel_maintenance_workers"]) * s["maintenance_work_mem"] / gb
    query = heavy * s["work_mem"] * (1 + s["max_parallel_workers_per_gather"]) * 2 / gb
    return fixed, autovac, maint, query
total = int(subprocess.run(["awk", "/MemTotal/{print $2}", "/proc/meminfo"], capture_output=True, text=True).stdout) / (1 << 20)
now17, mlb = settings(port17), settings(other)
prop = dict(now17) if now17 else None
if prop:
    m = {"shared_buffers": "shared_buffers", "work_mem": "work_mem", "maintenance_work_mem": "maintenance_work_mem",
         "autovacuum_work_mem": "autovacuum_work_mem",
         "max_parallel_workers_per_gather": "max_parallel_workers_per_gather",
         "max_parallel_maintenance_workers": "max_parallel_maintenance_workers"}
    for line in proposals.splitlines():
        name, val, _ = line.split("|", 2)
        if name in m:
            prop[m[name]] = unit_kb(val) if name not in ("max_parallel_workers_per_gather", "max_parallel_maintenance_workers") else float(val)
rows = [("16 (mlb) as configured", mlb), ("17 as configured", now17), ("17 as proposed", prop)]
print(f"  {'cluster':<24}{'shared':>8}{'autovac':>9}{'maint op':>10}{'8 queries':>11}{'worst':>8}")
sums = {}
for label, s in rows:
    if not s:
        print(f"  {label:<24} (unreachable)"); continue
    f, a, m_, q = budget(s); sums[label] = f + a + m_ + q
    print(f"  {label:<24}{f:8.1f}{a:9.1f}{m_:10.1f}{q:11.1f}{f+a+m_+q:8.1f}")
print(f"  host RAM {total:.0f} GB.")
if "16 (mlb) as configured" in sums and "17 as proposed" in sums:
    both = sums["16 (mlb) as configured"] + sums["17 as proposed"]
    fixed_both = (mlb["shared_buffers"] + prop["shared_buffers"]) / (1 << 20)
    print(f"  both clusters, theoretical worst case: {both:.0f} GB ({100*both/total:.0f}% of RAM)")
    print(f"  both clusters, always-allocated shared_buffers: {fixed_both:.0f} GB ({100*fixed_both/total:.0f}% of RAM)")
    if sums["16 (mlb) as configured"] > total * 0.8:
        av = mlb["autovacuum_max_workers"] * (mlb["autovacuum_work_mem"] if mlb["autovacuum_work_mem"] > 0 else mlb["maintenance_work_mem"]) / (1 << 20)
        print(f"  NOTE: the 16 cluster alone can theoretically exceed 80% of RAM: its {int(mlb['autovacuum_max_workers'])} autovacuum")
        print(f"        workers can each use maintenance_work_mem ({av:.0f} GB total if all vacuum at once). This script does")
        print("        not change it. A cheap safe fix on the 16 cluster (reload, no restart):")
        print("          sudo -u postgres psql -p 5432 -c \"ALTER SYSTEM SET autovacuum_work_mem='1GB'\" -c 'SELECT pg_reload_conf()'")
PY
echo

if [ "$mode" = dry ]; then
  echo "Dry run only; nothing changed. To apply: $0 --apply [--restart]"; exit 0
fi

need_restart() { $READ -c "select string_agg(name, ', ') from pg_settings where pending_restart"; }

if [ "$mode" = revert ]; then
  echo "Reverting: ALTER SYSTEM RESET for every setting above."
  {
    for row in "${SETTINGS[@]}"; do IFS='|' read -r name _ _ <<<"$row"; echo "ALTER SYSTEM RESET $name;"; done
    echo "SELECT pg_reload_conf();"
  } | $ADMIN
  echo "Done. Restart needed for: $(need_restart). Run: sudo systemctl restart $SERVICE"; exit 0
fi

if [ -z "${TUNE_TEST:-}" ]; then
  auto="/var/lib/postgresql/17/main/postgresql.auto.conf"
  backup="$auto.bak-$(date +%Y%m%d-%H%M%S)"
  sudo cp -a "$auto" "$backup" && echo "Backed up $auto -> $backup"
fi
echo "Applying with ALTER SYSTEM (writes postgresql.auto.conf, which overrides postgresql.conf)."
{
  for row in "${SETTINGS[@]}"; do IFS='|' read -r name proposed _ <<<"$row"; echo "ALTER SYSTEM SET $name = '$proposed';"; done
  echo "SELECT pg_reload_conf();"
} | $ADMIN
sleep 1
pending="$(need_restart)"
echo "Applied. Waiting for a restart: ${pending:-nothing}"
if [ -n "$pending" ] && [ "$restart" = 1 ]; then
  echo "Restarting $SERVICE (the 16 cluster is not affected)..."
  sudo systemctl restart "$SERVICE"
  for _ in $(seq 1 30); do pg_isready -q -p "$PORT" && break; sleep 2; done
  pg_isready -p "$PORT"
  for row in "${SETTINGS[@]}"; do IFS='|' read -r name _ _ <<<"$row"; printf '  %-34s %s\n' "$name" "$(human "$name")"; done
elif [ -n "$pending" ]; then
  echo "Restart when no load is running:  sudo systemctl restart $SERVICE"
fi
echo "To undo: $0 --revert   (then restart)"
