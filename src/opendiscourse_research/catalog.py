from __future__ import annotations

from pathlib import Path

import yaml
from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert

from .db import session
from .models.catalog import Dataset, Provider
from .plans import sync_plans, validate_plans

ROOT = Path(__file__).resolve().parents[2]


def load_inventory() -> dict:
    with (ROOT / "inventory" / "sources.yaml").open() as f:
        return yaml.safe_load(f)


def validate_inventory() -> list[str]:
    inventory = load_inventory()
    errors: list[str] = []
    ids: set[str] = set()
    for provider in inventory.get("providers", []):
        if not provider.get("id") or not provider.get("name"):
            errors.append("provider requires id and name")
        for dataset in provider.get("datasets", []):
            dataset_id = dataset.get("id")
            required = (
                "id",
                "title",
                "access",
                "client",
                "grain",
                "identifiers",
                "cadence",
            )
            missing = [key for key in required if not dataset.get(key)]
            if missing:
                errors.append(
                    f"{dataset_id or '<unknown>'}: missing {', '.join(missing)}"
                )
            if dataset_id in ids:
                errors.append(f"duplicate dataset id: {dataset_id}")
            ids.add(dataset_id)
    return errors + validate_plans()


def sync_inventory() -> None:
    """Upsert the reviewed provider and dataset inventory before syncing plans."""
    inventory = load_inventory()
    provider_table = Provider.__table__
    dataset_table = Dataset.__table__
    with session() as active_session:
        for provider in inventory["providers"]:
            provider_statement = insert(provider_table).values(
                provider_id=provider["id"],
                name=provider["name"],
                base_url=provider.get("base_url"),
            )
            active_session.execute(
                provider_statement.on_conflict_do_update(
                    index_elements=(provider_table.c.provider_id,),
                    set_={
                        "name": provider_statement.excluded.name,
                        "base_url": provider_statement.excluded.base_url,
                    },
                )
            )
            for dataset in provider["datasets"]:
                metadata = {
                    k: v
                    for k, v in dataset.items()
                    if k
                    not in {"id", "title", "access", "grain", "cadence", "priority"}
                }
                dataset_statement = insert(dataset_table).values(
                    dataset_id=dataset["id"],
                    provider_id=provider["id"],
                    title=dataset["title"],
                    access_method=dataset["access"],
                    grain_description=dataset["grain"],
                    refresh_cadence=dataset["cadence"],
                    priority=dataset.get("priority"),
                    metadata=metadata,
                )
                active_session.execute(
                    dataset_statement.on_conflict_do_update(
                        index_elements=(dataset_table.c.dataset_id,),
                        set_={
                            "title": dataset_statement.excluded.title,
                            "access_method": dataset_statement.excluded.access_method,
                            "grain_description": dataset_statement.excluded.grain_description,
                            "refresh_cadence": dataset_statement.excluded.refresh_cadence,
                            "priority": dataset_statement.excluded.priority,
                            "metadata": dataset_statement.excluded.metadata,
                            "updated_at": func.now(),
                        },
                    )
                )
    sync_plans()
