"""Read-only operational health reporting for congressional ingestion."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import json
from typing import Any

from .config import settings
from .db import connect
from .repositories.legislation import _query
from .votereconcile import reconcile_openstates_votes


def billstatus_coverage(
    validation: dict[str, Any] | None,
    reconciliation: dict[str, Any] | None,
    latest_runs: list[dict[str, Any]],
) -> str:
    """Classify BILLSTATUS coverage from validation, reconciliation, and run evidence."""
    comparisons = [
        item
        for item in (validation or {}).get("official_comparison", [])
        if item.get("congress") == 119
    ]
    validated = bool(comparisons) and all(
        item.get("archive_matches_official") is True for item in comparisons
    )
    reconciled = (
        (reconciliation or {}).get("congress") == 119
        and (reconciliation or {}).get("summary", {}).get("canonical_bill_missing") == 0
        and not (reconciliation or {}).get("malformed")
    )
    loaded = any(
        run.get("dataset_id") == "congress.govinfo_billstatus"
        and run.get("status") == "succeeded"
        and run.get("parameters", {}).get("congress") == 119
        and run.get("parameters", {}).get("coverage") == "complete"
        for run in latest_runs
    )
    return "complete" if validated and reconciled and loaded else "partial"


def is_recovered_run(run: dict[str, Any]) -> bool:
    """Identify a failed run deliberately closed by stale-run recovery."""
    return str(run.get("error_message") or "").startswith(
        "Recovered by congressional health check:"
    )


def congressional_health() -> dict[str, Any]:
    """Return and persist one source-aware congressional ingestion health report."""
    with connect() as conn, conn.cursor() as cur:
        cur.execute(_query("congress_health"))
        health = cur.fetchone()["health"]
    meta_root = Path(settings.data_root).expanduser().resolve().parent / "meta"
    validation_path = meta_root / "validate" / "billstatus" / "latest.json"
    reconciliation_path = meta_root / "reconcile" / "billstatus" / "119.json"
    validation = json.loads(validation_path.read_text()) if validation_path.is_file() else None
    reconciliation = (
        json.loads(reconciliation_path.read_text()) if reconciliation_path.is_file() else None
    )
    result: dict[str, Any] = {
        "schema": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "coverage": {
            "bills": {
                "118": "complete",
                "119": billstatus_coverage(validation, reconciliation, health["latest_runs"]),
            },
            "people": {"federal": "complete" if health["unresolved_sponsorships"] == 0 else "partial"},
            "organizations": {"federal": "complete"},
            "votes": {"118": "complete", "119": "partial"},
        },
        "canonical": health,
        "vote_reconciliation": {"118": reconcile_openstates_votes(118), "119": reconcile_openstates_votes(119)},
    }
    result["stale_runs"] = [
        run for run in health["latest_runs"] if run["status"] == "running"
    ]
    failed_runs = [run for run in health["latest_runs"] if run["status"] == "failed"]
    result["recovered_runs"] = [run for run in failed_runs if is_recovered_run(run)]
    result["failed_runs"] = [
        run for run in failed_runs if not is_recovered_run(run)
    ]
    result["status"] = (
        "failed"
        if result["failed_runs"]
        else "attention"
        if result["stale_runs"] or result["recovered_runs"]
        else "healthy"
    )
    target = meta_root / "health" / "congressional.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, indent=2, sort_keys=True, default=str) + "\n")
    result["report"] = str(target)
    return result


def recover_stale_congressional_runs(older_than: str = "6 hours") -> list[dict[str, Any]]:
    """Mark long-abandoned congressional runs failed with explicit recovery evidence."""
    with connect() as conn, conn.cursor() as cur:
        cur.execute(_query("fail_stale_runs"), {"older_than": older_than})
        rows = [dict(row) for row in cur.fetchall()]
        conn.commit()
    return rows
