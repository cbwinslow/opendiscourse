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
