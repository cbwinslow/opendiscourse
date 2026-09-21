# Upstream checkouts

OpenDiscourse wraps maintained projects instead of rewriting them. This
directory holds local clones used by ingestion adapters.

Refresh with:

```bash
scripts/bootstrap_upstream.sh
```

| Directory | Upstream | Role |
|---|---|---|
| `unitedstates-congress` | https://github.com/unitedstates/congress | House/Senate vote and bill scrapers GovTrack runs on |
| `congress-legislators` | https://github.com/unitedstates/congress-legislators | BioGuide-keyed legislator identity YAML |
| `mcp/congress` | https://github.com/amurshak/congressMCP (`838687d`) | Congress.gov / GovInfo MCP helper |
| `mcp/fec` | https://github.com/sh-patterson/fec-mcp-server (`79f9ffd`) | OpenFEC MCP helper |
| `mcp/census` | https://github.com/uscensusbureau/us-census-bureau-data-api-mcp (`5dcaa63`) | Census MCP helper |
| `mcp/openstates` | https://github.com/Travis-Prall/openstates-mcp (`77afca6`) | OpenStates MCP helper (currently fails to start) |

Clones are gitignored. Do not copy their parsers into `src/` — call or adapt
them behind our provenance boundary.
