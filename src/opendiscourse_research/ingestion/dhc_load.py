"""LOGRECNO-aware staging and table-scoped canonical loading for 2020 DHC."""

from __future__ import annotations

import csv
import io
from collections.abc import Callable
from pathlib import Path
from typing import Any
from zipfile import ZipFile

from psycopg.types.json import Jsonb
from sqlalchemy import select

from ..db import connect, session
from ..models.catalog import artifact_table

PREFIX_FIELDS = 5  # FILEID, STUSAB, CHARITER, CIFSN, LOGRECNO


def _artifact(key: str) -> dict[str, Any]:
    """Return a downloaded DHC artifact through immutable typed evidence storage."""
    table = artifact_table()
    with session() as active_session:
        row = active_session.execute(
            select(table.c.artifact_id, table.c.local_path).where(
                table.c.artifact_key == key,
                table.c.status.in_(("downloaded", "skipped")),
            )
        ).mappings().first()
    if row is None:
        raise ValueError(f"Required DHC artifact {key!r} has not been downloaded")
    return dict(row)


def _scope(plan: dict[str, Any]) -> tuple[set[str], set[str]]:
    scope = plan.get("canonical_load_scope", {})
    levels = set(scope.get("summary_levels", []))
    tables = {str(table).upper() for table in scope.get("tables", [])}
    if not levels or not tables:
        raise ValueError("DHC approval requires --summary-level and --table selections")
    return levels, tables


def _matrix(path: Path, requested: set[str]) -> dict[int, list[tuple[str, str, int]]]:
    try:
        import openpyxl
    except ImportError as exc:
        raise RuntimeError("DHC loading requires `uv sync --extra ingest`") from exc
    sheet = openpyxl.load_workbook(path, read_only=True, data_only=True)[
        "DHC Table Matrix"
    ]
    result: dict[int, list[tuple[str, str, int]]] = {}
    counters: dict[int, int] = {}
    current = ""
    found: set[str] = set()
    for row in sheet.iter_rows(min_row=3, values_only=True):
        if row[1]:
            current = str(row[1]).strip()
        variable, segment = row[2], row[3]
        if not variable or not segment:
            continue
        segment_number = int(segment)
        ordinal = counters.get(segment_number, PREFIX_FIELDS)
        counters[segment_number] = ordinal + 1
        if current in requested:
            result.setdefault(segment_number, []).append(
                (current, str(variable).strip(), ordinal)
            )
            found.add(current)
    if missing := requested - found:
        raise ValueError(
            f"DHC table IDs not found in official table matrix: {sorted(missing)}"
        )
    return result


def stage_dhc(plan: dict[str, Any], update: Callable[[str], None] | None = None) -> int:
    """Stage selected DHC GEO records without altering canonical facts."""
    if plan.get("state") != "downloaded":
        raise ValueError("DHC plan must be downloaded before staging")
    levels, _ = _scope(plan)
    total = 0
    with connect() as conn:
        artifact = _artifact("dhc-2020-national")
        with ZipFile(Path(artifact["local_path"])) as archive:
            for member in (
                name for name in archive.namelist() if "geo2020.dhc" in name.lower()
            ):
                if update:
                    update(f"Staging DHC GEO: {member}")
                rows = []
                with archive.open(member) as binary:
                    reader = csv.reader(
                        io.TextIOWrapper(binary, encoding="latin-1"), delimiter="|"
                    )
                    for ordinal, fields in enumerate(reader, start=1):
                        if len(fields) < 9 or fields[2] not in levels:
                            continue
                        rows.append(
                            (
                                artifact["artifact_id"],
                                member,
                                ordinal,
                                fields[7],
                                fields[2],
                                fields[8],
                                Jsonb({"fields": fields}),
                            )
                        )
                        if len(rows) == 2_000:
                            with conn.cursor() as cur:
                                cur.executemany(
                                    "INSERT INTO stage.dhc_geo_row (artifact_id,source_member,source_ordinal,logrecno,sumlev,geoid,raw) VALUES (%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING",
                                    rows,
                                )
                            total += len(rows)
                            rows = []
                if rows:
                    with conn.cursor() as cur:
                        cur.executemany(
                            "INSERT INTO stage.dhc_geo_row (artifact_id,source_member,source_ordinal,logrecno,sumlev,geoid,raw) VALUES (%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING",
                            rows,
                        )
                    total += len(rows)
                conn.commit()
    return total


def load_dhc(plan: dict[str, Any], update: Callable[[str], None] | None = None) -> int:
    """Promote selected DHC tables by joining segment records to GEO LOGRECNO."""
    if plan.get("state") != "staged":
        raise ValueError("DHC plan must be staged before canonical loading")
    levels, tables = _scope(plan)
    total = 0
    with connect() as conn:
        artifact = _artifact("dhc-2020-national")
        matrix = _artifact("dhc-2020-table-matrix")
        segments = _matrix(Path(matrix["local_path"]), tables)
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO core.geography (geography_type,geoid,state_fips,county_fips)
              SELECT DISTINCT CASE sumlev WHEN '040' THEN 'state' WHEN '050' THEN 'county' WHEN '140' THEN 'tract' ELSE 'census_'||sumlev END,
                geoid, substring(geoid from 'US([0-9]{2})'), substring(geoid from 'US[0-9]{2}([0-9]{3})')
              FROM stage.dhc_geo_row WHERE artifact_id=%s AND sumlev=ANY(%s)
              ON CONFLICT (geography_type,geoid) DO NOTHING""",
                (artifact["artifact_id"], list(levels)),
            )
            cur.execute(
                "SELECT logrecno,sumlev,geoid FROM stage.dhc_geo_row WHERE artifact_id=%s AND sumlev=ANY(%s)",
                (artifact["artifact_id"], list(levels)),
            )
            geography = {row["logrecno"]: row for row in cur.fetchall()}
            cur.execute("SELECT geography_id,geography_type,geoid FROM core.geography")
            ids = {
                (row["geography_type"], row["geoid"]): row["geography_id"]
                for row in cur.fetchall()
            }
        with ZipFile(Path(artifact["local_path"])) as archive:
            for segment, variables in segments.items():
                suffix = f"{segment:04d}2020.dhc"
                for member in (
                    name for name in archive.namelist() if name.lower().endswith(suffix)
                ):
                    if update:
                        update(f"Loading DHC segment {segment}: {member}")
                    rows = []
                    with archive.open(member) as binary:
                        reader = csv.reader(
                            io.TextIOWrapper(binary, encoding="latin-1"), delimiter="|"
                        )
                        for ordinal, fields in enumerate(reader, start=1):
                            if (
                                len(fields) <= PREFIX_FIELDS
                                or (geo := geography.get(fields[4])) is None
                            ):
                                continue
                            kind = {
                                "040": "state",
                                "050": "county",
                                "140": "tract",
                            }.get(geo["sumlev"], "census_" + geo["sumlev"])
                            geography_id = ids[(kind, geo["geoid"])]
                            for table, variable, index in variables:
                                if (
                                    index < len(fields)
                                    and fields[index].lstrip("-").isdigit()
                                ):
                                    rows.append(
                                        (
                                            2020,
                                            geography_id,
                                            table,
                                            variable,
                                            int(fields[index]),
                                            artifact["artifact_id"],
                                            member,
                                            ordinal,
                                        )
                                    )
                            if len(rows) >= 5_000:
                                with conn.cursor() as cur:
                                    cur.executemany(
                                        "INSERT INTO fact.decennial_dhc_value (release_year,geography_id,table_id,variable_id,value,source_artifact_id,source_member,source_ordinal) VALUES (%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING",
                                        rows,
                                    )
                                total += len(rows)
                                rows = []
                    if rows:
                        with conn.cursor() as cur:
                            cur.executemany(
                                "INSERT INTO fact.decennial_dhc_value (release_year,geography_id,table_id,variable_id,value,source_artifact_id,source_member,source_ordinal) VALUES (%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING",
                                rows,
                            )
                        total += len(rows)
                    conn.commit()
    return total
