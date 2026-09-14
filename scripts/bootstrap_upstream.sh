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

echo "Upstream checkouts ready under $vendor"
