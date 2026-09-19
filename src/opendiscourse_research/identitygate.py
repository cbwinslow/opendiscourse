"""Gate for sources whose rows can only join to people through BioGuide (Story 3.2).

A dataset that carries politicians (FEC, disclosures, elections-as-member) declares
``person_join`` in ``inventory/sources.yaml``. It stays ``blocked`` until a reviewed,
approved contract says how its rows reach a BioGuide person through an identifier we
hold. Nothing here matches names: ``via`` is a ``core.person_identifier`` namespace.

Code that promotes person-keyed rows into ``core``/``fact`` must call
:func:`require_person_join` first; ``validate_person_joins`` runs in ``init-db``.
"""

from __future__ import annotations

from typing import Any

from .catalog import load_inventory
from .contracts import load_contracts

# Datasets that must declare a gate; dropping one silently is a validation error.
PERSON_JOIN_DATASETS = (
    "fec.campaign_finance",
    "disclosures.financial",
    "elections.results",
)
STATES = ("blocked", "ready")
NAME_LIKE = {"name", "names", "full_name", "display_name", "official_full", "label"}


class PersonJoinBlocked(RuntimeError):
    """Raised when code tries to join a source to people before its gate opens."""


def _datasets(inventory: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        dataset["id"]: dataset
        for provider in inventory["providers"]
        for dataset in provider["datasets"]
    }


def person_join(dataset_id: str, inventory: dict[str, Any] | None = None) -> dict[str, Any] | None:
    """Return the dataset's ``person_join`` gate, or None if it declares none."""
    dataset = _datasets(inventory or load_inventory()).get(dataset_id)
    return None if dataset is None else dataset.get("person_join")


def require_person_join(dataset_id: str, inventory: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return the open gate for ``dataset_id`` or raise with what still blocks it."""
    gate = person_join(dataset_id, inventory)
    if gate is None:
        raise PersonJoinBlocked(
            f"{dataset_id} declares no person_join gate; declare one in inventory/sources.yaml"
        )
    if gate.get("state") != "ready":
        raise PersonJoinBlocked(
            f"{dataset_id} person joins are blocked by: {', '.join(gate.get('blocked_by') or ['?'])}. "
            "Join through BioGuide identifiers only, never names."
        )
    return gate


def validate_person_joins(
    inventory: dict[str, Any] | None = None,
    contracts: list[dict[str, Any]] | None = None,
) -> list[str]:
    """Check the declared gates and that no blocked source promotes into core/fact."""
    inventory = inventory or load_inventory()
    contracts = load_contracts() if contracts is None else contracts
    datasets = _datasets(inventory)
    by_id = {c.get("id"): c for c in contracts}
    errors: list[str] = []
    for dataset_id in PERSON_JOIN_DATASETS:
        if dataset_id not in datasets:
            errors.append(f"{dataset_id}: dataset missing from inventory")
        elif "person_join" not in datasets[dataset_id]:
            errors.append(f"{dataset_id}: must declare person_join")
    for dataset_id, dataset in datasets.items():
        gate = dataset.get("person_join")
        if gate is None:
            continue
        label = f"{dataset_id}.person_join"
        if gate.get("state") not in STATES:
            errors.append(f"{label}: state must be one of {', '.join(STATES)}")
        if gate.get("key") != "bioguide":
            errors.append(f"{label}: key must be bioguide (federal people join on BioGuide)")
        via = gate.get("via")
        if via is not None and (not isinstance(via, str) or via.lower() in NAME_LIKE):
            errors.append(f"{label}: via must be a person_identifier namespace, not a name")
        if gate.get("state") == "blocked" and not gate.get("blocked_by"):
            errors.append(f"{label}: blocked requires a non-empty blocked_by list")
        if gate.get("state") == "ready":
            contract = by_id.get(gate.get("contract"))
            if not via:
                errors.append(f"{label}: ready requires via (the identifier namespace)")
            if contract is None or contract.get("approval") != "approved":
                errors.append(f"{label}: ready requires an approved contract")
        if gate.get("state") != "ready":
            for contract in contracts:
                target = str(contract.get("target", ""))
                if (
                    contract.get("dataset") == dataset_id
                    and contract.get("enabled")
                    and not target.startswith("stage.")
                ):
                    errors.append(
                        f"{label}: enabled contract {contract.get('id')} writes {target} "
                        "while person joins are blocked"
                    )
    return errors


def status(inventory: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Report each gate with how many people carry its ``via`` identifier (read-only)."""
    from sqlalchemy import distinct, func, select
    from sqlalchemy.exc import SQLAlchemyError

    from .db import session
    from .models.core import person_identifier_table

    identifier = person_identifier_table()
    rows: list[dict[str, Any]] = []
    inventory = inventory or load_inventory()
    for dataset_id in PERSON_JOIN_DATASETS:
        gate = person_join(dataset_id, inventory) or {}
        row = {"dataset": dataset_id, **{k: gate.get(k) for k in ("state", "via", "blocked_by")}}
        namespace = gate.get("via")
        try:
            with session() as active:
                row["people_with_via"] = (
                    active.scalar(
                        select(func.count(distinct(identifier.c.person_id))).where(
                            identifier.c.namespace == namespace
                        )
                    )
                    if namespace
                    else None
                )
        except SQLAlchemyError:
            row["people_with_via"] = None  # database unreachable: gate state still reported
        rows.append(row)
    return rows
