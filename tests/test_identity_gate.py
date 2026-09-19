"""Story 3.2: politician-join sources are gated, and the gate is enforced."""

from __future__ import annotations

import copy

import pytest

from opendiscourse_research.catalog import load_inventory, validate_inventory
from opendiscourse_research.identitygate import (
    PERSON_JOIN_DATASETS,
    PersonJoinBlocked,
    person_join,
    require_person_join,
    validate_person_joins,
)


def _inventory(**gate: object) -> dict:
    """Real inventory with the FEC gate overridden."""
    inventory = copy.deepcopy(load_inventory())
    for provider in inventory["providers"]:
        for dataset in provider["datasets"]:
            if dataset["id"] == "fec.campaign_finance":
                dataset["person_join"] = {**dataset["person_join"], **gate}
    return inventory


def test_shipped_inventory_validates() -> None:
    assert validate_inventory() == []


@pytest.mark.parametrize("dataset_id", PERSON_JOIN_DATASETS)
def test_every_politician_source_is_blocked_with_reasons(dataset_id: str) -> None:
    gate = person_join(dataset_id)
    assert gate["state"] == "blocked" and gate["key"] == "bioguide"
    assert gate["blocked_by"], "a blocked gate must say what unblocks it"
    with pytest.raises(PersonJoinBlocked, match="blocked by"):
        require_person_join(dataset_id)


def test_fec_names_the_identifier_it_would_join_on() -> None:
    assert person_join("fec.campaign_finance")["via"] == "fec"


def test_undeclared_dataset_cannot_pass_the_runtime_gate() -> None:
    with pytest.raises(PersonJoinBlocked, match="declares no person_join"):
        require_person_join("census.acs_5")


def test_dropping_a_required_gate_is_an_error() -> None:
    inventory = _inventory()
    for provider in inventory["providers"]:
        for dataset in provider["datasets"]:
            dataset.pop("person_join", None) if dataset["id"] == "disclosures.financial" else None
    assert "disclosures.financial: must declare person_join" in validate_person_joins(inventory, [])


@pytest.mark.parametrize(
    ("override", "fragment"),
    [
        ({"state": "maybe"}, "state must be one of"),
        ({"key": "full_name"}, "key must be bioguide"),
        ({"via": "full_name"}, "not a name"),
        ({"blocked_by": []}, "non-empty blocked_by"),
    ],
)
def test_malformed_gate_is_rejected(override: dict, fragment: str) -> None:
    errors = validate_person_joins(_inventory(**override), [])
    assert any(fragment in e for e in errors), errors


def test_ready_needs_via_and_an_approved_contract() -> None:
    pending = [{"id": "fecjoin", "dataset": "fec.campaign_finance", "target": "core.x", "approval": "pending_review"}]
    errors = validate_person_joins(_inventory(state="ready", contract="fecjoin"), pending)
    assert any("approved contract" in e for e in errors)
    no_via = validate_person_joins(_inventory(state="ready", via=None, contract="fecjoin"), [])
    assert any("requires via" in e for e in no_via)
    approved = [{**pending[0], "approval": "approved"}]
    assert validate_person_joins(_inventory(state="ready", contract="fecjoin"), approved) == []


def test_ready_gate_passes_the_runtime_check() -> None:
    inventory = _inventory(state="ready", contract="fecjoin")
    assert require_person_join("fec.campaign_finance", inventory)["via"] == "fec"


def test_enabled_contract_may_not_write_core_while_blocked() -> None:
    contracts = [
        {"id": "a", "dataset": "fec.campaign_finance", "target": "stage.fec_row", "enabled": True},
        {"id": "b", "dataset": "fec.campaign_finance", "target": "fact.contribution", "enabled": True},
        {"id": "c", "dataset": "fec.campaign_finance", "target": "core.person", "enabled": False},
    ]
    errors = validate_person_joins(_inventory(), contracts)
    assert len(errors) == 1 and "contract b writes fact.contribution" in errors[0]


def test_shipped_contracts_do_not_promote_blocked_sources() -> None:
    assert validate_person_joins() == []
