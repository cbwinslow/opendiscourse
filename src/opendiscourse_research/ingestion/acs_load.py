"""Artifact-linked county/state loading for ACS table-based summary files."""
from __future__ import annotations

import csv
from decimal import Decimal, InvalidOperation
from pathlib import Path
import re
from typing import Any, Callable

from psycopg.types.json import Jsonb

from ..db import connect


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
        raise ValueError(f"Choose supported ACS geography types {sorted(SUMMARY_LEVELS.values())}; got {sorted(unknown)}")
    return scope


def _artifact(conn: Any, dataset_id: str, key: str) -> dict[str, Any]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT artifact_id, local_path FROM ingest.artifact WHERE dataset_id=%s AND artifact_key=%s AND status IN ('downloaded','skipped')",
            (dataset_id, key),
        )
        row = cur.fetchone()
    if row is None:
        raise ValueError(f"Required ACS artifact {key!r} has not been downloaded")
    return row


def _table_artifacts(plan: dict[str, Any]) -> list[dict[str, Any]]:
    artifacts = [item for item in plan.get("artifacts", []) if item.get("kind") == "detailed_table"]
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


def stage_acs_bulk(plan: dict[str, Any], update: Callable[[str], None] | None = None) -> int:
    """Stage approved table rows for explicitly selected state/county geographies."""
    if plan.get("state") != "downloaded":
        raise ValueError("ACS plan must be downloaded before staging")
    dataset_id = str(plan.get("dataset", "census.acs_5_bulk"))
    scope = _scope(plan)
    total = 0
    with connect() as conn:
        for item in _table_artifacts(plan):
            artifact = _artifact(conn, dataset_id, str(item["artifact_key"]))
            if update:
                update(f"Staging ACS {item['table_id']}")
            rows = []
            with Path(artifact["local_path"]).open(encoding="utf-8-sig", newline="") as source:
                for ordinal, row in enumerate(csv.DictReader(source, delimiter="|"), start=1):
                    parsed = _geo_id(str(row.get("GEO_ID", "")))
                    if parsed is None or parsed[0] not in scope:
                        continue
                    rows.append((artifact["artifact_id"], ordinal, int(item["release_year"]), str(item["table_id"]), parsed[0], parsed[1], Jsonb(row)))
                    if len(rows) == 2_000:
                        with conn.cursor() as cur:
                            cur.executemany("INSERT INTO stage.acs_bulk_row (artifact_id,source_ordinal,release_year,table_id,geography_type,geoid,raw) VALUES (%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING", rows)
                        total += len(rows)
                        rows = []
            if rows:
                with conn.cursor() as cur:
                    cur.executemany("INSERT INTO stage.acs_bulk_row (artifact_id,source_ordinal,release_year,table_id,geography_type,geoid,raw) VALUES (%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING", rows)
                total += len(rows)
            conn.commit()
    return total


def load_acs_bulk(plan: dict[str, Any], update: Callable[[str], None] | None = None) -> int:
    """Promote staged ACS estimates/MOEs to typed artifact-linked facts."""
    if plan.get("state") != "staged":
        raise ValueError("ACS plan must be staged before canonical loading")
    dataset_id = str(plan.get("dataset", "census.acs_5_bulk"))
    scope = list(_scope(plan))
    total = 0
    if update:
        update("Creating ACS geographies")
    with connect() as conn, conn.cursor() as cur:
        artifact_ids = [
            _artifact(conn, dataset_id, str(item["artifact_key"]))["artifact_id"]
            for item in _table_artifacts(plan)
        ]
        cur.execute("""INSERT INTO core.geography (geography_type,geoid,state_fips,county_fips)
          SELECT DISTINCT geography_type, geoid, substring(geoid from '^([0-9]{2})'), CASE WHEN geography_type='county' THEN substring(geoid from '^[0-9]{2}([0-9]{3})') END
          FROM stage.acs_bulk_row WHERE artifact_id=ANY(%s) AND geography_type=ANY(%s)
          ON CONFLICT (geography_type,geoid) DO NOTHING""", (artifact_ids, scope))
        cur.execute("SELECT geography_id,geography_type,geoid FROM core.geography")
        geographies = {(row["geography_type"], row["geoid"]): row["geography_id"] for row in cur.fetchall()}
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
                rows.append((source["release_year"], geography_id, source["table_id"], field_id, measure, _numeric(value), source["artifact_id"], source["source_ordinal"]))
                if len(rows) == 2_000:
                    cur.executemany("INSERT INTO fact.acs_bulk_estimate (release_year,geography_id,table_id,field_id,measure,value,source_artifact_id,source_ordinal) VALUES (%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING", rows)
                    total += len(rows)
                    rows = []
        if rows:
            cur.executemany("INSERT INTO fact.acs_bulk_estimate (release_year,geography_id,table_id,field_id,measure,value,source_artifact_id,source_ordinal) VALUES (%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING", rows)
            total += len(rows)
        conn.commit()
    return total
