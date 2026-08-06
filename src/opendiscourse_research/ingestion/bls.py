"""BLS API v2 time-series ingestion, targeting fact.measurement like FRED."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, date, datetime
from pathlib import Path

import yaml

from ..config import settings
from .base import IngestionRun, client, json_response

BLS_URL = "https://api.bls.gov/publicAPI/v2/timeseries/data/"
# Monthly periods only (M01-M12); M13 ("annual average") and any
# quarterly/annual period codes are skipped so this stays one clean grain
# rather than mixing monthly and annualized observations for the same field.
_MONTH_PERIODS = {f"M{month:02d}": month for month in range(1, 13)}


def ingest_series(
    dataset_id: str,
    series_id: str,
    start_year: int | None = None,
    end_year: int | None = None,
) -> int:
    """Ingest one BLS series into fact.measurement under the given dataset_id."""
    end_year = end_year or datetime.now(UTC).date().year
    start_year = start_year or end_year - 19
    payload_request = {
        "seriesid": [series_id],
        "startyear": str(start_year),
        "endyear": str(end_year),
    }
    if settings.bls_api_key:
        payload_request["registrationkey"] = settings.bls_api_key
    parameters = {
        "dataset_id": dataset_id,
        "series_id": series_id,
        "start_year": start_year,
        "end_year": end_year,
    }
    with client() as http, IngestionRun(dataset_id, parameters) as run:
        response = http.post(BLS_URL, json=payload_request)
        payload = json_response(response)
        if payload.get("status") != "REQUEST_SUCCEEDED":
            raise ValueError(
                f"BLS request for {series_id} did not succeed: {payload.get('message')}"
            )
        payload_id = run.store_payload(response, payload)
        series_list = payload.get("Results", {}).get("series", [])
        if not series_list:
            return run.record_count
        for observation in series_list[0].get("data", []):
            month = _MONTH_PERIODS.get(observation["period"])
            if month is None:
                continue
            period_start = date(int(observation["year"]), month, 1)
            raw_value = observation["value"]
            value = None if raw_value in ("", ".") else float(raw_value)
            with run.conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO fact.measurement (dataset_id, field_id, period_start, value_numeric, unit, flags, source_payload_id)
                       VALUES (%s, %s, %s, %s, 'source-defined', %s, %s)
                       ON CONFLICT (dataset_id, field_id, geography_id, period_start, period_end, vintage_date)
                       DO UPDATE SET value_numeric = EXCLUDED.value_numeric, flags = EXCLUDED.flags, source_payload_id = EXCLUDED.source_payload_id""",
                    (
                        dataset_id,
                        series_id,
                        period_start,
                        value,
                        '{"source":"BLS"}',
                        payload_id,
                    ),
                )
                run.record_count += 1
            run.conn.commit()
        return run.record_count


def ingest_manifest(
    category: str | None = None,
    priority: int | None = None,
    report: Callable[[str], None] | None = None,
) -> tuple[dict[str, int], dict[str, str]]:
    """Backfill the version-controlled BLS core manifest, one traceable run per series.

    A failure on one series is recorded and skipped rather than aborting the
    remaining curated backfill; returns (successes, failures).
    """
    path = Path(__file__).resolve().parents[3] / "inventory" / "core_bls_series.yaml"
    series = yaml.safe_load(path.read_text())["series"]
    selected = [
        entry
        for entry in series
        if (category is None or entry["category"] == category)
        and (priority is None or entry["priority"] <= priority)
    ]
    successes: dict[str, int] = {}
    failures: dict[str, str] = {}
    for entry in selected:
        series_id = entry["series_id"]
        try:
            successes[series_id] = ingest_series(entry["dataset"], series_id)
        except Exception as exc:  # noqa: BLE001 -- one bad series must not abort the batch
            failures[series_id] = str(exc)
            if report:
                report(f"{series_id}: failed ({exc})")
            continue
        if report:
            report(f"{series_id}: {successes[series_id]} observations")
    return successes, failures
