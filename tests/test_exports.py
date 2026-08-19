"""Unit tests for safe researcher-facing export formats."""

from pathlib import Path

import pytest

from opendiscourse_research.exports import _write, available_exports, export_relation


def test_available_exports_are_named_and_stable() -> None:
    """The public API exposes only reviewed relation names."""
    assert available_exports() == ("measurements",)


def test_write_csv_and_jsonl(tmp_path: Path) -> None:
    """Portable formats preserve a small representative research row."""
    rows = [{"dataset_id": "treasury.yield_curve", "value": 4.25}]
    csv_path = tmp_path / "measurements.csv"
    jsonl_path = tmp_path / "measurements.jsonl"

    _write(rows, csv_path, "csv")
    _write(rows, jsonl_path, "jsonl")

    assert csv_path.read_text() == "dataset_id,value\ntreasury.yield_curve,4.25\n"
    assert jsonl_path.read_text() == '{"dataset_id": "treasury.yield_curve", "value": 4.25}\n'


def test_export_rejects_unknown_relation_and_existing_output(tmp_path: Path) -> None:
    """Exports cannot execute arbitrary SQL or silently overwrite evidence."""
    with pytest.raises(ValueError, match="Unknown export"):
        export_relation("fact.measurement; DROP TABLE fact.measurement", tmp_path / "x.csv", "csv")

    output = tmp_path / "existing.csv"
    output.write_text("keep")
    with pytest.raises(FileExistsError, match="Refusing to overwrite"):
        export_relation("measurements", output, "csv")
