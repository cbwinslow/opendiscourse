"""Single public metadata-refresh registry for catalog providers."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from collections.abc import Callable

from .browser import ensure_acs, preview_fred_full, sync_fred, sync_fred_full
from .providers.census import sync_acs_bulk_packages, sync_catalog as sync_census_catalog
from .providers.fred import index_batch as index_fred_batch
from .providers.congress import sync as sync_congress
from .repositories.catalog import discovery
from .db import connect


ACS_YEARS = (2022, 2023, 2024)


def sync(refresh: bool = False, sources: set[str] | None = None, full: bool = False, preview: bool = False, index_pages: int | None = None, index_seconds: int | None = None, report: Callable[[str], None] | None = None) -> dict[str, Any]:
    """Synchronize implemented metadata adapters; never acquire bulk data."""
    results: dict[str, Any] = {}
    requested = sources or {"acs", "census", "fred", "congress"}
    if "census" in requested:
        with connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT 1 FROM catalog.snapshot WHERE dataset_id = 'census.api_catalog' LIMIT 1")
            census_ready = cur.fetchone() is not None
        catalog_result = sync_census_catalog() if refresh or not census_ready else {"state": "current"}
        results["census"] = {**catalog_result, "acs_bulk_packages": sync_acs_bulk_packages()}
    if "acs" in requested:
        with connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT DISTINCT (metadata->>'year')::integer AS year FROM catalog.snapshot WHERE dataset_id = 'census.acs_5'")
            existing = {row["year"] for row in cur.fetchall() if row["year"] is not None}
        years = ACS_YEARS if refresh else tuple(year for year in ACS_YEARS if year not in existing)
        for year in years:
            results[f"acs:{year}"] = {"resources": ensure_acs(year), "state": "synced"}
        if not years:
            results["acs"] = {"state": "current", "years": list(ACS_YEARS)}
    if "fred" in requested:
        if index_pages is not None or index_seconds is not None:
            results["fred"] = index_fred_batch(index_pages, index_seconds, report)
            return {"at": datetime.now(timezone.utc).isoformat(), "results": results}
        if full:
            results["fred"] = preview_fred_full() if preview else sync_fred_full()
        else:
            with connect() as conn, conn.cursor() as cur:
                cur.execute("SELECT 1 FROM catalog.snapshot WHERE dataset_id = 'fred.series' LIMIT 1")
                fred_ready = cur.fetchone() is not None
            results["fred"] = sync_fred(refresh) if refresh or not fred_ready else {"state": "current"}
    if "congress" in requested:
        results["congress"] = sync_congress()
    return {"at": datetime.now(timezone.utc).isoformat(), "results": results}


def status() -> list[dict[str, Any]]:
    """Report what the browser can actually navigate today."""
    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT p.provider_id, p.name, d.dataset_id, d.title,
                      count(DISTINCT r.resource_id) AS resources,
                      max(s.captured_at) AS last_snapshot
               FROM catalog.provider p JOIN catalog.dataset d ON d.provider_id = p.provider_id
               LEFT JOIN catalog.resource r ON r.dataset_id = d.dataset_id
               LEFT JOIN catalog.snapshot s ON s.dataset_id = d.dataset_id
               GROUP BY p.provider_id, p.name, d.dataset_id, d.title
               ORDER BY p.name, d.title"""
        )
        rows = cur.fetchall()
    for row in rows:
        if row["resources"]:
            row["state"] = "ready"
        else:
            row["state"] = "pending_adapter"
        if row["dataset_id"] == "fred.series":
            row["discovery"] = discovery("fredmeta")
    return rows
