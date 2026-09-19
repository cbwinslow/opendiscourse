"""Shared pytest markers and collection policy."""

from __future__ import annotations

from pathlib import Path

import pytest

_DB_FILES = {
    "test_persistence_foundation.py",
    "test_census_bulk_integration.py",
    "test_provenance_identity_contracts.py",
    "test_legislators_load.py",
    "test_run_ledger.py",
    "test_coverage_db.py",
    "test_billstatus_connector.py",
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
