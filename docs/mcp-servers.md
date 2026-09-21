# OpenDiscourse MCP servers

MCP servers assist an AI agent with source discovery, schema inspection, spot
checks, and troubleshooting. They never replace the checked-in Connector
commands that download, retain, checksum, and ingest the warehouse data.

Both Codex (`.codex/config.toml`) and Claude Code (`.mcp.json`) launch the
audited clones under `vendor/mcp/` through `scripts/mcp_run.sh`. The files
contain environment-variable names, never secrets. Set the required key in the
shell or secret manager before starting either client; a missing key means that
server will not start.

| Server | Use | Required environment variable | Pinned local source |
|---|---|---|---|
| `opendiscourse-congress` | Congress.gov and GovInfo exploration, including bill text and committees | `CONGRESS_API_KEY` | `vendor/mcp/congress` at `838687d2037421ad79b0cb31dd90cf3bf5136533` |
| `opendiscourse-fec` | OpenFEC discovery and validation only | `FEC_API_KEY` | `vendor/mcp/fec` at `79f9ffd8a1619531a0b4777c37c963b623a7d482` |
| `opendiscourse-openstates` | OpenStates API discovery and FDW/connector spot checks | `OPENSTATES_API_KEY` | `vendor/mcp/openstates` at `77afca6d5999544d28380c4e930c41d51704b222` |

## First use

1. Obtain the four source API keys and store them in the operator's secret
   manager or shell profile, never a tracked file.
2. Clone the pinned sources: `scripts/bootstrap_upstream.sh`. That also
   refreshes the Congress ingest checkouts. The MCP SHAs are listed above;
   changing a SHA requires a re-audit and a matching docs change.
3. One-time per clone:
   - Congress: `uv sync` in `vendor/mcp/congress`
   - FEC: `npm ci && npm run build` in `vendor/mcp/fec`
   - OpenStates: `uv sync` in `vendor/mcp/openstates` (this clone currently
     fails to start because of an upstream library conflict; leave it unused)
   - Do not start the official Census MCP. It wants its own Postgres 16 Docker
     database (`mcp_db`). Warehouse facts stay in the one bare-metal
     PostgreSQL 17 database `opendiscourse` on port 5434. Census ACS/CBP/TIGER
     data already loaded there is the source of truth.
4. Restart Codex or Claude Code. Claude will ask for approval before using the
   project-scoped servers. Check availability with `codex mcp list` or
   `claude mcp list`.

## Safety boundary

- Give these servers only the named source API keys. Do not give them warehouse
  database credentials, cloud credentials, or write-capable tokens.
- Community FEC and OpenStates MCP output is a dated API response, not source
  evidence. Use it to guide or validate a Connector; retain original government
  bytes through OpenDiscourse before publishing facts.
- Re-audit and deliberately update each `vendor/mcp/` clone before changing a
  pinned revision.
- Never point an MCP helper at the warehouse, and never start the Census MCP's
  companion Postgres. Throwaway databases for tests and the Compose fallback on
  port 5433 are still allowed. Congress and FEC helpers talk to remote APIs only.
