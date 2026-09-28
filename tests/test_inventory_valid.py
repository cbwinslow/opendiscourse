"""The version-controlled inventory must always load and validate.

``init-db`` and ``progress-list`` read these files at runtime, so an edit that is not valid
YAML (for example a stray ``: `` in a plain scalar) would only surface when someone runs them.
"""

from __future__ import annotations

from opendiscourse_research.catalog import validate_inventory
from opendiscourse_research.contracts import validate_contracts
from opendiscourse_research.progress import validate_progress


def test_inventory_progress_and_contracts_validate() -> None:
    assert validate_inventory() + validate_progress() + validate_contracts() == []


def test_archive_contract_requires_lifecycle_and_endpoint_policy(monkeypatch, tmp_path) -> None:
    from opendiscourse_research import contracts

    (tmp_path / "archive.yaml").write_text(
        "contracts:\n"
        "  - id: archive\n"
        "    provider: census\n"
        "    dataset: census.acs_housing_archive\n"
        "    kind: archive_manifest\n"
        "    cadence: annual\n"
        "    target: [stage.acs_pums_record]\n"
        "    products: [acs_pums_1]\n"
        "    selection: {years: 2024}\n"
        "    storage: {capacity_rule: fail_closed}\n"
        "    approval: required\n"
    )
    monkeypatch.setattr(contracts, "CONTRACT_ROOT", tmp_path)
    errors = contracts.validate_contracts()
    assert any("endpoint_policy" in error for error in errors)
    assert any("lifecycle_state" in error for error in errors)
