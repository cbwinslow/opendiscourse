# OpenDiscourse MCP servers

MCP servers assist an AI agent with source discovery, schema inspection, spot
checks, and troubleshooting. They never replace the checked-in Connector
commands that download, retain, checksum, and ingest the warehouse data.

Both Codex (`.codex/config.toml`) and Claude Code (`.mcp.json`) load this
project-scoped configuration. The files contain environment-variable names,
never secrets. Set the required key in the shell or secret manager before
starting either client; a missing key means that server will not start.

| Server | Use | Required environment variable | Pinned local source |
|---|---|---|---|
| `opendiscourse-congress` | Congress.gov and GovInfo exploration, including bill text and committees | `CONGRESS_API_KEY` | PyPI package `congressmcp`; audited source `vendor/mcp/congress` at `838687d2037421ad79b0cb31dd90cf3bf5136533` |
| `opendiscourse-fec` | OpenFEC discovery and validation only | `FEC_API_KEY` | npm package `fec-mcp-server`; audited source `vendor/mcp/fec` at `79f9ffd8a1619531a0b4777c37c963b623a7d482` |
| `opendiscourse-openstates` | OpenStates API discovery and FDW/connector spot checks | `OPENSTATES_API_KEY` | `vendor/mcp/openstates` at `77afca6d5999544d28380c4e930c41d51704b222` |
| `opendiscourse-census` | Census dataset and variable discovery, geography checks, and spot checks | `CENSUS_API_KEY` | `vendor/mcp/census` at `5dcaa637871b9ded5dab415118f9008c06d13f2a` |

## First use

1. Obtain the four source API keys and store them in the operator's secret
   manager or shell profile, never a tracked file.
2. Run `uv sync` in `vendor/mcp/openstates` once. Congress and FEC start from
   their package registries through `uvx` and `npx`.
3. For Census, run its first-time database seed from `vendor/mcp/census`:
   `docker compose --profile prod run --rm census-mcp-db-init sh -c "npm run migrate:up && npm run seed"`.
   Its MCP startup script then starts the local containers as needed.
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
