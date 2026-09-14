#!/usr/bin/env bash
# Exhaustive pytest lane used by the PostGIS CI job. Keep in sync with `just check-full`.
set -euo pipefail
cd "$(dirname "$0")/../.."
uv run --extra ingest --extra spatial pytest
