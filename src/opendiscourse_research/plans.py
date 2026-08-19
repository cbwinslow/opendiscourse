"""Version-controlled ingestion contracts and their safe local runner."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert

from .db import session
from .ingestion.bls import ingest_manifest as ingest_bls_manifest
from .ingestion.census import bootstrap_housing
from .ingestion.congress import ingest_bills
from .ingestion.fred import ingest_manifest
from .models.catalog import Plan
from .models.ingest import cursor_table

ROOT = Path(__file__).resolve().parents[2]
HANDLERS = {
    "fred_core",
    "acs_housing",
    "congress_bills",
    "census_metadata",
    "bls_core",
}


def load_plans() -> list[dict[str, Any]]:
    return yaml.safe_load((ROOT / "inventory" / "plans.yaml").read_text()).get(
        "plans", []
    )


def validate_plans() -> list[str]:
    errors: list[str] = []
    seen: set[str] = set()
    for plan in load_plans():
        plan_id = plan.get("id", "<unknown>")
        missing = [
            key
            for key in ("id", "dataset", "handler", "cadence", "parameters")
            if key not in plan
        ]
        if missing:
            errors.append(f"{plan_id}: missing {', '.join(missing)}")
        if plan_id in seen:
            errors.append(f"duplicate plan id: {plan_id}")
        seen.add(plan_id)
        if (
            not isinstance(plan_id, str)
            or not plan_id.isalnum()
            or plan_id != plan_id.lower()
        ):
            errors.append(f"{plan_id}: id must be one lower-case alphanumeric word")
        if plan.get("handler") not in HANDLERS:
            errors.append(f"{plan_id}: unknown handler {plan.get('handler')!r}")
        if not isinstance(plan.get("parameters"), dict):
            errors.append(f"{plan_id}: parameters must be a mapping")
    return errors


def sync_plans() -> None:
    """Upsert reviewed ingestion plans into the catalog."""
    table = Plan.__table__
    with session() as active_session:
        for plan in load_plans():
            statement = insert(table).values(
                plan_id=plan["id"],
                dataset_id=plan["dataset"],
                handler=plan["handler"],
                cadence=plan["cadence"],
                enabled=plan.get("enabled", True),
                parameters=plan["parameters"],
                metadata={"notes": plan.get("notes")},
            )
            active_session.execute(
                statement.on_conflict_do_update(
                    index_elements=(table.c.plan_id,),
                    set_={
                        "dataset_id": statement.excluded.dataset_id,
                        "handler": statement.excluded.handler,
                        "cadence": statement.excluded.cadence,
                        "enabled": statement.excluded.enabled,
                        "parameters": statement.excluded.parameters,
                        "metadata": statement.excluded.metadata,
                        "updated_at": func.now(),
                    },
                )
            )


def run_plan(plan_id: str) -> int:
    plans = {plan["id"]: plan for plan in load_plans()}
    if plan_id not in plans:
        raise ValueError(
            f"Unknown plan {plan_id!r}; use plan-list to see available plans"
        )
    plan = plans[plan_id]
    if not plan.get("enabled", True):
        raise ValueError(f"Plan {plan_id!r} is disabled")
    # Keep the catalog foreign-key allow-list aligned with the reviewed file
    # before recording an execution cursor for a newly introduced plan.
    sync_plans()
    args = plan["parameters"]
    failures: dict[str, str] = {}
    if plan["handler"] == "fred_core":
        successes, failures = ingest_manifest(priority=args.get("max_priority", 1))
        count = sum(successes.values())
    elif plan["handler"] == "acs_housing":
        count = bootstrap_housing(
            args["year"], [str(state).zfill(2) for state in args["states"]]
        )
    elif plan["handler"] == "congress_bills":
        count = ingest_bills(
            args["congress"], args.get("max_records", 250), mode="incremental"
        )
    elif plan["handler"] == "census_metadata":
        from .registry import sync as registry_sync

        result = registry_sync(sources={"census"})
        count = sum(
            value
            for value in result["results"]["census"].values()
            if isinstance(value, int)
        )
    elif plan["handler"] == "bls_core":
        successes, failures = ingest_bls_manifest(priority=args.get("max_priority", 1))
        count = sum(successes.values())
    else:
        raise AssertionError(f"Handler validation missed {plan['handler']!r}")
    table = cursor_table()
    statement = insert(table).values(
        plan_id=plan_id,
        cursor={
            "last_count": count,
            "completed_at": datetime.now(UTC).isoformat(),
            "failures": failures or None,
        },
    )
    with session() as active_session:
        active_session.execute(
            statement.on_conflict_do_update(
                index_elements=(table.c.plan_id,),
                set_={"cursor": statement.excluded.cursor, "updated_at": func.now()},
            )
        )
    if failures:
        # The cursor above still records this run so a scheduled retry
        # doesn't immediately repeat the series that already succeeded;
        # surface the partial failure clearly rather than reporting a
        # silent full success.
        raise ValueError(
            f"Plan {plan_id!r} completed with {len(failures)} failed series: "
            + ", ".join(f"{k} ({v})" for k, v in failures.items())
        )
    return count


def due_plans(now: datetime | None = None) -> list[dict[str, Any]]:
    """Return enabled contracts whose configured cadence has elapsed."""
    now = now or datetime.now(UTC)
    intervals = {
        "daily": timedelta(days=1),
        "weekly": timedelta(days=7),
        "monthly": timedelta(days=31),
        "annual": timedelta(days=365),
    }
    table = cursor_table()
    with session() as active_session:
        completed = {
            row["plan_id"]: row["updated_at"]
            for row in active_session.execute(
                select(table.c.plan_id, table.c.updated_at)
            ).mappings()
        }
    return [
        plan
        for plan in load_plans()
        if plan.get("enabled", True)
        and (
            plan["id"] not in completed
            or now - completed[plan["id"]] >= intervals[plan["cadence"]]
        )
    ]
