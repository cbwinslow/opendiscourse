"""Safe, named research exports from canonical database relations."""

from __future__ import annotations

import csv
import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from .db import connect
from .feedback import spinner

EXPORTS = {
    "measurements": (
        "SELECT measurement_id, dataset_id, field_id, geography_id, period_start, "
        "period_end, vintage_date, value_numeric, value_text, unit, flags, "
        "source_payload_id FROM fact.measurement "
        "ORDER BY dataset_id, field_id, period_start, measurement_id"
    ),
}


def available_exports() -> tuple[str, ...]:
    """Return the stable names accepted by the researcher export API."""
    return tuple(EXPORTS)


def export_relation(name: str, output: Path, format_: str) -> int:
    """Export one approved relation without accepting arbitrary SQL input."""
    try:
        statement = EXPORTS[name]
    except KeyError as exc:
        raise ValueError(f"Unknown export {name!r}; choose one of: {', '.join(EXPORTS)}") from exc
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite existing export: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    with spinner(f"Exporting {name} as {format_}") as update:
        with connect() as connection, connection.cursor() as cursor:
            cursor.execute(statement)
            rows = list(cursor.fetchall())
        update(f"Writing {len(rows)} {name} rows")
        _write(rows, output, format_)
    return len(rows)


def _write(rows: Iterable[dict[str, Any]], output: Path, format_: str) -> None:
    """Write rows in a portable researcher format."""
    materialized = list(rows)
    if format_ == "csv":
        fields = list(materialized[0]) if materialized else []
        with output.open("x", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            writer.writerows(materialized)
        return
    if format_ == "jsonl":
        with output.open("x") as stream:
            for row in materialized:
                stream.write(json.dumps(row, default=str, sort_keys=True) + "\n")
        return
    if format_ == "parquet":
        try:
            import polars as pl
        except ImportError as exc:
            raise RuntimeError("Parquet export requires `uv sync --extra analytics`") from exc
        pl.DataFrame(materialized).write_parquet(output)
        return
    raise ValueError("format must be one of: csv, jsonl, parquet")
