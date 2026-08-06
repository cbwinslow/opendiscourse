from __future__ import annotations

from pathlib import Path

import yaml

from ..config import settings
from .base import IngestionRun, client, json_response


def ingest_series(series_id: str) -> int:
    if not settings.fred_api_key:
        raise ValueError("FRED_API_KEY is required for FRED ingestion")
    params = {
        "series_id": series_id,
        "api_key": settings.fred_api_key,
        "file_type": "json",
    }
    with client() as http, IngestionRun("fred.series", {"series_id": series_id}) as run:
        response = http.get(
            "https://api.stlouisfed.org/fred/series/observations", params=params
        )
        payload = json_response(response)
        payload_id = run.store_payload(response, payload)
        for observation in payload["observations"]:
            value = None if observation["value"] == "." else float(observation["value"])
            with run.conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO fact.measurement (dataset_id, field_id, period_start, vintage_date, value_numeric, unit, flags, source_payload_id)
                       VALUES ('fred.series', %s, %s, %s, %s, 'source-defined', %s, %s)
                       ON CONFLICT (dataset_id, field_id, geography_id, period_start, period_end, vintage_date)
                       DO UPDATE SET value_numeric = EXCLUDED.value_numeric, flags = EXCLUDED.flags, source_payload_id = EXCLUDED.source_payload_id""",
                    (
                        series_id,
                        observation["date"],
                        observation["realtime_start"],
                        value,
                        '{"source":"FRED"}',
                        payload_id,
                    ),
                )
                run.record_count += 1
            run.conn.commit()
        return run.record_count


def ingest_manifest(
    category: str | None = None, priority: int | None = None
) -> dict[str, int]:
    """Backfill the version-controlled FRED core manifest, one traceable run per series."""
    path = Path(__file__).resolve().parents[3] / "inventory" / "core_fred_series.yaml"
    series = yaml.safe_load(path.read_text())["series"]
    selected = [
        entry
        for entry in series
        if (category is None or entry["category"] == category)
        and (priority is None or entry["priority"] <= priority)
    ]
    return {entry["series_id"]: ingest_series(entry["series_id"]) for entry in selected}
