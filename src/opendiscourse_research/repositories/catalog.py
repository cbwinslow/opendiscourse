"""Catalog persistence repository; all reusable statements are external SQL."""
from __future__ import annotations

from pathlib import Path
from typing import Any
from datetime import datetime

from psycopg.types.json import Jsonb

from ..db import connect


ROOT = Path(__file__).resolve().parents[3]


def _query(name: str) -> str:
    """Read a named, version-controlled catalog query template."""
    return (ROOT / "sql" / "query" / "catalog" / f"{name}.sql").read_text()


def cache_fred_records(records: list[dict[str, Any]], discovery: dict[str, Any]) -> int:
    """Upsert FRED metadata records without acquiring observations."""
    with connect() as conn, conn.cursor() as cur:
        for record in records:
            metadata = {
                key: record.get(key) for key in (
                    "observation_start", "observation_end", "frequency",
                    "frequency_short", "units", "units_short",
                    "seasonal_adjustment", "seasonal_adjustment_short",
                    "last_updated", "popularity",
                )
            }
            metadata.update({"series_id": record["id"], "discovery": discovery})
            cur.execute(_query("upsert_fred_search"), {
                "key": record["id"], "title": record.get("title", record["id"]),
                "summary": record.get("notes"), "metadata": Jsonb(metadata),
            })
        conn.commit()
    return len(records)


def cache_fred_search(records: list[dict[str, Any]], query: str) -> int:
    """Cache one official FRED search result page."""
    return cache_fred_records(records, {"method": "search", "query": query})


def upsert_resource(
    dataset_id: str, resource_key: str, resource_type: str, title: str,
    summary: str, release_year: int | None, metadata: dict[str, Any],
) -> None:
    """Persist one provider-catalog resource using its external SQL statement."""
    with connect() as conn, conn.cursor() as cur:
        cur.execute(_query("upsert_resource"), {
            "dataset_id": dataset_id,
            "resource_key": resource_key,
            "resource_type": resource_type,
            "title": title,
            "summary": summary,
            "release_year": release_year,
            "metadata": Jsonb(metadata),
        })
        conn.commit()


def delete_resources_prefix(dataset_id: str, prefix: str) -> None:
    """Remove obsolete derived catalog rows; source artifacts are never affected."""
    with connect() as conn, conn.cursor() as cur:
        cur.execute(_query("delete_resources_prefix"), {"dataset_id": dataset_id, "prefix": prefix})
        conn.commit()


def resource_ids(dataset: str, year: int | None = None, product: str | None = None) -> list[str]:
    """Return every resource ID in one catalog group for selection expansion."""
    with connect() as conn, conn.cursor() as cur:
        cur.execute(_query("resource_ids"), {"dataset": dataset, "year": year, "product": product})
        return [str(row["resource_id"]) for row in cur.fetchall()]


def discovery(discovery_id: str) -> dict[str, Any] | None:
    """Load durable state for one bounded metadata-discovery workflow."""
    with connect() as conn, conn.cursor() as cur:
        cur.execute(_query("get_discovery"), {"discovery_id": discovery_id})
        return cur.fetchone()


def claim_discovery(discovery_id: str, dataset_id: str) -> dict[str, Any] | None:
    """Claim one discovery job, refusing a second active worker for 15 minutes."""
    with connect() as conn, conn.cursor() as cur:
        cur.execute(_query("claim_discovery"), {"discovery_id": discovery_id, "dataset_id": dataset_id})
        claimed = cur.fetchone()
        conn.commit()
        return claimed


def save_discovery(
    discovery_id: str, dataset_id: str, state: str, cursor: dict[str, Any],
    statistics: dict[str, Any], error_message: str | None = None,
    started_at: datetime | None = None, finished_at: datetime | None = None,
) -> None:
    """Persist a safe resume cursor after each committed discovery batch."""
    with connect() as conn, conn.cursor() as cur:
        cur.execute(_query("upsert_discovery"), {
            "discovery_id": discovery_id, "dataset_id": dataset_id, "state": state,
            "cursor": Jsonb(cursor), "statistics": Jsonb(statistics),
            "error_message": error_message, "started_at": started_at, "finished_at": finished_at,
        })
        conn.commit()
