"""Safe, named research exports from canonical database relations."""

from __future__ import annotations

import csv
import json
import os
import tempfile
from collections.abc import Callable, Iterable, Sequence
from decimal import Decimal
from pathlib import Path
from typing import Any

import psycopg

from .db import connect
from .feedback import spinner

_FORMATS = ("csv", "jsonl", "parquet")

_MEASUREMENT_FIELDS = (
    "measurement_id",
    "dataset_id",
    "field_id",
    "geography_id",
    "period_start",
    "period_end",
    "vintage_date",
    "value_numeric",
    "value_text",
    "unit",
    "margin_of_error",
    "flags",
    "source_payload_id",
)

EXPORTS = {
    "measurements": (
        _MEASUREMENT_FIELDS,
        "SELECT " + ", ".join(_MEASUREMENT_FIELDS) + " FROM fact.measurement "
        "ORDER BY dataset_id, field_id, period_start, measurement_id",
    ),
}


def available_exports() -> tuple[str, ...]:
    """Return the stable names accepted by the researcher export API."""
    return tuple(EXPORTS)


def export_relation(name: str, output: Path, format_: str) -> int:
    """Export one approved relation without accepting arbitrary SQL input."""
    if format_ not in _FORMATS:
        raise ValueError(f"format must be one of: {', '.join(_FORMATS)}")
    try:
        fields, statement = EXPORTS[name]
    except KeyError as exc:
        raise ValueError(f"Unknown export {name!r}; choose one of: {', '.join(EXPORTS)}") from exc
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite existing export: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    with spinner(f"Exporting {name} as {format_}") as update:
        try:
            with connect() as connection, connection.cursor() as cursor:
                cursor.execute(statement)
                rows = cursor.fetchall()
        except psycopg.Error as exc:
            raise RuntimeError(f"Export query failed: {exc}") from exc
        update(f"Writing {len(rows)} {name} rows")
        _write(rows, output, format_, fields)
    return len(rows)


def _json_default(value: Any) -> Any:
    """Preserve numeric precision for Decimal columns; fall back to text for the rest."""
    if isinstance(value, Decimal):
        return float(value)
    return str(value)


def _atomic_write(
    output: Path, mode: str, writer: Callable[[Any], None], **open_kwargs: Any
) -> None:
    """Write through a same-directory temp file, then publish with an exclusive, atomic link.

    ``os.link`` fails with ``FileExistsError`` if ``output`` already exists, so two
    concurrent exports can never both succeed and a partially written file is never
    visible at the final path.
    """
    fd, tmp_name = tempfile.mkstemp(dir=output.parent, prefix=f".{output.name}.")
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, mode, **open_kwargs) as stream:
            writer(stream)
        os.link(tmp_path, output)
    except FileExistsError:
        raise FileExistsError(f"Refusing to overwrite existing export: {output}") from None
    finally:
        tmp_path.unlink(missing_ok=True)


def _write(
    rows: Iterable[dict[str, Any]],
    output: Path,
    format_: str,
    fields: Sequence[str] = (),
) -> None:
    """Write rows in a portable researcher format, publishing atomically."""
    if format_ not in _FORMATS:
        raise ValueError(f"format must be one of: {', '.join(_FORMATS)}")
    materialized = list(rows)
    fieldnames = list(fields) if fields else (list(materialized[0]) if materialized else [])
    if format_ == "csv":

        def write_csv(stream: Any) -> None:
            writer = csv.DictWriter(stream, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(materialized)

        _atomic_write(output, "w", write_csv, newline="")
        return
    if format_ == "jsonl":

        def write_jsonl(stream: Any) -> None:
            for row in materialized:
                stream.write(json.dumps(row, default=_json_default, sort_keys=True) + "\n")

        _atomic_write(output, "w", write_jsonl)
        return

    try:
        import polars as pl
    except ImportError as exc:
        raise RuntimeError("Parquet export requires `uv sync --extra analytics`") from exc

    def write_parquet(stream: Any) -> None:
        pl.DataFrame(materialized).write_parquet(stream)

    _atomic_write(output, "wb", write_parquet)
