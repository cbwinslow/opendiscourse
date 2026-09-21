"""Story 11.3: every element path of every BILLS file on this machine is captured.

Skips on a machine that has not run ``research-db sync-bill-text``. Run it with
``uv run pytest -m slow tests/test_bill_text_record_corpus.py``.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from opendiscourse_research.config import settings
from opendiscourse_research.ingestion.bill_text_parse import parse_bills_xml, parse_xml_without_dtd
from opendiscourse_research.ingestion.billstatus_record import record_problems
from opendiscourse_research.providers.govinfo import bills_member_identity

pytestmark = [pytest.mark.slow, pytest.mark.timeout(3600)]


def _zips() -> list[Path]:
    root = Path(settings.data_root)
    return sorted(root.rglob("BILLS-*-*.zip")) if root.is_dir() else []


@pytest.fixture(scope="module")
def zips() -> list[Path]:
    found = _zips()
    if not found:
        pytest.skip(f"no BILLS zips under DATA_ROOT ({settings.data_root}); run sync-bill-text")
    return found


def test_every_path_and_value_of_every_member_is_in_its_record(zips: list[Path]) -> None:
    members = 0
    failures: list[str] = []
    for path in zips:
        with zipfile.ZipFile(path) as bundle:
            for name in bundle.namelist():
                if not name.endswith(".xml") or bills_member_identity(name) is None:
                    continue
                members += 1
                content = bundle.read(name)
                try:
                    parsed = parse_bills_xml(content, name)
                    problems = record_problems(parse_xml_without_dtd(content), parsed.record)
                except Exception as exc:
                    problems = [f"unreadable: {exc}"]
                failures += [f"{path.name}:{name}: {p}" for p in problems[:3]]
                if len(failures) > 20:
                    break
        if len(failures) > 20:
            break
    assert members, "the zips held no BILLS XML members"
    assert not failures, f"{len(failures)}+ problems, first: {failures[:5]}"
