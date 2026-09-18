from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from time import monotonic, sleep

import yaml
from sqlalchemy.dialects.postgresql import insert

from ..config import settings
from ..db import session
from ..models.core import measurement_table
from .base import IngestionRun, client, json_response

# providers/fred.py already paces its own (metadata-only) requests at this
# rate; ingest_manifest's back-to-back series fetches never had the same
# pacing, and a batch run once saw a transiently-failing series (HTTP 400)
# that succeeded fine when retried in isolation moments later.
PACE_SECONDS = 1.0

# Batch commits rather than one per row: a large daily series (e.g. the Fed
# funds rate since 1954) is ~26,000 observations, and a commit-per-row round
# trip made that take minutes. The whole series already arrives in one API
# response, so there is no resumability benefit to committing more often
# than this -- a failure mid-series is re-run from scratch either way
# (idempotent via ON CONFLICT), matching the batch size already used by the
# Census bulk loaders (acs_load.py, cbp_load.py).
_COMMIT_BATCH = 2000


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
        table = measurement_table()
        observations = payload["observations"]
        for start in range(0, len(observations), _COMMIT_BATCH):
            with session() as active_session:
                for observation in observations[start : start + _COMMIT_BATCH]:
                    value = None if observation["value"] == "." else float(observation["value"])
                    statement = insert(table).values(
                        dataset_id="fred.series",
                        field_id=series_id,
                        period_start=observation["date"],
                        vintage_date=observation["realtime_start"],
                        value_numeric=value,
                        unit="source-defined",
                        flags={"source": "FRED"},
                        source_payload_id=payload_id,
                    )
                    active_session.execute(
                        statement.on_conflict_do_update(
                            index_elements=(
                                table.c.dataset_id,
                                table.c.field_id,
                                table.c.geography_id,
                                table.c.period_start,
                                table.c.period_end,
                                table.c.vintage_date,
                            ),
                            set_={
                                "value_numeric": statement.excluded.value_numeric,
                                "flags": statement.excluded.flags,
                                "source_payload_id": statement.excluded.source_payload_id,
                            },
                        )
                    )
                    run.record_count += 1
        return run.record_count


def ingest_manifest(
    category: str | None = None,
    priority: int | None = None,
    report: Callable[[str], None] | None = None,
) -> tuple[dict[str, int], dict[str, str]]:
    """Backfill the version-controlled FRED core manifest, one traceable run per series.

    A failure on one series is recorded and skipped rather than aborting the
    remaining curated backfill; returns (successes, failures).
    """
    path = Path(__file__).resolve().parents[3] / "inventory" / "core_fred_series.yaml"
    series = yaml.safe_load(path.read_text())["series"]
    selected = [
        entry
        for entry in series
        if (category is None or entry["category"] == category)
        and (priority is None or entry["priority"] <= priority)
    ]
    successes: dict[str, int] = {}
    failures: dict[str, str] = {}
    last_request = 0.0
    for entry in selected:
        series_id = entry["series_id"]
        wait = PACE_SECONDS - (monotonic() - last_request)
        if wait > 0:
            sleep(wait)
        try:
            successes[series_id] = ingest_series(series_id)
        except Exception as exc:  # noqa: BLE001 -- one bad series must not abort the batch
            failures[series_id] = str(exc)
            if report:
                report(f"{series_id}: failed ({exc})")
            last_request = monotonic()
            continue
        last_request = monotonic()
        if report:
            report(f"{series_id}: {successes[series_id]} observations")
    return successes, failures
