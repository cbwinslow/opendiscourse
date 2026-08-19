"""Census Data API catalog provider adapter."""

from __future__ import annotations

import json
from hashlib import sha256
from typing import Any

from sqlalchemy import func, literal, select
from sqlalchemy.dialects.postgresql import insert

from ..db import session
from ..ingestion.base import IngestionRun, client, json_response
from ..models.catalog import CatalogSnapshot, Resource, SnapshotResource
from ..repositories.catalog import upsert_resource

CATALOG_URL = "https://api.census.gov/data.json"
ACS_TABLE_BASED_YEARS = (2021, 2022, 2023, 2024)
# Verified directly against the real Census directory listings.
CBP_YEARS = tuple(range(2009, 2024))
TIGER_YEARS = tuple(range(2016, 2026))
DHC_2020_URL = "https://www2.census.gov/programs-surveys/decennial/2020/data/demographic-and-housing-characteristics-file/National/us2020.dhc.zip"


def _offering_key(item: dict[str, Any]) -> str:
    """Return the stable Census identifier used as a catalog resource key."""
    return str(item.get("identifier") or item.get("@id") or item.get("title"))


def _endpoint(item: dict[str, Any]) -> str | None:
    """Extract the first JSON API distribution endpoint when it is published."""
    for distribution in item.get("distribution", []):
        if distribution.get("format") == "API" and distribution.get("accessURL"):
            return str(distribution["accessURL"])
    return None


def _offering_type(item: dict[str, Any]) -> str:
    """Classify an offering into a browser facet from its official API path."""
    path = "/".join(str(part).casefold() for part in item.get("c_dataset", []))
    description = " ".join(
        str(item.get(key) or "") for key in ("identifier", "title", "description")
    ).casefold()
    if path.startswith("acs5") or "/acs5" in path:
        return "ACS 5-Year"
    if path.startswith("acs1") or "/acs1" in path:
        return "ACS 1-Year"
    if path.startswith("acs"):
        return "ACS supplemental and special products"
    if path.startswith("dec") or "decennial" in description:
        return "Decennial Census"
    if path.startswith("pep") or "population estimates" in description:
        return "Population Estimates"
    if path.startswith("tiger") or "tiger/line" in description:
        return "TIGER geography"
    return "Census API offering"


def sync_catalog() -> dict[str, int | str]:
    """Index every published Census API offering without fetching observations."""
    with (
        client() as http,
        IngestionRun("census.api_catalog", {"action": "catalog"}, mode="plan") as run,
    ):
        response = http.get(CATALOG_URL)
        payload = json_response(response)
        payload_id = run.store_payload(response, payload)
        offerings = payload.get("dataset", [])
        if not isinstance(offerings, list):
            raise ValueError("Census data catalog did not contain a dataset list")
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        resource_table = Resource.__table__
        snapshot_table = CatalogSnapshot.__table__
        with session() as active_session:
            for item in offerings:
                if not isinstance(item, dict):
                    continue
                key = _offering_key(item)
                endpoint = _endpoint(item)
                vintage = item.get("c_vintage")
                try:
                    release_year = int(vintage) if vintage is not None else None
                except (TypeError, ValueError):
                    release_year = None
                metadata = {
                    "identifier": item.get("identifier"),
                    "endpoint": endpoint,
                    "dataset_path": item.get("c_dataset"),
                    "available": item.get("c_isAvailable"),
                    "aggregate": item.get("c_isAggregate"),
                    "cube": item.get("c_isCube"),
                    "temporal": item.get("temporal"),
                    "keywords": item.get("keyword", []),
                    "variables_url": item.get("c_variablesLink"),
                    "groups_url": item.get("c_groupsLink"),
                    "geography_url": item.get("c_geographyLink"),
                    "source_payload_id": payload_id,
                }
                resource_statement = insert(resource_table).values(
                    dataset_id="census.api_catalog",
                    resource_key=key,
                    resource_type=_offering_type(item),
                    title=str(item.get("title") or key),
                    summary=item.get("description"),
                    release_year=release_year,
                    metadata=metadata,
                )
                excluded = resource_statement.excluded
                active_session.execute(
                    resource_statement.on_conflict_do_update(
                        index_elements=(resource_table.c.dataset_id, resource_table.c.resource_key),
                        set_={
                            "resource_type": excluded.resource_type,
                            "title": excluded.title,
                            "summary": excluded.summary,
                            "release_year": excluded.release_year,
                            "metadata": excluded.metadata,
                            "updated_at": func.now(),
                        },
                    )
                )
                run.record_count += 1
            snapshot_statement = insert(snapshot_table).values(
                dataset_id="census.api_catalog",
                source_url=CATALOG_URL,
                checksum_sha256=sha256(canonical).hexdigest(),
                metadata={"kind": "census_data_api_catalog", "offerings": run.record_count},
            )
            snapshot_id = active_session.execute(
                snapshot_statement.on_conflict_do_update(
                    index_elements=(snapshot_table.c.dataset_id, snapshot_table.c.checksum_sha256),
                    set_={"metadata": snapshot_statement.excluded.metadata},
                ).returning(snapshot_table.c.snapshot_id)
            ).scalar_one()
            active_session.execute(
                insert(SnapshotResource.__table__)
                .from_select(
                    ("snapshot_id", "resource_id"),
                    select(literal(snapshot_id), Resource.resource_id).where(
                        Resource.dataset_id == "census.api_catalog"
                    ),
                )
                .on_conflict_do_nothing()
            )
    return {"resources": run.record_count, "payload_id": payload_id}


def sync_acs_bulk_packages() -> int:
    """Publish one clear, complete ACS Summary File download per modern release."""
    for year in ACS_TABLE_BASED_YEARS:
        base = f"https://www2.census.gov/programs-surveys/acs/summary_file/{year}/table-based-SF"
        upsert_resource(
            "census.acs_5_bulk",
            f"full:{year}",
            "Full Detailed Tables",
            f"{year} ACS 5-Year — full Detailed Tables summary file",
            "One official bulk package containing every Detailed Table, estimates, margins of error, and published geography for this ACS 5-year release.",
            year,
            {
                "package": "full_summary_file",
                "url": f"{base}/data/5YRData/5YRData.zip",
                "geography_url": f"{base}/documentation/Geos{year}5YR.txt",
                "table_shells_url": f"{base}/documentation/ACS{year}5YR_Table_Shells.txt",
            },
        )
    return len(ACS_TABLE_BASED_YEARS)


def sync_cbp_bulk_packages() -> int:
    """Publish one official complete CBP annual bundle per available release year."""
    for year in CBP_YEARS:
        upsert_resource(
            "census.business_patterns",
            f"full:{year}",
            "Complete CSV bundle",
            f"{year} County Business Patterns — complete CSV bundle",
            "Official U.S., state, and county CBP/ZBP files for one annual release.",
            year,
            {
                "package": "complete_csv_bundle",
                "source_page": f"https://www.census.gov/data/datasets/{year}/econ/cbp/{year}-cbp.html",
            },
        )
    return len(CBP_YEARS)


PEP_VINTAGE_SERIES = {
    "2020-2025": 2025,
    "2010-2020": 2020,
}


def sync_pep_bulk_packages() -> int:
    """Publish one complete, no-mixing PEP package per available vintage series.

    The pre-fix resource_key format ("vintage:2025") is left registered but
    orphaned rather than deleted -- it may already be referenced by a saved
    basket selection, and the current parser
    (ingestion/pep_bulk.py::_series) simply won't match it, so selecting it
    fails clearly ("select exactly one PEP vintage") rather than silently
    doing the wrong thing.
    """
    for series, end_year in PEP_VINTAGE_SERIES.items():
        upsert_resource(
            "census.population_estimates",
            f"vintage:{series}",
            "National, state, and county totals",
            f"{series} Population Estimates — national, state, and county totals",
            f"Complete {series} PEP vintage series for national/state/county totals. Never combine it with another vintage.",
            end_year,
            {"package": "national_state_county_totals", "vintage": series},
        )
    return len(PEP_VINTAGE_SERIES)


def sync_dhc_bulk_packages() -> int:
    """Publish the one complete 2020 DHC archive without disguising segments as tables."""
    upsert_resource(
        "census.decennial",
        "dhc:2020:national",
        "Complete DHC national archive",
        "2020 Decennial DHC — complete national archive",
        "Official 2020 Demographic and Housing Characteristics archive. Geographic headers and segmented records remain source-shaped until an explicit LOGRECNO-aware loader is approved.",
        2020,
        {"package": "complete_national_dhc", "url": DHC_2020_URL},
    )
    return 1


def sync_tiger_bulk_packages() -> int:
    """Publish a small, complete national boundary package per available TIGER vintage."""
    for year in TIGER_YEARS:
        upsert_resource(
            "census.tiger",
            f"national:{year}:core-boundaries",
            "National core boundary layers",
            f"{year} TIGER/Line — national core boundary layers",
            "Official nationwide state, county, CBSA, and ZCTA boundary archives. State-partitioned tract, block-group, and block layers stay separate to keep package sizes and scope clear.",
            year,
            {
                "package": "national_core_boundaries",
                "base_url": f"https://www2.census.gov/geo/tiger/TIGER{year}",
            },
        )
    return len(TIGER_YEARS)
