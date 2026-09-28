from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

CONTRACT_ROOT = Path(__file__).resolve().parents[2] / "inventory" / "contracts"


def load_contracts() -> list[dict[str, Any]]:
    """Load all version-controlled ingestion contracts by their short IDs."""
    items: list[dict[str, Any]] = []
    for path in sorted(CONTRACT_ROOT.glob("*.yaml")):
        payload = yaml.safe_load(path.read_text()) or {}
        for contract in payload.get("contracts", []):
            item = dict(contract)
            item["_file"] = str(path.relative_to(CONTRACT_ROOT.parent))
            items.append(item)
    return items


def get_contract(contract_id: str) -> dict[str, Any]:
    matches = [item for item in load_contracts() if item.get("id") == contract_id]
    if len(matches) != 1:
        raise ValueError(
            f"Expected one contract named {contract_id!r}, found {len(matches)}"
        )
    return matches[0]


def validate_contracts() -> list[str]:
    errors: list[str] = []
    seen: set[str] = set()
    required = {"id", "provider", "dataset", "cadence", "target"}
    for contract in load_contracts():
        label = f"{contract.get('_file')}:{contract.get('id', '?')}"
        missing = sorted(required - contract.keys())
        if missing:
            errors.append(f"{label}: missing {', '.join(missing)}")
        contract_id = contract.get("id")
        if (
            not isinstance(contract_id, str)
            or not contract_id.isalnum()
            or contract_id.lower() != contract_id
        ):
            errors.append(f"{label}: id must be a lowercase one-word identifier")
        elif contract_id in seen:
            errors.append(f"{label}: duplicate contract id")
        else:
            seen.add(contract_id)
        if (
            contract.get("provider") == "census"
            and contract.get("kind", "acs_group") == "acs_group"
        ):
            for key in ("endpoint", "year", "geography", "states", "groups"):
                if key not in contract:
                    errors.append(f"{label}: Census contract missing {key}")
        if contract.get("provider") == "census" and contract.get("kind") == "acs_bulk":
            for key in ("year", "products", "selection", "approval"):
                if key not in contract:
                    errors.append(f"{label}: ACS bulk contract missing {key}")
        if contract.get("kind") == "archive_manifest":
            for key in (
                "products",
                "selection",
                "storage",
                "approval",
                "endpoint_policy",
                "lifecycle_state",
                "target",
            ):
                if key not in contract:
                    errors.append(f"{label}: archive manifest contract missing {key}")
            if not isinstance(contract.get("products"), list) or not contract.get("products"):
                errors.append(f"{label}: archive manifest products must be a non-empty list")
            if not isinstance(contract.get("target"), list) or not contract.get("target"):
                errors.append(f"{label}: archive manifest target must be a non-empty list")
            if not isinstance(contract.get("selection"), dict) or not contract["selection"]:
                errors.append(f"{label}: archive manifest selection must be a non-empty mapping")
            if not isinstance(contract.get("storage"), dict) or not contract["storage"]:
                errors.append(f"{label}: archive manifest storage must be a non-empty mapping")
    return errors
