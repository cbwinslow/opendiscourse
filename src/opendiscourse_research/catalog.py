from __future__ import annotations

from pathlib import Path
import yaml
from psycopg.types.json import Jsonb

from .db import connect
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
            required = ("id", "title", "access", "client", "grain", "identifiers", "cadence")
            missing = [key for key in required if not dataset.get(key)]
            if missing:
                errors.append(f"{dataset_id or '<unknown>'}: missing {', '.join(missing)}")
            if dataset_id in ids:
                errors.append(f"duplicate dataset id: {dataset_id}")
            ids.add(dataset_id)
    return errors + validate_plans()


def sync_inventory() -> None:
    inventory = load_inventory()
    with connect() as conn, conn.cursor() as cur:
        for provider in inventory["providers"]:
            cur.execute(
                """INSERT INTO catalog.provider (provider_id, name, base_url)
                   VALUES (%s, %s, %s)
                   ON CONFLICT (provider_id) DO UPDATE SET name = EXCLUDED.name, base_url = EXCLUDED.base_url""",
                (provider["id"], provider["name"], provider.get("base_url")),
            )
            for dataset in provider["datasets"]:
                metadata = {k: v for k, v in dataset.items() if k not in {"id", "title", "access", "grain", "cadence", "priority"}}
                cur.execute(
                    """INSERT INTO catalog.dataset
                       (dataset_id, provider_id, title, access_method, grain_description, refresh_cadence, priority, metadata)
                       VALUES (%(id)s, %(provider_id)s, %(title)s, %(access)s, %(grain)s, %(cadence)s, %(priority)s, %(metadata)s)
                       ON CONFLICT (dataset_id) DO UPDATE SET
                         title = EXCLUDED.title, access_method = EXCLUDED.access_method,
                         grain_description = EXCLUDED.grain_description, refresh_cadence = EXCLUDED.refresh_cadence,
                         priority = EXCLUDED.priority, metadata = EXCLUDED.metadata, updated_at = now()""",
                    {**dataset, "provider_id": provider["id"], "priority": dataset.get("priority"), "metadata": Jsonb(metadata)},
                )
        conn.commit()
    sync_plans()
