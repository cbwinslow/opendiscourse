"""Guard: the suite never inherits the operator's real DATA_ROOT."""

from pathlib import Path

from opendiscourse_research.config import PROJECT_ROOT, settings


def test_tests_run_against_a_scratch_data_root() -> None:
    root = Path(settings.data_root).resolve()
    assert root.name == "raw"
    assert not root.is_relative_to(PROJECT_ROOT), "scratch root must not be inside the checkout"
    assert "workspace/data-lake" not in str(root), "must not be the operator's lake"
