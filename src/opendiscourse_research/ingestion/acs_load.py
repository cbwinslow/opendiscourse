"""Artifact-linked county/state loading for ACS table-based summary files."""

from __future__ import annotations

import csv
import re
from collections.abc import Callable
from concurrent.futures import ProcessPoolExecutor, as_completed
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from psycopg.types.json import Jsonb
from sqlalchemy import select

from ..db import connect, session
from ..models.catalog import artifact_table

SUMMARY_LEVELS = {"040": "state", "050": "county"}
FIELD_PATTERN = re.compile(r"_(E|M)[0-9]+$")
# Census uses these text and numeric sentinels for unavailable cells.  The
# immutable source row remains in stage.acs_bulk_row, while a SQL NULL keeps
# analysis from treating a suppression marker as an observation.
MISSING_VALUES = {"", "N", ".", "-666666666", "-999999999"}


def _scope(plan: dict[str, Any]) -> set[str]:
    scope = set(plan.get("canonical_load_scope", {}).get("geography_types", []))
    unknown = scope - set(SUMMARY_LEVELS.values())
    if unknown or not scope:
        raise ValueError(
            f"Choose supported ACS geography types {sorted(SUMMARY_LEVELS.values())}; got {sorted(unknown)}"
        )
    return scope


def _artifact(dataset_id: str, key: str) -> dict[str, Any]:
    """Return a downloaded ACS artifact through immutable typed evidence storage."""
    table = artifact_table()
    with session() as active_session:
        row = active_session.execute(
            select(table.c.artifact_id, table.c.local_path).where(
                table.c.dataset_id == dataset_id,
                table.c.artifact_key == key,
                table.c.status.in_(("downloaded", "skipped")),
            )
        ).mappings().first()
    if row is None:
        raise ValueError(f"Required ACS artifact {key!r} has not been downloaded")
    return dict(row)


def _table_artifacts(plan: dict[str, Any]) -> list[dict[str, Any]]:
    artifacts = [
        item
        for item in plan.get("artifacts", [])
        if item.get("kind") == "detailed_table"
    ]
    if not artifacts:
        raise ValueError(
            "ACS canonical loading currently supports selected Detailed Table artifacts, not full release packages"
        )
    return artifacts


def _geo_id(value: str) -> tuple[str, str] | None:
    """Map an ACS GEO_ID to the canonical state/county geoid without a crosswalk."""
    if len(value) < 9 or "US" not in value:
        return None
    level, fips = value[:3], value.split("US", 1)[1]
    geography_type = SUMMARY_LEVELS.get(level)
    if geography_type == "state" and len(fips) == 2:
        return geography_type, fips
    if geography_type == "county" and len(fips) == 5:
        return geography_type, fips
    return None


def _numeric(value: Any) -> Decimal | None:
    """Return a Census numeric cell, mapping documented unavailable markers to NULL."""
    text = "" if value is None else str(value).strip()
    if text in MISSING_VALUES:
        return None
    try:
        return Decimal(text)
    except InvalidOperation as exc:
        raise ValueError(f"Invalid ACS numeric value {value!r}") from exc


def stage_acs_bulk(
    plan: dict[str, Any],
    update: Callable[[str], None] | None = None,
    *,
    table_ids: frozenset[str] | None = None,
) -> int:
    """Stage approved table rows for explicitly selected state/county geographies.

    ``table_ids`` restricts staging to a subset of the plan's Detailed
    Tables -- the partitioning hook `stage_acs_bulk_parallel` uses to run
    several disjoint table subsets as separate worker processes.
    """
    if plan.get("state") != "downloaded":
        raise ValueError("ACS plan must be downloaded before staging")
    dataset_id = str(plan.get("dataset", "census.acs_5_bulk"))
    scope = _scope(plan)
    total = 0
    with connect() as conn:
        for item in _table_artifacts(plan):
            if table_ids is not None and str(item["table_id"]) not in table_ids:
                continue
            artifact = _artifact(dataset_id, str(item["artifact_key"]))
            if update:
                update(f"Staging ACS {item['table_id']}")
            rows = []
            with Path(artifact["local_path"]).open(
                encoding="utf-8-sig", newline=""
            ) as source:
                for ordinal, row in enumerate(
                    csv.DictReader(source, delimiter="|"), start=1
                ):
                    parsed = _geo_id(str(row.get("GEO_ID", "")))
                    if parsed is None or parsed[0] not in scope:
                        continue
                    rows.append(
                        (
                            artifact["artifact_id"],
                            ordinal,
                            int(item["release_year"]),
                            str(item["table_id"]),
                            parsed[0],
                            parsed[1],
                            Jsonb(row),
                        )
                    )
                    if len(rows) == 2_000:
                        with conn.cursor() as cur:
                            cur.executemany(
                                "INSERT INTO stage.acs_bulk_row (artifact_id,source_ordinal,release_year,table_id,geography_type,geoid,raw) VALUES (%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING",
                                rows,
                            )
                        total += len(rows)
                        rows = []
            if rows:
                with conn.cursor() as cur:
                    cur.executemany(
                        "INSERT INTO stage.acs_bulk_row (artifact_id,source_ordinal,release_year,table_id,geography_type,geoid,raw) VALUES (%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING",
                        rows,
                    )
                total += len(rows)
            conn.commit()
    return total


def load_acs_bulk(
    plan: dict[str, Any],
    update: Callable[[str], None] | None = None,
    *,
    table_ids: frozenset[str] | None = None,
) -> int:
    """Promote staged ACS estimates/MOEs to typed artifact-linked facts.

    ``table_ids`` restricts loading to a subset of the plan's Detailed
    Tables -- the partitioning hook `load_acs_bulk_parallel` uses to run
    several disjoint table subsets as separate worker processes.
    """
    if plan.get("state") != "staged":
        raise ValueError("ACS plan must be staged before canonical loading")
    dataset_id = str(plan.get("dataset", "census.acs_5_bulk"))
    scope = list(_scope(plan))
    total = 0
    if update:
        update("Creating ACS geographies")
    with connect() as conn, conn.cursor() as cur:
        artifact_ids = [
            _artifact(dataset_id, str(item["artifact_key"]))["artifact_id"]
            for item in _table_artifacts(plan)
            if table_ids is None or str(item["table_id"]) in table_ids
        ]
        if not artifact_ids:
            return 0
        cur.execute(
            """INSERT INTO core.geography (geography_type,geoid,state_fips,county_fips)
          SELECT DISTINCT geography_type, geoid, substring(geoid from '^([0-9]{2})'), CASE WHEN geography_type='county' THEN substring(geoid from '^[0-9]{2}([0-9]{3})') END
          FROM stage.acs_bulk_row WHERE artifact_id=ANY(%s) AND geography_type=ANY(%s)
          ON CONFLICT (geography_type,geoid) DO NOTHING""",
            (artifact_ids, scope),
        )
        cur.execute("SELECT geography_id,geography_type,geoid FROM core.geography")
        geographies = {
            (row["geography_type"], row["geoid"]): row["geography_id"]
            for row in cur.fetchall()
        }
        cur.execute(
            "SELECT artifact_id,source_ordinal,release_year,table_id,geography_type,geoid,raw FROM stage.acs_bulk_row WHERE artifact_id=ANY(%s) AND geography_type=ANY(%s)",
            (artifact_ids, scope),
        )
        source_rows = cur.fetchall()
        rows = []
        for source in source_rows:
            geography_id = geographies[(source["geography_type"], source["geoid"])]
            for field_id, value in source["raw"].items():
                match = FIELD_PATTERN.search(field_id)
                if field_id == "GEO_ID" or match is None:
                    continue
                measure = "estimate" if match.group(1) == "E" else "margin_of_error"
                rows.append(
                    (
                        source["release_year"],
                        geography_id,
                        source["table_id"],
                        field_id,
                        measure,
                        _numeric(value),
                        source["artifact_id"],
                        source["source_ordinal"],
                    )
                )
                if len(rows) == 2_000:
                    cur.executemany(
                        "INSERT INTO fact.acs_bulk_estimate (release_year,geography_id,table_id,field_id,measure,value,source_artifact_id,source_ordinal) VALUES (%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING",
                        rows,
                    )
                    total += len(rows)
                    rows = []
                    conn.commit()
        if rows:
            cur.executemany(
                "INSERT INTO fact.acs_bulk_estimate (release_year,geography_id,table_id,field_id,measure,value,source_artifact_id,source_ordinal) VALUES (%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING",
                rows,
            )
            total += len(rows)
        conn.commit()
    return total


def _table_id_partitions(plan: dict[str, Any], workers: int) -> list[frozenset[str]]:
    """Split a plan's Detailed Table IDs into disjoint worker subsets.

    Partitioning by table_id (rather than by geography or row range) keeps
    each worker's SQL scoped to its own artifact_ids, so concurrent workers
    never contend for the same fact rows -- only the small, idempotent
    core.geography upsert is shared, which is safe under ON CONFLICT DO
    NOTHING.
    """
    table_ids = sorted({str(item["table_id"]) for item in _table_artifacts(plan)})
    workers = max(1, min(workers, len(table_ids)))
    return [
        frozenset(table_ids[worker::workers])
        for worker in range(workers)
        if table_ids[worker::workers]
    ]


def _stage_worker(plan: dict[str, Any], table_ids: frozenset[str]) -> int:
    return stage_acs_bulk(plan, table_ids=table_ids)


def stage_acs_bulk_parallel(
    plan: dict[str, Any], workers: int, update: Callable[[str], None] | None = None
) -> int:
    """Stage a plan's Detailed Tables across several worker processes."""
    partitions = _table_id_partitions(plan, workers)
    total = 0
    with ProcessPoolExecutor(max_workers=len(partitions)) as pool:
        futures = [pool.submit(_stage_worker, plan, part) for part in partitions]
        for future in as_completed(futures):
            total += future.result()
            if update:
                update(
                    f"Staged {total} ACS source rows across {len(partitions)} workers"
                )
    return total


def _load_worker(plan: dict[str, Any], table_ids: frozenset[str]) -> int:
    return load_acs_bulk(plan, table_ids=table_ids)


def load_acs_bulk_parallel(
    plan: dict[str, Any], workers: int, update: Callable[[str], None] | None = None
) -> int:
    """Load a plan's Detailed Tables across several worker processes."""
    partitions = _table_id_partitions(plan, workers)
    total = 0
    with ProcessPoolExecutor(max_workers=len(partitions)) as pool:
        futures = [pool.submit(_load_worker, plan, part) for part in partitions]
        for future in as_completed(futures):
            total += future.result()
            if update:
                update(f"Loaded {total} ACS estimates across {len(partitions)} workers")
    return total
