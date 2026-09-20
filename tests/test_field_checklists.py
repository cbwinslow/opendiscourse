"""Every field checklist under inventory/fields follows the format in inventory/DATA-SPEC.md."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from opendiscourse_research.catalog import load_inventory

FIELDS = Path(__file__).resolve().parents[1] / "inventory" / "fields"
STATUSES = {"typed", "whole_record_only", "not_stored"}
CHECKLISTS = sorted(FIELDS.glob("*.yaml"))


def _dataset_ids() -> set[str]:
    return {d["id"] for p in load_inventory()["providers"] for d in p["datasets"]}


def test_there_is_at_least_one_checklist() -> None:
    assert CHECKLISTS


@pytest.mark.parametrize("path", CHECKLISTS, ids=lambda p: p.name)
def test_checklist_is_complete_and_honest(path: Path) -> None:
    document = yaml.safe_load(path.read_text())
    assert document["dataset"] == path.stem, "the file is named after its dataset"
    assert document["dataset"] in _dataset_ids(), "dataset is not in inventory/sources.yaml"
    assert document.get("audited_on") and document.get("origin")
    assert "whole_record" in (document.get("capture") or {}), "say where the whole record is kept (or null)"
    fields = document.get("fields") or []
    assert fields, "a checklist lists at least one field or group"
    for field in fields:
        name = field.get("name")
        assert name and field.get("status") in STATUSES, f"{name!r}: status must be one of {sorted(STATUSES)}"
        if field["status"] != "typed":
            assert field.get("reason"), f"{name!r}: {field['status']} needs a reason"
        if field["status"] == "typed":
            assert field.get("where"), f"{name!r}: typed needs the table it lands in"
