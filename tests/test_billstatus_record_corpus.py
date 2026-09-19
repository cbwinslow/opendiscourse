"""Story 9.5b: every element path of every BILLSTATUS file on this machine is captured.

The fixture test (``test_billstatus_record.py``) proves the encoding on 14 real files. This one
proves it on all of them: it opens every BILLSTATUS zip under ``DATA_ROOT`` (the project's
own download folder, never a fixed path), parses each member with the production parser, and
fails on any XML path or value the record lacks, or any promoted section that lost a row.
It skips on a machine that has not run ``research-db sync-billstatus``. Run it with
``uv run pytest -m slow tests/test_billstatus_record_corpus.py``.
"""

from __future__ import annotations

import zipfile
from pathlib import Path
from xml.etree import ElementTree

import pytest

from opendiscourse_research.config import settings
from opendiscourse_research.ingestion.billstatus_record import record_problems
from opendiscourse_research.repositories.legislation import parse_billstatus_xml

# The whole corpus is 2.8 GB of XML: minutes, not the suite's 60 second default.
pytestmark = [pytest.mark.slow, pytest.mark.timeout(3600)]

# section -> XML paths whose element count each promoted row must match
_PROMOTED = {
    "laws": ("./laws/item",),
    "related_bills": ("./relatedBills/item",),
    "amendments": ("./amendments/amendment",),
}


def _zips() -> list[Path]:
    root = Path(settings.data_root)
    return sorted(root.rglob("BILLSTATUS-*.zip")) if root.is_dir() else []


@pytest.fixture(scope="module")
def zips() -> list[Path]:
    found = _zips()
    if not found:
        pytest.skip(f"no BILLSTATUS zips under DATA_ROOT ({settings.data_root}); run sync-billstatus")
    return found


def test_every_path_and_value_of_every_member_is_in_its_record(zips: list[Path]) -> None:
    members = 0
    failures: list[str] = []
    for path in zips:
        with zipfile.ZipFile(path) as bundle:
            for name in bundle.namelist():
                if not name.endswith(".xml"):
                    continue
                members += 1
                content = bundle.read(name)
                try:
                    record = parse_billstatus_xml(content, member_name=name)["record"]
                    problems = record_problems(ElementTree.fromstring(content), record)
                except Exception as exc:  # any member the loader could not take is a failure here
                    problems = [f"unreadable: {exc}"]
                failures += [f"{path.name}:{name}: {p}" for p in problems[:3]]
                if len(failures) > 20:
                    break
        if len(failures) > 20:
            break
    assert members, "the zips held no XML members"
    assert not failures, f"{len(failures)}+ problems, first: {failures[:5]}"


def test_no_promoted_section_silently_drops_a_row(zips: list[Path]) -> None:
    mismatches: list[str] = []
    for path in zips:
        with zipfile.ZipFile(path) as bundle:
            for name in bundle.namelist():
                if not name.endswith(".xml"):
                    continue
                content = bundle.read(name)
                data = parse_billstatus_xml(content, member_name=name)
                bill = ElementTree.fromstring(content).find("bill")
                assert bill is not None
                for section, xpaths in _PROMOTED.items():
                    expected = sum(len(bill.findall(x)) for x in xpaths)
                    if len(data[section]) != expected:
                        mismatches.append(f"{name}: {section} {len(data[section])} of {expected}")
                summaries = len(bill.findall("./summaries/summary")) or len(
                    bill.findall("./summaries/billSummaries/item")
                )
                if len(data["summaries"]) != summaries:
                    mismatches.append(f"{name}: summaries {len(data['summaries'])} of {summaries}")
                if len(mismatches) > 20:
                    break
        if len(mismatches) > 20:
            break
    assert not mismatches, f"{len(mismatches)}+ mismatches, first: {mismatches[:5]}"
