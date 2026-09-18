"""Single public metadata-refresh registry for catalog providers."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Integer, cast, distinct, func, select

from .browser import ensure_acs, preview_fred_full, sync_bls, sync_fred, sync_fred_full
from .db import session
from .models.catalog import CatalogSnapshot, Dataset, Provider, Resource
from .providers.census import (
    sync_acs_bulk_packages,
    sync_cbp_bulk_packages,
    sync_dhc_bulk_packages,
    sync_pep_bulk_packages,
    sync_tiger_bulk_packages,
)
from .providers.census import sync_catalog as sync_census_catalog
from .providers.congress import sync as sync_congress
from .providers.fred import index_batch as index_fred_batch
from .repositories.catalog import discovery

ACS_YEARS = (2022, 2023, 2024)


def sync(
    refresh: bool = False,
    sources: set[str] | None = None,
    full: bool = False,
    preview: bool = False,
    index_pages: int | None = None,
    index_seconds: int | None = None,
    report: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    """Synchronize implemented metadata adapters; never acquire bulk data."""
    results: dict[str, Any] = {}
    requested = sources or {"acs", "census", "fred", "congress", "bls"}
    if "census" in requested:
        census_ready = _has_snapshot("census.api_catalog")
        catalog_result = (
            sync_census_catalog()
            if refresh or not census_ready
            else {"state": "current"}
        )
        results["census"] = {
            **catalog_result,
            "acs_bulk_packages": sync_acs_bulk_packages(),
            "cbp_bulk_packages": sync_cbp_bulk_packages(),
            "pep_bulk_packages": sync_pep_bulk_packages(),
            "dhc_bulk_packages": sync_dhc_bulk_packages(),
            "tiger_bulk_packages": sync_tiger_bulk_packages(),
        }
    if "acs" in requested:
        with session() as active_session:
            existing = set(
                active_session.scalars(
                    select(
                        distinct(cast(CatalogSnapshot.metadata_["year"].astext, Integer))
                    ).where(CatalogSnapshot.dataset_id == "census.acs_5")
                )
            )
        existing.discard(None)
        years = (
            ACS_YEARS
            if refresh
            else tuple(year for year in ACS_YEARS if year not in existing)
        )
        for year in years:
            results[f"acs:{year}"] = {"resources": ensure_acs(year), "state": "synced"}
        if not years:
            results["acs"] = {"state": "current", "years": list(ACS_YEARS)}
    if "fred" in requested:
        if index_pages is not None or index_seconds is not None:
            results["fred"] = index_fred_batch(index_pages, index_seconds, report)
            return {"at": datetime.now(UTC).isoformat(), "results": results}
        if full:
            results["fred"] = preview_fred_full() if preview else sync_fred_full()
        else:
            fred_ready = _has_snapshot("fred.series")
            results["fred"] = (
                sync_fred(refresh)
                if refresh or not fred_ready
                else {"state": "current"}
            )
    if "congress" in requested:
        results["congress"] = sync_congress()
    if "bls" in requested:
        bls_ready = _has_snapshot("bls.cpi")
        results["bls"] = (
            sync_bls() if refresh or not bls_ready else {"state": "current"}
        )
    return {"at": datetime.now(UTC).isoformat(), "results": results}


def status() -> list[dict[str, Any]]:
    """Report what the browser can actually navigate today."""
    with session() as active_session:
        rows = [
            dict(row)
            for row in active_session.execute(
                select(
                    Provider.provider_id,
                    Provider.name,
                    Dataset.dataset_id,
                    Dataset.title,
                    func.count(distinct(Resource.resource_id)).label("resources"),
                    func.max(CatalogSnapshot.captured_at).label("last_snapshot"),
                )
                .join(Dataset, Dataset.provider_id == Provider.provider_id)
                .outerjoin(Resource, Resource.dataset_id == Dataset.dataset_id)
                .outerjoin(CatalogSnapshot, CatalogSnapshot.dataset_id == Dataset.dataset_id)
                .group_by(Provider.provider_id, Provider.name, Dataset.dataset_id, Dataset.title)
                .order_by(Provider.name, Dataset.title)
            ).mappings()
        ]
    for row in rows:
        if row["resources"]:
            row["state"] = "ready"
        else:
            row["state"] = "pending_adapter"
        if row["dataset_id"] == "fred.series":
            row["discovery"] = discovery("fredmeta")
    return rows


def _has_snapshot(dataset_id: str) -> bool:
    """Return whether a catalog dataset has at least one successful discovery snapshot."""
    with session() as active_session:
        return active_session.scalar(
            select(CatalogSnapshot.snapshot_id)
            .where(CatalogSnapshot.dataset_id == dataset_id)
            .limit(1)
        ) is not None
