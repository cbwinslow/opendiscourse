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


def congressional_health() -> dict[str, Any]:
    """Return and persist one source-aware congressional ingestion health report."""
    with connect() as conn, conn.cursor() as cur:
        cur.execute(_query("congress_health"))
        health = cur.fetchone()["health"]
    result: dict[str, Any] = {
        "schema": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "coverage": {"118": "complete", "119": "partial"},
        "canonical": health,
        "vote_reconciliation": {"118": reconcile_openstates_votes(118), "119": reconcile_openstates_votes(119)},
    }
    result["stale_runs"] = [
        run for run in health["latest_runs"] if run["status"] == "running"
    ]
    result["failed_runs"] = [
        run for run in health["latest_runs"] if run["status"] == "failed"
    ]
    result["status"] = (
        "failed"
        if result["failed_runs"]
        else "attention"
        if result["stale_runs"]
        else "healthy"
    )
    target = Path(settings.data_root).expanduser().resolve().parent / "meta" / "health" / "congressional.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, indent=2, sort_keys=True, default=str) + "\n")
    result["report"] = str(target)
    return result
