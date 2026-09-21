#!/usr/bin/env bash
# Launch a project-scoped MCP server from its audited vendor/mcp clone.
# Keys stay in the environment. Missing clones: run scripts/bootstrap_upstream.sh.
set -euo pipefail

name="${1:-}"
root="$(cd "$(dirname "$0")/.." && pwd)"
dest="$root/vendor/mcp/$name"

if [[ -z "$name" ]]; then
  echo "usage: scripts/mcp_run.sh congress|fec|openstates" >&2
  exit 2
fi
if [[ "$name" == "census" ]]; then
  echo "The official Census MCP is disabled: it starts a second Postgres." >&2
  echo "Census facts belong in database opendiscourse on port 5434." >&2
  exit 1
fi
if [[ ! -d "$dest/.git" ]]; then
  echo "MCP source missing: $dest" >&2
  echo "Run scripts/bootstrap_upstream.sh, then the first-use steps in docs/mcp-servers.md." >&2
  exit 1
fi

case "$name" in
  congress)
    exec uv --directory "$dest" run congressmcp
    ;;
  fec)
    if [[ ! -f "$dest/build/index.js" ]]; then
      echo "FEC MCP is not built at $dest/build/index.js" >&2
      echo "From that directory run: npm ci && npm run build" >&2
      exit 1
    fi
    exec node "$dest/build/index.js"
    ;;
  openstates)
    exec uv --directory "$dest" run python -m app --transport stdio
    ;;
  *)
    echo "unknown MCP server: $name" >&2
    exit 2
    ;;
esac
