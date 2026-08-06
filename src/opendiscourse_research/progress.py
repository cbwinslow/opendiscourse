"""Validation and display for the version-controlled dataset work register."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .catalog import load_inventory

ROOT = Path(__file__).resolve().parents[2]


def load_progress() -> dict[str, Any]:
    return yaml.safe_load((ROOT / "inventory" / "progress.yaml").read_text())


def validate_progress() -> list[str]:
    source_ids = {
        dataset["id"]
        for provider in load_inventory()["providers"]
        for dataset in provider["datasets"]
    }
    register = load_progress()
    allowed = set(register["states"])
    seen: set[str] = set()
    errors: list[str] = []
    for item in register.get("items", []):
        item_id = item.get("id", "<unknown>")
        required = (
            "id",
            "state",
            "scope",
            "origin",
            "provenance",
            "sensitivity",
            "validate",
            "next",
        )
        missing = [field for field in required if not item.get(field)]
        if missing:
            errors.append(f"{item_id}: missing {', '.join(missing)}")
        if item_id in seen:
            errors.append(f"duplicate progress id: {item_id}")
        seen.add(item_id)
        if (
            not isinstance(item_id, str)
            or not item_id.isalnum()
            or item_id != item_id.lower()
        ):
            errors.append(f"{item_id}: id must be one lower-case alphanumeric word")
        if item.get("state") not in allowed:
            errors.append(f"{item_id}: unknown state {item.get('state')!r}")
        if item.get("dataset") is not None and item["dataset"] not in source_ids:
            errors.append(f"{item_id}: unknown dataset {item['dataset']!r}")
    return errors
