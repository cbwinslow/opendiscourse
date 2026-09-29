"""Assemble a read-only source lifecycle report from contracts and evidence."""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select

from ..contracts import load_contracts
from ..db import session
from ..models.catalog import artifact_table
from ..models.core import (
    housing_archive_release_table,
    housing_microdata_projection_table,
)
from ..models.ingest import run_table, run_target_table
from ..models.stage import stage_acs_pums_record, stage_ahs_record
from .artifacts import current_artifacts


def _contract_for_dataset(dataset_id: str) -> dict[str, Any]:
    matches = [contract for contract in load_contracts() if contract.get("dataset") == dataset_id]
    if len(matches) != 1:
        raise ValueError(f"Expected one source contract for dataset {dataset_id!r}, found {len(matches)}")
    return matches[0]


def source_status(dataset_id: str) -> dict[str, Any]:
    """Return approved source intent and evidence-ledger facts in stable JSON-ready data."""
    contract = _contract_for_dataset(dataset_id)
    artifacts = artifact_table()
    current = current_artifacts(dataset_id)
    with session() as active_session:
        runs = run_table()
        targets = run_target_table()
        attempts = [
            dict(row)
            for row in active_session.execute(
                select(
                    artifacts.c.artifact_id,
                    artifacts.c.artifact_key,
                    artifacts.c.artifact_version,
                    artifacts.c.remote_url,
                    artifacts.c.status,
                    artifacts.c.bytes_downloaded,
                    artifacts.c.checksum_sha256,
                    artifacts.c.error_message,
                    artifacts.c.metadata,
                )
                .where(artifacts.c.dataset_id == dataset_id)
                .order_by(artifacts.c.artifact_key, artifacts.c.artifact_version)
            ).mappings()
        ]
        artifact_ids = select(artifacts.c.artifact_id).where(artifacts.c.dataset_id == dataset_id)
        stage = {
            "acs_pums_rows": active_session.execute(
                select(func.count()).select_from(stage_acs_pums_record).where(
                    stage_acs_pums_record.c.artifact_id.in_(artifact_ids)
                )
            ).scalar_one(),
            "ahs_rows": active_session.execute(
                select(func.count()).select_from(stage_ahs_record).where(
                    stage_ahs_record.c.artifact_id.in_(artifact_ids)
                )
            ).scalar_one(),
        }
        published = {
            "releases": active_session.execute(
                select(func.count()).select_from(housing_archive_release_table).where(
                    housing_archive_release_table.c.dataset_id == dataset_id
                )
            ).scalar_one(),
            "projection_rows": active_session.execute(
                select(func.count()).select_from(housing_microdata_projection_table).where(
                    housing_microdata_projection_table.c.artifact_id.in_(artifact_ids)
                )
            ).scalar_one(),
        }
        current_run = active_session.execute(
            select(runs).where(runs.c.dataset_id == dataset_id).order_by(runs.c.started_at.desc()).limit(1)
        ).mappings().first()
        reconciliation: list[dict[str, Any]] = []
        if current_run is not None:
            reconciliation = [
                dict(row)
                for row in active_session.execute(
                    select(
                        targets.c.target, targets.c.coverage_key, targets.c.status,
                        targets.c.rows_parsed, targets.c.rows_inserted,
                        targets.c.rows_existing, targets.c.rows_rejected,
                    )
                    .where(targets.c.run_id == current_run["run_id"])
                    .order_by(targets.c.target, targets.c.coverage_key)
                ).mappings()
            ]
    usable_groups: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for row in current.values():
        metadata = row["metadata"] or {}
        group_key = (
            str(metadata.get("product", "unclassified")),
            str(metadata.get("period", "unclassified")),
            str(metadata.get("kind", "unclassified")),
            str(row["status"]),
        )
        group = usable_groups.setdefault(
            group_key,
            {
                "product": group_key[0],
                "period": group_key[1],
                "kind": group_key[2],
                "status": group_key[3],
                "artifact_count": 0,
                "bytes": 0,
            },
        )
        group["artifact_count"] += 1
        group["bytes"] += row["bytes_downloaded"] or 0
    failures = [
        {
            "artifact_key": row["artifact_key"],
            "artifact_version": row["artifact_version"],
            "remote_url": row["remote_url"],
            "error": row["error_message"],
            "metadata": row["metadata"],
        }
        for row in attempts
        if row["status"] == "failed"
    ]
    return {
        "dataset": dataset_id,
        "contract": {
            "id": contract["id"],
            "provider": contract["provider"],
            "products": contract.get("products", []),
            "selection": contract.get("selection", {}),
            "approval": contract.get("approval"),
            "lifecycle_state": contract.get("lifecycle_state"),
            "endpoint_policy": contract.get("endpoint_policy"),
            "target_layers": contract.get("target", []),
            "gaps": contract.get("gaps", []),
        },
        "artifacts": {
            "usable": [usable_groups[key] for key in sorted(usable_groups)],
            "usable_artifact_count": len(current),
            "failures": failures,
            "attempt_count": len(attempts),
            "retained_bytes": sum(row["bytes_downloaded"] or 0 for row in current.values()),
        },
        "stage": stage,
        "published": published,
        "current_run": (
            {
                "run_id": str(current_run["run_id"]),
                "status": current_run["status"],
                "code_version": current_run["code_version"],
                "checkpoint": (current_run["parameters"] or {}).get("checkpoint", {}),
                "reconciliation": reconciliation,
                "unresolved_failure": current_run["status"] in {"failed", "partial"},
            }
            if current_run is not None
            else None
        ),
    }
