"""Read-only planning evidence for an OpenStates congressional vote refresh."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
from typing import Any

from .config import settings
from .contracts import get_contract
from .db import connect
from .repositories.legislation import openstates_vote_snapshot_counts


def _report_path(contract_id: str) -> Path:
    """Return the data-lake path for a refresh dry-run report."""
    return (
        Path(settings.data_root).expanduser().resolve().parent
        / "meta"
        / "plan"
        / "openstates"
        / f"{contract_id}-dry-run.json"
    )


def validate_openstates_vote_contract(contract: dict[str, Any]) -> None:
    """Reject contracts that cannot safely describe a snapshot vote refresh."""
    if contract.get("provider") != "openstates" or contract.get("kind") != "snapshot_incremental":
        raise ValueError("contract must be an OpenStates snapshot_incremental contract")
    selection = contract.get("selection") or {}
    if selection.get("entities") != ["voteevent", "personvote"]:
        raise ValueError("contract must select voteevent and personvote")
    if not all(isinstance(value, int) and value > 0 for value in selection.get("congresses", [])):
        raise ValueError("contract must name one or more positive Congress numbers")
    cursor = contract.get("cursor") or {}
    if cursor.get("strategy") != "ocd_vote_event_keyset" or cursor.get("key") != "ocd_id":
        raise ValueError("contract must use the ocd_id keyset cursor")
    if not (contract.get("validation") or {}).get("dry_run_required"):
        raise ValueError("contract must require a dry run")
    snapshot = contract.get("snapshot") or {}
    if not isinstance(snapshot.get("endpoint_template"), str):
        raise ValueError("contract must name the provider snapshot endpoint template")


def build_openstates_vote_dry_run(
    contract: dict[str, Any], counts: dict[str, dict[str, Any]], free_bytes: int
) -> dict[str, Any]:
    """Build a serializable no-write refresh report from inspected evidence."""
    validation = contract["validation"]
    readiness = {
        "contract_enabled": bool(contract.get("enabled")),
        "approval": contract.get("approval"),
        "source_access_approved": contract.get("approval") not in {None, "pending"},
        "snapshot_acquisition_authorized": False,
        "promotion_authorized": False,
    }
    return {
        "schema": 1,
        "kind": "openstates_vote_refresh_dry_run",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "contract": contract["id"],
        "state": "ready_for_review" if readiness["source_access_approved"] else "approval_required",
        "readiness": readiness,
        "snapshot": {
            "source": contract["provenance"]["source"],
            "endpoint_template": contract["snapshot"]["endpoint_template"],
            "current_watermark": {
                congress: values.get("source_updated_at_max")
                for congress, values in counts.items()
            },
            "artifact_key": None,
            "checksum_sha256": None,
            "reason": "No new source snapshot has been approved or acquired.",
        },
        "coverage": counts,
        "storage": {
            "available_bytes": free_bytes,
            "reserve_gib": contract["storage"]["reserve_gib"],
            "sufficient_reserve": free_bytes >= contract["storage"]["reserve_gib"] * 1024**3,
        },
        "no_writes": {
            "provider": True,
            "source_snapshot": True,
            "canonical_tables": True,
            "ingest_run": True,
        },
        "validation": {
            "dry_run_required": validation["dry_run_required"],
            "reconcile_command": validation["reconcile_command"],
            "idempotency_required": validation["idempotency_required"],
        },
        "next": (
            "Review this report, approve source access and storage, then acquire a new "
            "immutable OpenStates snapshot. Do not promote 119th vote coverage from partial."
        ),
    }


def dry_run_openstates_vote_refresh(contract_id: str = "openstatesvotes") -> dict[str, Any]:
    """Inspect the provisioned source snapshot under a read-only transaction."""
    contract = get_contract(contract_id)
    validate_openstates_vote_contract(contract)
    congresses = contract["selection"]["congresses"]
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SET TRANSACTION READ ONLY")
        counts = openstates_vote_snapshot_counts(congresses, conn)
        conn.rollback()
    free_bytes = shutil.disk_usage(Path(settings.data_root).expanduser()).free
    result = build_openstates_vote_dry_run(contract, counts, free_bytes)
    target = _report_path(contract_id)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(result, indent=2, sort_keys=True, default=str) + "\n")
    temporary.replace(target)
    result["report"] = str(target)
    return result
