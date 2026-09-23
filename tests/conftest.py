"""Shared pytest markers and collection policy."""

from __future__ import annotations

from pathlib import Path

import pytest

from opendiscourse_research.config import settings

_DB_FILES = {
    "test_persistence_foundation.py",
    "test_census_bulk_integration.py",
    "test_provenance_identity_contracts.py",
    "test_legislators_load.py",
    "test_run_ledger.py",
    "test_coverage_db.py",
    "test_billstatus_connector.py",
    "test_bill_text_connector.py",
    "test_committee_membership_connector.py",
    "test_voteview_connector.py",
    "test_house_votes_connector.py",
    "test_senate_votes_connector.py",
}


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Mark known database integration modules without rewriting every test."""
    db_marker = pytest.mark.db
    integration_marker = pytest.mark.integration
    for item in items:
        path = Path(getattr(item, "path", item.fspath))
        if path.name in _DB_FILES:
            item.add_marker(db_marker)
            item.add_marker(integration_marker)


@pytest.fixture(autouse=True)
def _isolated_data_root(tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch) -> None:
    """Point DATA_ROOT at a scratch folder so no test writes into the operator's real lake.

    Tests that download or retain artifacts used to inherit ``.env``'s DATA_ROOT and left
    dozens of tiny fixture files (and unregistered ``.zip`` stubs) beside real evidence.
    A test that needs a specific root still sets its own with ``monkeypatch``; module- or
    session-scoped fixtures run before this one and may read the real root read-only.
    """
    monkeypatch.setattr(settings, "data_root", str(tmp_path_factory.mktemp("lake") / "raw"))
