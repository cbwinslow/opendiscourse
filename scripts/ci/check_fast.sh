#!/usr/bin/env bash
# Fast CI/local lane. Keep in sync with the justfile `check-fast` recipe.
set -euo pipefail
cd "$(dirname "$0")/../.."
uv run ruff check src
uv run pytest -m "not db and not slow and not live and not e2e" -n auto --dist worksteal
