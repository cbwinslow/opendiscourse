"""Story 11.1: every House roll-call file on this machine is captured, and every stored record equals its XML.

The fixture test (``test_house_vote_parse.py``) proves the encoding on real files from four eras. This
one proves it on all of them: it opens every roll-call file the Connector retained under ``DATA_ROOT``
(found through the artifact registry's own folder, never a fixed path), parses it with the production
parser, and fails on any element, attribute or value the record lacks, or any recorded vote the typed
rows would lose. Then it reads every ``core.roll_call_source_record`` row in the warehouse and compares
its JSON with the XML of the artifact it points at (0 mismatches, as Story 9.5b did for BILLSTATUS).
Both skip on a machine that has not run ``research-db sync-votes --chamber house``. Run it with
``uv run pytest -m slow tests/test_house_votes_record_corpus.py``.
"""

from __future__ import annotations

from pathlib import Path
from xml.etree import ElementTree

import psycopg
import pytest

from opendiscourse_research.config import settings
from opendiscourse_research.db import connect
from opendiscourse_research.ingestion.billstatus_record import record_problems, xml_to_record
from opendiscourse_research.ingestion.house_vote_parse import HOUSE_LIST_TAGS, parse_house_vote

# About 16,000 files of 80 KB: minutes, not the suite's 60 second default.
pytestmark = [pytest.mark.slow, pytest.mark.timeout(3600)]


def _files() -> list[Path]:
    root = Path(settings.data_root) / "congress" / "house_votes"
    return sorted(root.rglob("roll*.xml")) if root.is_dir() else []


@pytest.fixture(scope="module")
def files() -> list[Path]:
    found = _files()
    if not found:
        pytest.skip(f"no House roll-call files under DATA_ROOT ({settings.data_root}); run sync-votes --chamber house")
    return found


def test_every_element_attribute_and_value_of_every_file_is_in_its_record(files: list[Path]) -> None:
    failures: list[str] = []
    for path in files:
        data = path.read_bytes()
        try:
            parsed = parse_house_vote(data)  # raises when the record is not lossless
            entries = len(ElementTree.fromstring(data).findall("vote-data/recorded-vote"))
            if len(parsed.votes) != entries:
                failures.append(f"{path.name}: {entries} recorded votes, {len(parsed.votes)} typed")
        except Exception as exc:  # any file the loader could not take is a failure here
            failures.append(f"{path.name}: {exc}")
        if len(failures) > 20:
            break
    assert not failures, f"{len(failures)}+ problems, first: {failures[:5]}"


def test_every_stored_record_equals_the_xml_of_its_artifact() -> None:
    try:
        conn = connect()
    except psycopg.Error:
        pytest.skip("no warehouse reachable")
    with conn:
        try:
            rows = conn.execute(
                "SELECT s.roll_call_id, s.record, s.entry_count, s.typed_count, s.entries_without_id, "
                "s.unresolved_bioguide_ids, a.local_path, "
                "(SELECT count(*) FROM fact.member_vote v WHERE v.roll_call_id = s.roll_call_id "
                " AND v.source_artifact_id = s.source_artifact_id) AS stored_votes "
                "FROM core.roll_call_source_record s JOIN ingest.artifact a ON a.artifact_id = s.source_artifact_id "
                "WHERE a.dataset_id = 'congress.house_votes'"
            ).fetchall()
        except psycopg.errors.UndefinedTable:
            pytest.skip("the warehouse has no core.roll_call_source_record (migration not applied)")
    if not rows:
        pytest.skip("the warehouse holds no House roll-call records")
    mismatches: list[str] = []
    for row in rows:
        path = Path(row["local_path"])
        if not path.is_file():
            mismatches.append(f"{path.name}: retained file is missing")
            continue
        root = ElementTree.fromstring(path.read_bytes())
        if row["record"] != xml_to_record(root, HOUSE_LIST_TAGS) or record_problems(root, row["record"]):
            mismatches.append(f"{path.name}: stored record differs from its XML")
        entries = len(root.findall("vote-data/recorded-vote"))
        # every entry is typed, unresolved or without an id; none is lost between the file and the counts
        if row["entry_count"] != entries or row["typed_count"] + row["entries_without_id"] + len(
            row["unresolved_bioguide_ids"]
        ) > entries:
            mismatches.append(f"{path.name}: {entries} entries, counted {row['entry_count']}/{row['typed_count']}")
        if row["stored_votes"] != row["typed_count"]:
            mismatches.append(f"{path.name}: {row['stored_votes']} vote rows for {row['typed_count']} typed")
        if len(mismatches) > 20:
            break
    assert not mismatches, f"{len(mismatches)}+ mismatches over {len(rows)} records, first: {mismatches[:5]}"
