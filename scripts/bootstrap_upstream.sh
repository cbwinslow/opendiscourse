#!/usr/bin/env bash
# Clone or update wrapped upstream tools. Safe to re-run.
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
vendor="$root/vendor"
mkdir -p "$vendor"

clone_or_update() {
  local dest="$1"
  local url="$2"
  if [[ -d "$dest/.git" ]]; then
    git -C "$dest" fetch --depth 1 origin
    git -C "$dest" reset --hard origin/HEAD
  else
    git clone --depth 1 "$url" "$dest"
  fi
}

clone_or_update "$vendor/unitedstates-congress" "https://github.com/unitedstates/congress.git"
clone_or_update "$vendor/congress-legislators" "https://github.com/unitedstates/congress-legislators.git"

# MCP helper clones are pinned. Do not float them to origin/HEAD; re-audit, then
# change the SHA here and in docs/mcp-servers.md together.
clone_at_sha() {
  local dest="$1"
  local url="$2"
  local sha="$3"
  mkdir -p "$(dirname "$dest")"
  if [[ -d "$dest/.git" ]]; then
    if [[ "$(git -C "$dest" rev-parse HEAD)" == "$sha" ]]; then
      return
    fi
    git -C "$dest" fetch --depth 1 origin "$sha"
    git -C "$dest" checkout --detach "$sha"
    return
  fi
  git init -q "$dest"
  git -C "$dest" remote add origin "$url"
  git -C "$dest" fetch --depth 1 origin "$sha"
  git -C "$dest" checkout --detach FETCH_HEAD
}

clone_at_sha "$vendor/mcp/congress" "https://github.com/amurshak/congressMCP.git" \
  "838687d2037421ad79b0cb31dd90cf3bf5136533"
clone_at_sha "$vendor/mcp/fec" "https://github.com/sh-patterson/fec-mcp-server.git" \
  "79f9ffd8a1619531a0b4777c37c963b623a7d482"
clone_at_sha "$vendor/mcp/census" "https://github.com/uscensusbureau/us-census-bureau-data-api-mcp.git" \
  "5dcaa637871b9ded5dab415118f9008c06d13f2a"
clone_at_sha "$vendor/mcp/openstates" "https://github.com/Travis-Prall/openstates-mcp.git" \
  "77afca6d5999544d28380c4e930c41d51704b222"

echo "Upstream checkouts ready under $vendor"
