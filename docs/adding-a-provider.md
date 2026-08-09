# Adding a Provider

A provider is a plain Python module under
`src/opendiscourse_research/providers/` that talks to one external data
source. Providers intentionally do **not** share a common base class or
function signature — FRED, Census, and Congress each expose different
shapes (paced search plus resumable indexing; multi-dataset bulk-package
sync; one-shot sync) because their upstream APIs are genuinely different.
See `AGENTS.md`: "keep provider-specific behavior explicit at the adapter
boundary."

Run `research-db new-provider <name>` first — it creates:

- `src/opendiscourse_research/providers/<name>.py`
- `tests/test_<name>_provider.py`
- a commented starter block in `inventory/sources.yaml`

Then fill in each of the required behaviors below.

## Required behaviors

1. **Record provenance through the repository layer, not inline SQL.** Call
   the existing functions in `src/opendiscourse_research/repositories/`
   (e.g. `catalog.py`) to persist results. *FRED example:*
   `providers/fred.py`'s `search()` and `index_batch()` call
   `repositories/catalog.py`'s `cache_fred_search()` and
   `cache_fred_records()` rather than touching the database directly.

2. **Respect the provider's pacing/rate limits**, if it has any. *FRED
   example:* `providers/fred.py` tracks `_last_request` with `monotonic()`
   and sleeps to enforce `PACE_SECONDS = 1.0` before every request.

3. **Raise a clear `ValueError` on missing required config**, instead of
   letting a request fail opaquely. *FRED example:* `providers/fred.py`'s
   `_get()` raises `ValueError("FRED_API_KEY is required for live FRED
   discovery")` up front when `settings.fred_api_key` is unset.

4. **Never contact a live provider from `init-db`.** `init-db` (`cli.py`'s
   `init_db()`) only applies migrations and syncs the version-controlled
   catalog in `inventory/sources.yaml` — it must stay that way. Discovery
   and sync are separate, explicit CLI commands.

5. **Use the shared HTTP client and response guard.** Call
   `ingestion.base.client()` for the `httpx.Client` (it sets a timeout and
   `User-Agent`) and wrap responses in `ingestion.base.json_response()`,
   which rejects non-JSON/error responses without leaking API keys into
   error messages. *FRED example:* `providers/fred.py`'s `_get()` does
   exactly this.

## Worked example: FRED end to end

- `src/opendiscourse_research/providers/fred.py` — `search()` runs one
  paced metadata search; `index_batch()` resumes a cursor-based crawl of
  every FRED release/series, checkpointing progress via
  `repositories/catalog.py`'s `claim_discovery()`/`save_discovery()` so a
  stopped run resumes instead of restarting.
- `src/opendiscourse_research/repositories/catalog.py` — owns the actual
  `INSERT`s (`cache_fred_records()`, `cache_fred_search()`); the provider
  module never writes SQL itself.
- `inventory/sources.yaml` — the `fred` provider block declares the
  `fred.series` dataset (grain, identifiers, cadence, priority) that
  `research-db status`/`browse` read.
- Register a new dataset in `inventory/sources.yaml` before writing any
  code for it, then see `docs/framework.md` for the full
  register → contract → discovery → staging → canonical-transform sequence
  this project follows once a provider goes beyond metadata discovery.

Note: FRED does not yet have a dedicated `tests/test_fred*.py` file. For a
worked example of this project's actual test style (real
`unittest.TestCase` classes, `unittest.mock.patch`, temp directories, no
live network calls), read `tests/test_census_bulk.py` or
`tests/test_openstates_refresh.py` instead.
