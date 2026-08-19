"""Unit tests for safe researcher-facing export formats."""

import os
from decimal import Decimal
from pathlib import Path

import pytest

from opendiscourse_research import exports
from opendiscourse_research.exports import (
    EXPORTS,
    _write,
    available_exports,
    export_relation,
)


def test_available_exports_are_named_and_stable() -> None:
    """The public API exposes only reviewed relation names."""
    assert available_exports() == ("measurements",)


def test_measurements_export_includes_margin_of_error() -> None:
    """The named export cannot silently drop a real fact.measurement column."""
    fields, statement = EXPORTS["measurements"]
    assert "margin_of_error" in fields
    assert "margin_of_error" in statement


def test_write_csv_and_jsonl(tmp_path: Path) -> None:
    """Portable formats preserve a small representative research row."""
    rows = [{"dataset_id": "treasury.yield_curve", "value": 4.25}]
    csv_path = tmp_path / "measurements.csv"
    jsonl_path = tmp_path / "measurements.jsonl"

    _write(rows, csv_path, "csv")
    _write(rows, jsonl_path, "jsonl")

    assert csv_path.read_text() == "dataset_id,value\ntreasury.yield_curve,4.25\n"
    assert jsonl_path.read_text() == '{"dataset_id": "treasury.yield_curve", "value": 4.25}\n'


def test_write_csv_empty_result_uses_canonical_header(tmp_path: Path) -> None:
    """An empty result still yields the reviewed column list, not a blank file."""
    csv_path = tmp_path / "measurements.csv"

    _write([], csv_path, "csv", fields=("dataset_id", "value"))

    assert csv_path.read_text() == "dataset_id,value\n"


def test_write_jsonl_preserves_decimal_precision(tmp_path: Path) -> None:
    """Numeric columns like value_numeric/margin_of_error stay exact JSON numbers.

    Routing through float would silently drop the trailing zero and, for a
    long enough coefficient, round the value -- exercised here with more
    digits than a float's ~15-17 significant digits can carry exactly.
    """
    rows = [
        {
            "value_numeric": Decimal("4.25"),
            "margin_of_error": Decimal("0.10"),
            "value_text": Decimal("123456789012345678901234567890.123456789"),
        }
    ]
    jsonl_path = tmp_path / "measurements.jsonl"

    _write(rows, jsonl_path, "jsonl")

    assert jsonl_path.read_text() == (
        '{"margin_of_error": 0.10, "value_numeric": 4.25, '
        '"value_text": 123456789012345678901234567890.123456789}\n'
    )


def test_write_jsonl_rejects_non_finite_decimal(tmp_path: Path) -> None:
    """NaN/Infinity are valid Decimal values but not valid JSON numbers."""
    rows = [{"value_numeric": Decimal("NaN")}]
    jsonl_path = tmp_path / "measurements.jsonl"

    with pytest.raises(ValueError, match="non-finite"):
        _write(rows, jsonl_path, "jsonl")

    assert not jsonl_path.exists()
    assert list(tmp_path.iterdir()) == []


def test_write_does_not_clobber_a_competing_writer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A destination created between the pre-check and publish must not be overwritten.

    ``os.link`` is where the export actually becomes visible; simulate a second
    process winning that race by creating ``output`` just before the real link.
    """
    output = tmp_path / "measurements.csv"
    real_link = os.link

    def racing_link(src: str, dst: str) -> None:
        Path(dst).write_text("written by a competing export\n")
        real_link(src, dst)

    monkeypatch.setattr(exports.os, "link", racing_link)

    with pytest.raises(FileExistsError, match="Refusing to overwrite"):
        _write([{"a": 1}], output, "csv")

    assert output.read_text() == "written by a competing export\n"
    assert list(tmp_path.iterdir()) == [output]


def test_export_rejects_unknown_relation_and_existing_output(tmp_path: Path) -> None:
    """Exports cannot execute arbitrary SQL or silently overwrite evidence."""
    with pytest.raises(ValueError, match="Unknown export"):
        export_relation("fact.measurement; DROP TABLE fact.measurement", tmp_path / "x.csv", "csv")

    output = tmp_path / "existing.csv"
    output.write_text("keep")
    with pytest.raises(FileExistsError, match="Refusing to overwrite"):
        export_relation("measurements", output, "csv")


def test_export_rejects_unknown_format(tmp_path: Path) -> None:
    """Format is validated before touching the filesystem or the database."""
    with pytest.raises(ValueError, match="format must be one of"):
        export_relation("measurements", tmp_path / "x.tsv", "tsv")


def test_write_rejects_unknown_format(tmp_path: Path) -> None:
    """`_write` enforces the same accepted-format contract as `export_relation`."""
    with pytest.raises(ValueError, match="format must be one of"):
        _write([], tmp_path / "x.tsv", "tsv")
