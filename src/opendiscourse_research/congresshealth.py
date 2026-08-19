"""Read-only operational health reporting for congressional ingestion."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import exists, func, select, text, update

from .config import settings
from .db import session
from .models.core import (
    bill_sponsorship_table,
    bill_table,
    member_vote_table,
    organization_table,
    person_identifier_table,
    person_table,
    roll_call_table,
)
from .models.ingest import identity_exception_table, run_table
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


def has_identity_attention(health: dict[str, Any]) -> bool:
    """Return whether unresolved identity evidence requires operator review."""
    return bool(
        health.get("unresolved_sponsorships") or health.get("unresolved_voters")
    )


def congressional_health() -> dict[str, Any]:
    """Return and persist one source-aware congressional ingestion health report."""
    health = _congressional_health_evidence()
    meta_root = Path(settings.data_root).expanduser().resolve().parent / "meta"
    validation_path = meta_root / "validate" / "billstatus" / "latest.json"
    reconciliation_path = meta_root / "reconcile" / "billstatus" / "119.json"
    validation = (
        json.loads(validation_path.read_text()) if validation_path.is_file() else None
    )
    reconciliation = (
        json.loads(reconciliation_path.read_text())
        if reconciliation_path.is_file()
        else None
    )
    result: dict[str, Any] = {
        "schema": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "coverage": {
            "bills": {
                "118": "complete",
                "119": billstatus_coverage(
                    validation, reconciliation, health["latest_runs"]
                ),
            },
            "people": {
                "federal": "complete"
                if health["unresolved_sponsorships"] == 0
                else "partial"
            },
            "organizations": {"federal": "complete"},
            "votes": {"118": "complete", "119": "partial"},
        },
        "canonical": health,
        "vote_reconciliation": {
            "118": reconcile_openstates_votes(118),
            "119": reconcile_openstates_votes(119),
        },
    }
    result["stale_runs"] = [
        run for run in health["latest_runs"] if run["status"] == "running"
    ]
    failed_runs = [run for run in health["latest_runs"] if run["status"] == "failed"]
    result["recovered_runs"] = [run for run in failed_runs if is_recovered_run(run)]
    result["failed_runs"] = [run for run in failed_runs if not is_recovered_run(run)]
    result["identity_exceptions"] = {
        "unresolved_sponsorships": health["unresolved_sponsorships"],
        "unresolved_voters": health["unresolved_voters"],
    }
    result["status"] = (
        "failed"
        if result["failed_runs"]
        else "attention"
        if result["stale_runs"]
        or result["recovered_runs"]
        or has_identity_attention(health)
        else "healthy"
    )
    target = meta_root / "health" / "congressional.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, indent=2, sort_keys=True, default=str) + "\n")
    result["report"] = str(target)
    return result


def _congressional_health_evidence() -> dict[str, Any]:
    """Read canonical congressional coverage and unresolved evidence via typed mappings."""
    bill = bill_table()
    person = person_table()
    organization = organization_table()
    roll_call = roll_call_table()
    member_vote = member_vote_table()
    sponsorship = bill_sponsorship_table()
    person_identifier = person_identifier_table()
    identity_exception = identity_exception_table()
    run = run_table()
    unresolved_voters = select(func.coalesce(func.sum(identity_exception.c.reference_count), 0)).where(
        ~exists(
            select(person_identifier.c.person_id).where(
                person_identifier.c.namespace == identity_exception.c.namespace,
                person_identifier.c.external_id == identity_exception.c.external_id,
            )
        )
    )
    latest_runs = (
        select(
            run.c.dataset_id,
            run.c.status,
            run.c.started_at,
            run.c.finished_at,
            run.c.record_count,
            run.c.error_message,
            run.c.parameters,
        )
        .where(run.c.dataset_id.in_(("congress.govinfo_billstatus", "openstates.legislation")))
        .order_by(run.c.started_at.desc())
        .limit(10)
    )
    with session() as active_session:
        def count(statement: Any) -> int:
            return int(active_session.execute(statement).scalar_one())

        return {
            "bills_118": count(select(func.count()).select_from(bill).where(bill.c.legislative_session == "118")),
            "bills_119": count(select(func.count()).select_from(bill).where(bill.c.legislative_session == "119")),
            "people": count(select(func.count()).select_from(person)),
            "organizations": count(select(func.count()).select_from(organization)),
            "roll_calls_118": count(select(func.count()).select_from(roll_call).where(roll_call.c.legislative_session == "118")),
            "roll_calls_119": count(select(func.count()).select_from(roll_call).where(roll_call.c.legislative_session == "119")),
            "member_votes_118": count(
                select(func.count())
                .select_from(member_vote.join(roll_call, member_vote.c.roll_call_id == roll_call.c.roll_call_id))
                .where(roll_call.c.legislative_session == "118")
            ),
            "member_votes_119": count(
                select(func.count())
                .select_from(member_vote.join(roll_call, member_vote.c.roll_call_id == roll_call.c.roll_call_id))
                .where(roll_call.c.legislative_session == "119")
            ),
            "unresolved_sponsorships": count(
                select(func.count()).select_from(sponsorship).where(sponsorship.c.person_id.is_(None))
            ),
            "unresolved_voters": int(active_session.execute(unresolved_voters).scalar_one()),
            "latest_runs": [dict(row) for row in active_session.execute(latest_runs).mappings()],
        }


def recover_stale_congressional_runs(
    older_than: str = "6 hours",
) -> list[dict[str, Any]]:
    """Mark long-abandoned congressional runs failed with explicit recovery evidence."""
    table = run_table()
    statement = (
        update(table)
        .where(
            table.c.status == "running",
            table.c.started_at < func.now() - text("CAST(:older_than AS interval)"),
            table.c.dataset_id.in_(("congress.govinfo_billstatus", "openstates.legislation")),
        )
        .values(
            status="failed",
            finished_at=func.now(),
            error_message="Recovered by congressional health check: run exceeded the stale-run threshold without completion.",
        )
        .returning(table.c.run_id, table.c.dataset_id, table.c.started_at)
    )
    with session() as active_session:
        return [
            dict(row)
            for row in active_session.execute(statement, {"older_than": older_than}).mappings()
        ]
