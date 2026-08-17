#!/usr/bin/env bash
# Idempotently drive one Census bulk plan through its full lifecycle:
#   preview -> approve -> download -> stage -> load -> census-health
# skipping any stage the plan file's `state:` shows as already passed, so
# this is safe to re-run against a plan at any point (interrupted download,
# already-loaded plan, etc.).
#
# Usage:
#   ops/census-bulk-refresh.sh <prefix> <plan-file> [options]
#
#   <prefix>     acs-bulk | cbp-bulk | pep-bulk | tiger-bulk
#   <plan-file>  path to a plan YAML under meta/bulk-plans/
#
# Options:
#   --geography TYPES   Comma-separated canonical geography types for the
#                        approval step (default: state,county). Only used
#                        the first time a plan is approved; ignored once a
#                        plan has already passed `approved`.
#   --workers N          Concurrent workers for download/stage/load.
#                        Only acs-bulk currently supports this (>1 uses
#                        the ProcessPoolExecutor/ThreadPoolExecutor paths
#                        added this session); passing it for cbp-bulk,
#                        pep-bulk, or tiger-bulk is a no-op since those
#                        loaders are still single-worker.
#
# Examples:
#   ops/census-bulk-refresh.sh acs-bulk meta/bulk-plans/acs5-relevant2024.yaml --workers 6
#   ops/census-bulk-refresh.sh cbp-bulk meta/bulk-plans/cbp-cbp2015.yaml
#
# For ACS specifically, this script also implements the "retry-then-exclude"
# discipline established this session: Census's server intermittently fails
# to report a Content-Length for a subset of Detailed Table files (dominated
# by the B24 industry-by-occupation and B27 health-insurance wide cross-tab
# families). A single retry has repeatedly resolved most of an initial
# unknown-size spike; whatever remains unresolved after that retry is
# checked against the documented `ACS_SIZE_PROBE_UNRESOLVABLE` set in
# `ingestion/census.py` for that year. If every remaining unresolved table
# is already documented, the plan is rebuilt without them and re-previewed.
# If a genuinely NEW unresolved table shows up (one this script has never
# seen documented for that year), this script stops and asks for a human to
# review it and extend `ACS_SIZE_PROBE_UNRESOLVABLE` -- it never silently
# force-approves an unknown size.

set -euo pipefail

PREFIX="${1:?Usage: $0 <prefix> <plan-file> [--geography TYPES] [--workers N]}"
PLAN="${2:?Usage: $0 <prefix> <plan-file> [--geography TYPES] [--workers N]}"
shift 2

GEOGRAPHY="state,county"
WORKERS=1
while [[ $# -gt 0 ]]; do
  case "$1" in
    --geography) GEOGRAPHY="$2"; shift 2 ;;
    --workers) WORKERS="$2"; shift 2 ;;
    *) echo "Unknown option: $1" >&2; exit 1 ;;
  esac
done

if [[ ! -f "$PLAN" ]]; then
  echo "Plan file not found: $PLAN" >&2
  exit 1
fi

RUN="uv run research-db ingest"
WORKERS_FLAG=()
if [[ "$PREFIX" == "acs-bulk" && "$WORKERS" -gt 1 ]]; then
  WORKERS_FLAG=(--workers "$WORKERS")
fi

GEOGRAPHY_FLAGS=()
IFS=',' read -ra GEO_PARTS <<< "$GEOGRAPHY"
for part in "${GEO_PARTS[@]}"; do
  GEOGRAPHY_FLAGS+=(--geography "$part")
done

plan_state() {
  uv run python -c "import yaml,sys; print((yaml.safe_load(open(sys.argv[1])) or {}).get('state','draft'))" "$PLAN"
}

# Retries an ACS preview once, then -- if the only remaining unresolved
# tables are ones already documented in ACS_SIZE_PROBE_UNRESOLVABLE for
# this plan's release year -- rebuilds the plan without them and previews
# again. Exits non-zero (without excluding anything) if a genuinely new
# unresolved table appears, so a human reviews it before it's ever dropped.
acs_preview_with_retry_then_exclude() {
  local attempt approved
  for attempt in 1 2; do
    echo "[census-bulk-refresh] ACS preview attempt $attempt for $PLAN"
    $RUN acs-bulk-preview --plan "$PLAN" > /dev/null
    approved=$(uv run python -c "
import json
report = json.load(open('${PLAN%.yaml}.preview.json'))
print('true' if report.get('approved') else 'false')
")
    if [[ "$approved" == "true" ]]; then
      return 0
    fi
  done

  echo "[census-bulk-refresh] Still unresolved after retry; checking against the documented unresolvable set..."
  local outcome
  outcome=$(uv run python - "$PLAN" <<'PYEOF'
import re
import sys
import json
from pathlib import Path

import yaml

from opendiscourse_research.ingestion.census import (
    ACS_SIZE_PROBE_UNRESOLVABLE,
    relevant_acs_tables,
)
from opendiscourse_research.ingestion.acs_bulk import write_acs5_bulk_plan

plan_path = Path(sys.argv[1])
plan = yaml.safe_load(plan_path.read_text())
preview = json.loads(plan_path.with_suffix(".preview.json").read_text())
unknown_urls = preview.get("unknown_urls") or []
unknown_ids = {
    match.group(1).upper()
    for url in unknown_urls
    if (match := re.search(r"-([a-z]\d+[a-z]*)\.dat$", url, re.IGNORECASE))
}

years = {int(item["release_year"]) for item in plan.get("artifacts", []) if "release_year" in item}
if len(years) != 1:
    print(f"MULTI_YEAR_PLAN:{sorted(years)}")
    sys.exit(0)
year = next(iter(years))
documented = ACS_SIZE_PROBE_UNRESOLVABLE.get(year, frozenset())
new_unresolved = unknown_ids - documented
if new_unresolved:
    print(f"NEW_UNRESOLVED:{year}:{sorted(new_unresolved)}")
    sys.exit(0)

# Every unresolved table is already documented -- rebuild the plan without
# them. Preserve the basket name so the plan file path is unchanged.
basket = plan["basket"]
selected = plan.get("selection", {}).get("detailed_tables", [])
if selected:
    # A relevant-tables-style plan: rebuild from its own selected list minus
    # the documented-unresolvable set for this year.
    keep_ids = [
        entry["table_id"]
        for entry in selected
        if entry["table_id"] not in documented
    ]
else:
    keep_ids = [t for t in relevant_acs_tables(year) if t not in documented]

resources = [
    {"dataset_id": "census.acs_5", "resource_type": "Detailed Table", "resource_key": f"{year}:{t}"}
    for t in keep_ids
]
write_acs5_bulk_plan(basket, resources)
print(f"REBUILT:{year}:{len(keep_ids)}")
PYEOF
)
  echo "[census-bulk-refresh] $outcome"
  case "$outcome" in
    REBUILT:*)
      echo "[census-bulk-refresh] Rebuilt $PLAN excluding documented-unresolvable tables; re-previewing."
      $RUN acs-bulk-preview --plan "$PLAN" > /dev/null
      approved=$(uv run python -c "
import json
report = json.load(open('${PLAN%.yaml}.preview.json'))
print('true' if report.get('approved') else 'false')
")
      if [[ "$approved" != "true" ]]; then
        echo "[census-bulk-refresh] Still not approved after excluding documented tables -- inspect ${PLAN%.yaml}.preview.json manually." >&2
        exit 1
      fi
      ;;
    NEW_UNRESOLVED:*)
      echo "[census-bulk-refresh] New, undocumented unresolved table(s) found: ${outcome#NEW_UNRESOLVED:}" >&2
      echo "[census-bulk-refresh] Review these manually and extend ACS_SIZE_PROBE_UNRESOLVABLE in census.py before re-running -- refusing to force-approve." >&2
      exit 1
      ;;
    MULTI_YEAR_PLAN:*)
      echo "[census-bulk-refresh] Plan spans multiple release years (${outcome#MULTI_YEAR_PLAN:}); retry-then-exclude only supports single-year plans. Inspect manually." >&2
      exit 1
      ;;
    *)
      echo "[census-bulk-refresh] Unexpected outcome: $outcome" >&2
      exit 1
      ;;
  esac
}

state="$(plan_state)"
echo "[census-bulk-refresh] $PLAN starting at state=$state"

if [[ "$state" == "draft" ]]; then
  if [[ "$PREFIX" == "acs-bulk" ]]; then
    acs_preview_with_retry_then_exclude
  else
    $RUN "${PREFIX}-preview" --plan "$PLAN"
  fi
  $RUN "${PREFIX}-approve" --plan "$PLAN" "${GEOGRAPHY_FLAGS[@]}"
  state="approved"
fi

if [[ "$state" == "approved" ]]; then
  $RUN "${PREFIX}-download" --plan "$PLAN" "${WORKERS_FLAG[@]}"
  state="downloaded"
fi

if [[ "$state" == "downloaded" ]]; then
  $RUN "${PREFIX}-stage" --plan "$PLAN" "${WORKERS_FLAG[@]}"
  state="staged"
fi

if [[ "$state" == "staged" ]]; then
  $RUN "${PREFIX}-load" --plan "$PLAN" "${WORKERS_FLAG[@]}"
  state="loaded"
fi

echo "[census-bulk-refresh] $PLAN reached state=$state"
uv run research-db census-health
