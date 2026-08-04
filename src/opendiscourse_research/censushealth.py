"""Read-only health reporting for Census bulk packages and canonical lineage."""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

import yaml

from .config import settings
from .db import connect


FAMILIES = {
    "census.acs_5_bulk": {"name": "ACS 5-year bulk", "fact_table": "fact.acs_bulk_estimate"},
    "census.business_patterns": {"name": "County Business Patterns", "fact_table": "fact.business_pattern"},
    "census.population_estimates": {"name": "Population Estimates Program", "fact_table": "fact.population_estimate"},
    "census.decennial": {"name": "2020 Decennial DHC", "fact_table": "fact.decennial_dhc_value"},
    "census.tiger": {"name": "TIGER/Line", "fact_table": "core.geography_boundary"},
}


def plan_files() -> list[tuple[Path, dict[str, Any]]]:
    """Return readable Census bulk plans without changing their lifecycle state."""
    root = Path(settings.data_root).expanduser().resolve().parent / "meta" / "bulk-plans"
    result = []
    for path in sorted(root.glob("*.yaml")) if root.is_dir() else []:
        payload = yaml.safe_load(path.read_text()) or {}
        if payload.get("dataset") in FAMILIES:
            result.append((path, payload))
    return result


def classify_plan(plan: dict[str, Any], artifacts: list[dict[str, Any]], fact_count: int) -> tuple[str, list[str]]:
    """Classify one plan from immutable artifact and canonical lineage evidence."""
    state = str(plan.get("state", "draft"))
    expected = {str(item.get("artifact_key")) for item in plan.get("artifacts", [])}
    by_key = {str(row.get("artifact_key")): row for row in artifacts}
    missing = sorted(expected - set(by_key))
    errors = [f"missing artifact: {key}" for key in missing]
    errors.extend(f"artifact failed: {row['artifact_key']}" for row in artifacts if row.get("status") == "failed")
    if state == "loaded" and errors:
        return "failed", errors
    if state == "loaded" and fact_count == 0:
        return "failed", ["loaded plan has no canonical artifact-linked rows"]
    if state == "loaded":
        return "healthy", []
    if state in {"draft", "approved", "downloaded", "staged"}:
        return "attention", []
    return "failed", [f"unknown plan lifecycle state: {state}"]


def _artifacts(conn: Any, keys: list[str]) -> list[dict[str, Any]]:
    if not keys:
        return []
    with conn.cursor() as cur:
        cur.execute("SELECT artifact_id, artifact_key, status, local_path, bytes_downloaded, checksum_sha256, error_message FROM ingest.artifact WHERE artifact_key = ANY(%s)", (keys,))
        return [dict(row) for row in cur.fetchall()]


def _fact_count(conn: Any, dataset_id: str, artifact_ids: list[str]) -> int:
    table = FAMILIES[dataset_id]["fact_table"]
    if not table or not artifact_ids:
        return 0
    with conn.cursor() as cur:
        cur.execute(f"SELECT count(*) AS count FROM {table} WHERE source_artifact_id = ANY(%s)", (artifact_ids,))
        return int(cur.fetchone()["count"])


def census_health() -> dict[str, Any]:
    """Persist a source-aware Census health report without loading provider data."""
    plans = plan_files()
    groups: dict[str, list[dict[str, Any]]] = {dataset: [] for dataset in FAMILIES}
    with connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT dataset_id, count(*) AS package_count FROM catalog.resource WHERE dataset_id = ANY(%s) GROUP BY dataset_id", (list(FAMILIES),))
        packages = {row["dataset_id"]: int(row["package_count"]) for row in cur.fetchall()}
        for path, plan in plans:
            keys = [str(item["artifact_key"]) for item in plan.get("artifacts", []) if item.get("artifact_key")]
            artifacts = _artifacts(conn, keys)
            facts = _fact_count(conn, plan["dataset"], [str(row["artifact_id"]) for row in artifacts])
            status, issues = classify_plan(plan, artifacts, facts)
            groups[plan["dataset"]].append({"path": str(path), "state": plan.get("state"), "scope": plan.get("canonical_load_scope"), "artifacts": artifacts, "canonical_rows": facts, "status": status, "issues": issues})
    families = []
    for dataset_id, meta in FAMILIES.items():
        entries = groups[dataset_id]
        status = "unknown" if not entries else "failed" if any(item["status"] == "failed" for item in entries) else "attention" if any(item["status"] == "attention" for item in entries) else "healthy"
        families.append({"dataset_id": dataset_id, "name": meta["name"], "catalog_packages": packages.get(dataset_id, 0), "status": status, "plans": entries})
    result = {"schema": 1, "generated_at": datetime.now(timezone.utc).isoformat(), "families": families}
    result["status"] = "failed" if any(row["status"] == "failed" for row in families) else "attention" if any(row["status"] in {"attention", "unknown"} for row in families) else "healthy"
    target = Path(settings.data_root).expanduser().resolve().parent / "meta" / "health" / "census.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, indent=2, sort_keys=True, default=str) + "\n")
    result["report"] = str(target)
    return result
