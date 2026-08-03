"""Census Data API catalog provider adapter."""
from __future__ import annotations

from hashlib import sha256
import json
from typing import Any

from psycopg.types.json import Jsonb

from ..db import connect
from ..ingestion.base import IngestionRun, client, json_response


CATALOG_URL = "https://api.census.gov/data.json"
ACS_TABLE_BASED_YEARS = (2021, 2022, 2023, 2024)
CBP_2023_URL = "https://www.census.gov/data/datasets/2023/econ/cbp/2023-cbp.html"


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
    description = " ".join(str(item.get(key) or "") for key in ("identifier", "title", "description")).casefold()
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
    with client() as http, IngestionRun("census.api_catalog", {"action": "catalog"}, mode="plan") as run:
        response = http.get(CATALOG_URL)
        payload = json_response(response)
        payload_id = run.store_payload(response, payload)
        offerings = payload.get("dataset", [])
        if not isinstance(offerings, list):
            raise ValueError("Census data catalog did not contain a dataset list")
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        with run.conn.cursor() as cur:
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
                    "identifier": item.get("identifier"), "endpoint": endpoint,
                    "dataset_path": item.get("c_dataset"), "available": item.get("c_isAvailable"),
                    "aggregate": item.get("c_isAggregate"), "cube": item.get("c_isCube"),
                    "temporal": item.get("temporal"), "keywords": item.get("keyword", []),
                    "variables_url": item.get("c_variablesLink"), "groups_url": item.get("c_groupsLink"),
                    "geography_url": item.get("c_geographyLink"), "source_payload_id": payload_id,
                }
                cur.execute(
                    """INSERT INTO catalog.resource
                       (dataset_id, resource_key, resource_type, title, summary, release_year, metadata)
                       VALUES ('census.api_catalog', %s, %s, %s, %s, %s, %s)
                       ON CONFLICT (dataset_id, resource_key) DO UPDATE SET
                         resource_type = EXCLUDED.resource_type, title = EXCLUDED.title,
                         summary = EXCLUDED.summary, release_year = EXCLUDED.release_year,
                         metadata = EXCLUDED.metadata, updated_at = now()""",
                    (key, _offering_type(item), str(item.get("title") or key), item.get("description"), release_year, Jsonb(metadata)),
                )
                run.record_count += 1
            cur.execute(
                """INSERT INTO catalog.snapshot (dataset_id, source_url, checksum_sha256, metadata)
                   VALUES ('census.api_catalog', %s, %s, %s)
                   ON CONFLICT (dataset_id, checksum_sha256) DO UPDATE SET metadata = EXCLUDED.metadata
                   RETURNING snapshot_id""",
                (CATALOG_URL, sha256(canonical).hexdigest(), Jsonb({"kind": "census_data_api_catalog", "offerings": run.record_count})),
            )
            snapshot_id = cur.fetchone()["snapshot_id"]
            cur.execute(
                """INSERT INTO catalog.snapshot_resource (snapshot_id, resource_id)
                   SELECT %s, resource_id FROM catalog.resource WHERE dataset_id = 'census.api_catalog'
                   ON CONFLICT DO NOTHING""",
                (snapshot_id,),
            )
        run.conn.commit()
    return {"resources": run.record_count, "payload_id": payload_id}


def sync_acs_bulk_packages() -> int:
    """Publish one clear, complete ACS Summary File download per modern release."""
    with connect() as conn, conn.cursor() as cur:
        for year in ACS_TABLE_BASED_YEARS:
            base = f"https://www2.census.gov/programs-surveys/acs/summary_file/{year}/table-based-SF"
            cur.execute(
                """INSERT INTO catalog.resource
                   (dataset_id, resource_key, resource_type, title, summary, release_year, metadata)
                   VALUES ('census.acs_5_bulk', %s, 'Full Detailed Tables', %s, %s, %s, %s)
                   ON CONFLICT (dataset_id, resource_key) DO UPDATE SET
                     resource_type = EXCLUDED.resource_type, title = EXCLUDED.title,
                     summary = EXCLUDED.summary, release_year = EXCLUDED.release_year,
                     metadata = EXCLUDED.metadata, updated_at = now()""",
                (
                    f"full:{year}", f"{year} ACS 5-Year — full Detailed Tables summary file",
                    "One official bulk package containing every Detailed Table, estimates, margins of error, and published geography for this ACS 5-year release.",
                    year, Jsonb({"package": "full_summary_file", "url": f"{base}/data/5YRData/5YRData.zip", "geography_url": f"{base}/documentation/Geos{year}5YR.txt", "table_shells_url": f"{base}/documentation/ACS{year}5YR_Table_Shells.txt"}),
                ),
            )
        conn.commit()
    return len(ACS_TABLE_BASED_YEARS)


def sync_cbp_bulk_packages() -> int:
    """Publish the official complete CBP annual bundle as one browser choice."""
    with connect() as conn, conn.cursor() as cur:
        cur.execute("""INSERT INTO catalog.resource
            (dataset_id, resource_key, resource_type, title, summary, release_year, metadata)
            VALUES ('census.business_patterns', 'full:2023', 'Complete CSV bundle', %s, %s, 2023, %s)
            ON CONFLICT (dataset_id, resource_key) DO UPDATE SET resource_type = EXCLUDED.resource_type,
              title = EXCLUDED.title, summary = EXCLUDED.summary, release_year = EXCLUDED.release_year,
              metadata = EXCLUDED.metadata, updated_at = now()""",
            ("2023 County Business Patterns — complete CSV bundle", "Official U.S., state, county, metro, ZIP, and congressional-district CBP files for one annual release.", Jsonb({"package": "complete_csv_bundle", "source_page": CBP_2023_URL})))
        conn.commit()
    return 1
