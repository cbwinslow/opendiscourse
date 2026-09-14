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

Clones are gitignored. Do not copy their parsers into `src/` — call or adapt
them behind our provenance boundary.
