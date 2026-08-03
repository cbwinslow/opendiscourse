"""FRED discovery adapter: paced, on-demand metadata search with local cache."""
from __future__ import annotations

from time import monotonic, sleep
from datetime import datetime, timezone
from typing import Any
from collections.abc import Callable

from ..config import settings
from ..ingestion.base import client, json_response
from ..repositories.catalog import cache_fred_records, cache_fred_search, claim_discovery, save_discovery


PACE_SECONDS = 1.0
_last_request = 0.0


def _get(endpoint: str, **params: Any) -> dict[str, Any]:
    """Make one paced FRED v1 metadata request without exposing credentials."""
    global _last_request
    if not settings.fred_api_key:
        raise ValueError("FRED_API_KEY is required for live FRED discovery")
    wait = PACE_SECONDS - (monotonic() - _last_request)
    if wait > 0:
        sleep(wait)
    with client() as http:
        response = http.get(
            f"https://api.stlouisfed.org/fred/{endpoint}",
            params={**params, "api_key": settings.fred_api_key, "file_type": "json"},
        )
    _last_request = monotonic()
    return json_response(response)


def search(text: str, limit: int = 100) -> int:
    """Search official FRED metadata and cache only the displayed result page."""
    query = text.strip()
    if len(query) < 2:
        raise ValueError("Enter at least two characters before searching FRED")
    return cache_fred_search(_get("series/search", search_text=query, limit=min(limit, 1000)).get("seriess", []), query)


def index_batch(pages: int | None = 1, duration_seconds: int | None = None, report: Callable[[str], None] | None = None) -> dict[str, Any]:
    """Index paced FRED pages until the requested count or time budget is reached."""
    if pages is not None and (pages < 1 or pages > 20):
        raise ValueError("pages must be between 1 and 20")
    if duration_seconds is not None and duration_seconds < 1:
        raise ValueError("duration_seconds must be positive")
    if (pages is None) == (duration_seconds is None):
        raise ValueError("provide exactly one of pages or duration_seconds")
    job_id = "fredmeta"
    prior = claim_discovery(job_id, "fred.series")
    if prior is None:
        raise ValueError("FRED metadata indexing is already running; wait for it to finish or retry after 15 minutes")
    cursor = dict(prior.get("cursor") or {"release_offset": 0, "series_offset": 0})
    stats = dict(prior.get("statistics") or {"pages": 0, "series": 0, "releases": 0})
    now = datetime.now(timezone.utc)
    save_discovery(job_id, "fred.series", "running", cursor, stats, started_at=now)
    started = monotonic()
    completed = 0
    while pages is None or completed < pages:
        if duration_seconds is not None and completed and monotonic() - started >= duration_seconds:
            break
        release_offset = int(cursor.get("release_offset", 0))
        release_id = cursor.get("release_id")
        if release_id is None:
            releases = _get("releases", limit=1, offset=release_offset).get("releases", [])
            if not releases:
                save_discovery(job_id, "fred.series", "complete", cursor, stats, finished_at=datetime.now(timezone.utc))
                return {"state": "complete", "cursor": cursor, "statistics": stats}
            release_id = int(releases[0]["id"])
            cursor.update({"release_id": release_id, "series_offset": 0})
        offset = int(cursor["series_offset"])
        payload = _get("release/series", release_id=release_id, limit=1000, offset=offset)
        records = payload.get("seriess", [])
        cached = cache_fred_records(records, {"method": "release", "release_id": release_id})
        stats["pages"] = int(stats["pages"]) + 1
        completed += 1
        stats["series"] = int(stats["series"]) + cached
        next_offset = offset + len(records)
        if not records or next_offset >= int(payload.get("count", 0)):
            stats["releases"] = int(stats["releases"]) + 1
            cursor = {"release_offset": release_offset + 1, "series_offset": 0}
        else:
            cursor.update({"series_offset": next_offset})
        save_discovery(job_id, "fred.series", "running", cursor, stats)
        if report:
            report(f"FRED release {release_id}: {stats['series']} metadata rows cached")
    save_discovery(job_id, "fred.series", "paused", cursor, stats)
    return {"state": "paused", "cursor": cursor, "statistics": stats, "run_pages": completed,
            "elapsed_seconds": round(monotonic() - started, 1)}
