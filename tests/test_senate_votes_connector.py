"""Story 11.2 database contract: the Senate votes Connector, download -> inventory -> ingest.

A fake Senate serves small synthetic roll calls for Congress 997 (calendar years 3781 and 3782), a
Congress that does not exist, so nothing here can touch real rows. Every test starts and ends with
those rows removed: CI runs every DB module against one shared database. The tests below cover the
spec's I/O matrix row by row; the House suite (``test_house_votes_connector.py``) covers the shared
stages (retained-file damage, capacity gate, truncated lists) on the same base class.
"""

from __future__ import annotations

import hashlib
import os
import re
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import patch
from xml.etree import ElementTree

import httpx
import pytest
from alembic import command
from psycopg.types.json import Jsonb

from opendiscourse_research.catalog import sync_inventory
from opendiscourse_research.config import settings
from opendiscourse_research.db import (
    _alembic_config,
    _engine,
    apply_migrations,
    connect,
)
from opendiscourse_research.ingestion import bulk, roll_call_votes, senate_votes
from opendiscourse_research.ingestion.billstatus_record import xml_to_record
from opendiscourse_research.ingestion.bulk import ArtifactSpec, register_local
from opendiscourse_research.ingestion.connector import Connector, run_connector
from opendiscourse_research.ingestion.senate_vote_parse import (
    SENATE_LIST_TAGS,
    parse_senate_vote,
)
from opendiscourse_research.ingestion.senate_votes import (
    SenateVotesConnector,
    artifact_key,
    session_of,
)
from opendiscourse_research.providers.senate import (
    MenuEntry,
    SenateError,
    SenateNotFound,
    SenateRemoteRoll,
    vote_url,
)
from opendiscourse_research.repositories.legislation import register_artifact
from opendiscourse_research.repositories.votes import (
    SENATE_OCD_ORGANIZATION,
    senate_external_id,
)

CONGRESS = 997
YEAR = 3781  # 1789 + 2 * (997 - 1)
LATER_YEAR = YEAR + 1
MODIFIED = "Tue, 01 Sep 2020 12:06:52 GMT"
LATER = "Wed, 02 Sep 2020 12:06:52 GMT"
PEOPLE = {f"T997{n:03d}": f"Person {n}" for n in range(1, 6)}
OPENSTATES_KEY = "test-openstates-997"


# -- database ---------------------------------------------------------------
@pytest.fixture(scope="module")
def catalog_database() -> Iterator[None]:
    """Use CI's PostGIS service or a disposable local one, as the other DB contracts do."""
    original = settings.database_url
    external = os.environ.get("OPENDISCOURSE_TEST_DATABASE_URL")
    if external:
        settings.database_url = external
        container = None
    else:
        postgres = pytest.importorskip("testcontainers.postgres")
        container = postgres.PostgresContainer(
            "postgis/postgis:17-3.5", username="test", password="test", dbname="test"
        )
        container.start()
        settings.database_url = container.get_connection_url().replace(
            "postgresql+psycopg2://", "postgresql://", 1
        )
    try:
        apply_migrations()
        sync_inventory()
        yield
    finally:
        _remove_rows()
        settings.database_url = original
        _engine.cache_clear()
        if container is not None:
            container.stop()


_ROLLS = "(SELECT roll_call_id FROM core.roll_call WHERE jurisdiction = 'us' AND legislative_session = '997')"


def _remove_rows() -> None:
    """Delete everything Congress 997 and its test people created, children before parents."""
    with connect() as conn:
        for statement in (
            f"DELETE FROM fact.member_vote WHERE roll_call_id IN {_ROLLS}",
            f"DELETE FROM core.roll_call_party_total WHERE roll_call_id IN {_ROLLS}",
            f"DELETE FROM core.roll_call_source_record WHERE roll_call_id IN {_ROLLS}",
            "DELETE FROM core.roll_call WHERE jurisdiction = 'us' AND legislative_session = '997'",
            "DELETE FROM core.bill WHERE jurisdiction = 'us' AND legislative_session = '997'",
            (
                "WITH gone AS (DELETE FROM core.person_identifier WHERE namespace IN ('lis', 'bioguide') "
                "AND external_id LIKE 'T997%' RETURNING person_id) "
                "DELETE FROM core.person WHERE person_id IN (SELECT person_id FROM gone)"
            ),
            "DELETE FROM core.legislative_session WHERE identifier = '997'",
            "DELETE FROM ingest.raw_payload WHERE source_url = 'https://test-997'",
            "DELETE FROM ingest.run WHERE parameters @> '{\"test997\": true}'",
            "DELETE FROM core.organization_identifier WHERE metadata @> '{\"test997\": true}'",
            "DELETE FROM core.organization WHERE metadata @> '{\"test997\": true}'",
            (
                "DELETE FROM ingest.run_target WHERE run_id IN (SELECT run_id FROM ingest.run "
                "WHERE dataset_id = 'congress.senate_votes' AND parameters->'congresses' @> '[997]')"
            ),
            (
                "DELETE FROM ingest.run WHERE dataset_id = 'congress.senate_votes' "
                "AND parameters->'congresses' @> '[997]'"
            ),
            "DELETE FROM ingest.artifact WHERE dataset_id = 'congress.senate_votes' AND artifact_key LIKE 'senate-roll-378%'",
            f"DELETE FROM ingest.artifact WHERE artifact_key = '{OPENSTATES_KEY}'",
        ):
            conn.execute(statement)
        conn.commit()


@pytest.fixture(autouse=True)
def _clean(
    catalog_database: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[None]:
    monkeypatch.setattr(settings, "data_root", str(tmp_path / "lake" / "raw"))
    monkeypatch.setattr(senate_votes, "FIRST_CONGRESS", CONGRESS)
    monkeypatch.setattr(senate_votes, "LAST_CONGRESS", CONGRESS)
    _remove_rows()
    _add_people(PEOPLE)
    yield
    _remove_rows()


def _add_people(lis_ids: dict[str, str]) -> None:
    with connect() as conn:
        for lis, name in lis_ids.items():
            person = conn.execute(
                "INSERT INTO core.person (full_name) VALUES (%s) RETURNING person_id", (name,)
            ).fetchone()
            conn.execute(
                "INSERT INTO core.person_identifier (person_id, namespace, external_id) VALUES (%s, 'lis', %s)",
                (person["person_id"], lis),
            )
        conn.commit()


def _add_bill(bill_type: str, number: int, congress: int = CONGRESS) -> str:
    with connect() as conn:
        row = conn.execute(
            "INSERT INTO core.bill (jurisdiction, legislative_session, bill_type, bill_number) "
            "VALUES ('us', %s, %s, %s) RETURNING bill_id",
            (str(congress), bill_type, str(number)),
        ).fetchone()
        conn.commit()
    return str(row["bill_id"])


def _one(sql: str, *params: object):
    with connect() as conn:
        row = conn.execute(sql, params or None).fetchone()
    assert row is not None
    return next(iter(row.values()))


def _rows(sql: str, *params: object) -> list[tuple]:
    with connect() as conn:
        return [tuple(r.values()) for r in conn.execute(sql, params or None).fetchall()]


# -- synthetic origin ---------------------------------------------------------
Votes = list[tuple[str | None, str]]  # (LIS id or None, the word the Senate printed)
DEFAULT_VOTES: Votes = [
    ("T997001", "Yea"),
    ("T997002", "Nay"),
    ("T997003", "Yea"),
    ("T997004", "Not Voting"),
    ("T997005", "Present"),
]
_EMPTY_AMENDMENT = (
    "<amendment><amendment_number/><amendment_to_amendment_number/><amendment_to_document_number/>"
    "<amendment_to_document_short_title/><amendment_purpose>No Statement of Purpose on File.</amendment_purpose>"
    "</amendment>"
)


def _vote_xml(
    number: int,
    votes: Votes | None = None,
    *,
    year: int = YEAR,
    session: int = 1,
    question: str = "On the Motion",
    result: str = "Motion Agreed to",
    claims: int | None = None,
    document: str | None = None,
    amendment: str = _EMPTY_AMENDMENT,
    tie: tuple[str, str] = ("", ""),
    modify: bool = True,
    clock: str | None = None,
) -> str:
    votes = DEFAULT_VOTES if votes is None else votes
    yea = sum(w in {"Yea", "Guilty"} for _, w in votes)
    nay = sum(w in {"Nay", "Not Guilty"} for _, w in votes)
    present = sum(w == "Present" for _, w in votes)
    absent = sum(w == "Not Voting" for _, w in votes)

    def count(n: int) -> str:
        return f"{n}" if n else ""

    members = "".join(
        f"<member><member_full>Person {i} ({'D' if i % 2 else 'R'}-XX)</member_full><last_name>Person{i}</last_name>"
        f"<first_name>First{i}</first_name><party>{'D' if i % 2 else 'R'}</party><state>XX</state>"
        f"<vote_cast>{word}</vote_cast>"
        + (f"<lis_member_id>{lis}</lis_member_id>" if lis else "<lis_member_id/>")
        + "</member>\n"
        for i, (lis, word) in enumerate(votes)
    )
    if document is None:
        document = (
            f"<document><document_congress>{CONGRESS}</document_congress><document_type>H.R.</document_type>"
            f"<document_number>{number}</document_number><document_name>H.R. {number}</document_name>"
            f"<document_title>A bill {number}</document_title><document_short_title/></document>"
        )
    return f"""<?xml version="1.0" encoding="UTF-8"?><roll_call_vote>
<congress>{CONGRESS}</congress>
<session>{session}</session>
<congress_year>{year}</congress_year>
<vote_number>{claims or number}</vote_number>
<vote_date>January {number}, {year},  {clock or f"02:{number:02d} PM"}</vote_date>
{f"<modify_date>January {number}, {year},  03:{number:02d} PM</modify_date>" if modify else ""}
<vote_question_text>{question} (text {number})</vote_question_text>
<vote_document_text>Document text {number}</vote_document_text>
<vote_result_text>{result} ({yea}-{nay})</vote_result_text>
<question>{question}</question>
<vote_title>Title {number}</vote_title>
<majority_requirement>1/2</majority_requirement>
<vote_result>{result}</vote_result>
{document}
{amendment}
<count><yeas>{count(yea)}</yeas><nays>{count(nay)}</nays><present>{count(present)}</present><absent>{count(absent)}</absent></count>
<tie_breaker><by_whom>{tie[0]}</by_whom><tie_breaker_vote>{tie[1]}</tie_breaker_vote></tie_breaker>
<members>
{members}</members>
</roll_call_vote>"""


class FakeSenate:
    """Stands in for senate.gov: the menus, the origin state of each file, and the download itself."""

    def __init__(self, tmp: Path, files: dict[tuple[int, int], str]) -> None:
        self.tmp = tmp
        self.files = {k: v.encode() for k, v in files.items()}
        self.modified: dict[tuple[int, int], str] = {}
        self.listed_extra: set[tuple[int, int]] = set()  # in the menu but not served
        self.menu_edits: dict[tuple[int, int], dict[str, Any]] = {}  # what the menu says, when it differs
        self.downloads: list[str] = []
        self.heads = 0
        self.fail_downloads: set[str] = set()
        self.head_errors: set[tuple[int, int]] = set()
        self.listing: dict[int, list[int]] = {}

    def publish(self, year: int, number: int, xml: str, modified: str = LATER) -> None:
        self.files[(year, number)] = xml.encode()
        self.modified[(year, number)] = modified

    # SenateVotes surface
    def roll_numbers(self, congress: int, session: int, year: int) -> list[int]:
        assert session == session_of(congress, year)
        if year in self.listing:
            return self.listing[year]
        return sorted({n for (y, n) in [*self.files, *self.listed_extra] if y == year})

    def _menu_line(self, year: int, number: int) -> MenuEntry:
        parsed = parse_senate_vote(self.files[(year, number)])
        roll = parsed.roll
        line = {
            "number": number,
            "date": f"{roll['action_date'].day}-{roll['action_date'].strftime('%b')}",
            "issue": roll["document_name"] or "",
            "question": roll["question"] or "",
            "result": roll["vote_result"] or "",
            "yeas": roll["yea_total"],
            "nays": roll["nay_total"],
            "title": roll["vote_title"] or "",
        }
        return MenuEntry(**{**line, **self.menu_edits.get((year, number), {})})

    def roll_info(self, congress: int, session: int, year: int, number: int) -> SenateRemoteRoll:
        self.heads += 1
        if (year, number) in self.head_errors:
            raise SenateError(f"{number}: 503")
        if (year, number) not in self.files:
            raise SenateNotFound(f"{number}: not published")
        return SenateRemoteRoll(
            year,
            number,
            vote_url(congress, session, number),
            len(self.files[(year, number)]),
            self.modified.get((year, number), MODIFIED),
            session,
            self._menu_line(year, number),
        )

    # Downloader surface (what bulk.download does, without HTTP)
    def download(self, spec: ArtifactSpec, *, overwrite: bool = False) -> Path:
        self.downloads.append(spec.artifact_key)
        if spec.artifact_key in self.fail_downloads:
            raise httpx.ConnectError("connection reset")
        _, _, year, tail = spec.artifact_key.split("-")  # senate-roll-<year>-<number>.xml
        source = self.tmp / f"{spec.artifact_key}.src"
        source.write_bytes(self.files[(int(year), int(tail.split(".")[0]))])
        return register_local(spec, source)


def _files(*numbers: int, year: int = YEAR, **kwargs: Any) -> dict[tuple[int, int], str]:
    return {(year, n): _vote_xml(n, year=year, **kwargs) for n in numbers}


@pytest.fixture
def senate(tmp_path: Path) -> FakeSenate:
    return FakeSenate(tmp_path, _files(1, 2, 3))


def _sync(senate: FakeSenate, **kwargs: Any) -> SenateVotesConnector:
    connector = SenateVotesConnector(
        [CONGRESS],
        senate=senate,  # type: ignore[arg-type]
        downloader=senate.download,
        sleep=lambda _s: None,
        **kwargs,
    )
    run_connector(connector)
    return connector


def _key(number: int, year: int = YEAR) -> str:
    return artifact_key(year, number)


def _artifact(number: int, year: int = YEAR) -> dict:
    with connect() as conn:
        return conn.execute(
            "SELECT * FROM ingest.artifact WHERE artifact_key = %s ORDER BY artifact_version DESC LIMIT 1",
            (_key(number, year),),
        ).fetchone()


def _run_status() -> tuple[str, str | None]:
    return _rows(
        "SELECT status, code_version FROM ingest.run WHERE dataset_id = 'congress.senate_votes' "
        "AND parameters->'congresses' @> '[997]' ORDER BY started_at DESC LIMIT 1"
    )[0]


def _roll_target_status() -> list[tuple]:
    return _rows(
        "SELECT t.status FROM ingest.run_target t JOIN ingest.run r USING (run_id) WHERE r.dataset_id = 'congress.senate_votes' "
        "AND r.parameters->'congresses' @> '[997]' AND target = 'core.roll_call'"
    )


def _roll(number: int, year: int = YEAR) -> dict:
    with connect() as conn:
        return conn.execute(
            "SELECT * FROM core.roll_call WHERE jurisdiction = 'us' AND legislative_session = '997' "
            "AND external_id = %s",
            (senate_external_id(year, number),),
        ).fetchone()


def _votes(number: int, year: int = YEAR) -> dict[str, tuple]:
    """LIS id -> (position, position_raw, party, state, printed name) for one roll call."""
    return {
        r[0]: r[1:]
        for r in _rows(
            "SELECT i.external_id, v.position, v.position_raw, v.party_at_vote, v.state_at_vote, v.name_at_vote "
            "FROM fact.member_vote v JOIN core.person_identifier i "
            "ON i.person_id = v.person_id AND i.namespace = 'lis' "
            "JOIN core.roll_call r ON r.roll_call_id = v.roll_call_id "
            "WHERE r.legislative_session = '997' AND r.external_id = %s",
            senate_external_id(year, number),
        )
    }


def _roll_calls() -> int:
    return _one("SELECT count(*) AS n FROM core.roll_call WHERE legislative_session = '997'")


def _state() -> list[tuple]:
    """Everything loaded, without ids or timestamps: equal states mean equal loads."""
    return _rows(
        "SELECT r.external_id, r.occurred_at, r.question, r.result, r.vote_result, r.yea_total, "
        "r.vote_title, r.document_number, r.bill_id, s.record_sha256, s.entry_count, s.typed_count, "
        "(SELECT count(*) FROM fact.member_vote v WHERE v.roll_call_id = r.roll_call_id) "
        "FROM core.roll_call r JOIN core.roll_call_source_record s USING (roll_call_id) "
        "WHERE r.legislative_session = '997' ORDER BY r.external_id"
    )


def _org(name: str, ocd: str | None) -> str:
    with connect() as conn:
        org = conn.execute(
            "INSERT INTO core.organization (organization_type, name, metadata) VALUES ('upper', %s, %s) "
            "RETURNING organization_id",
            (name, Jsonb({"test997": True})),
        ).fetchone()
        if ocd:
            conn.execute(
                "INSERT INTO core.organization_identifier (organization_id, namespace, external_id, metadata) "
                "VALUES (%s, 'ocd', %s, %s)",
                (org["organization_id"], ocd, Jsonb({"test997": True})),
            )
        conn.commit()
    return str(org["organization_id"])


def _senate_org_exists() -> bool:
    return bool(_rows("SELECT 1 FROM core.organization_identifier WHERE namespace = 'ocd' AND external_id = %s", SENATE_OCD_ORGANIZATION))


def _openstates_roll(number: int, votes: dict[str, str], *, payload: bool = False) -> str:
    """A roll call OpenStates created earlier, with its own (older, partial) votes."""
    art = register_artifact(
        "openstates.legislation", "https://v3.openstates.org/x", "virtual://openstates-997", OPENSTATES_KEY,
        content_type="application/json",
    )
    with connect() as conn:
        roll = conn.execute(
            "INSERT INTO core.roll_call (jurisdiction, legislative_session, chamber, external_id, "
            "occurred_at, question, result, metadata, ocd_id) VALUES ('us', '997', 'senate', %s, "
            "'3781-01-01 00:00+00', 'On the Motion (provider text)', 'fail', %s, 'ocd-vote/test-997') "
            "RETURNING roll_call_id",
            (senate_external_id(YEAR, number), Jsonb({"source": "openstates"})),
        ).fetchone()
        payload_id = None
        if payload:
            run = conn.execute(
                "INSERT INTO ingest.run (dataset_id, mode, status, parameters) "
                "VALUES ('openstates.legislation', 'manual', 'succeeded', %s) RETURNING run_id",
                (Jsonb({"test997": True}),),
            ).fetchone()
            payload_id = conn.execute(
                "INSERT INTO ingest.raw_payload (run_id, source_url, http_status, checksum_sha256, payload) "
                "VALUES (%s, 'https://test-997', 200, 'test-997', '{}'::jsonb) RETURNING payload_id",
                (run["run_id"],),
            ).fetchone()["payload_id"]
        for lis, position in votes.items():
            conn.execute(
                "INSERT INTO fact.member_vote (roll_call_id, person_id, position, source_artifact_id, source_payload_id) "
                "SELECT %s, person_id, %s, %s, %s FROM core.person_identifier "
                "WHERE namespace = 'lis' AND external_id = %s",
                (roll["roll_call_id"], position, art["artifact_id"], payload_id, lis),
            )
        conn.commit()
    return str(roll["roll_call_id"])


# -- the workflow -------------------------------------------------------------
def test_senate_votes_connector_satisfies_the_connector_protocol() -> None:
    assert isinstance(SenateVotesConnector(), Connector)


def test_it_refuses_a_congress_outside_the_supported_range(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(senate_votes, "FIRST_CONGRESS", 108)
    monkeypatch.setattr(senate_votes, "LAST_CONGRESS", 119)
    with pytest.raises(ValueError, match="Senate votes are supported for Congresses 108-119"):
        SenateVotesConnector([500])


def test_the_keys_are_the_ones_openstates_and_the_registry_use() -> None:
    # verified against the official menus 2026-09-20: all 427 OpenStates Senate rows (us-<year>-upper-<n>)
    # equal the menu's roll number of that calendar year, on the same day
    assert senate_external_id(2023, 196) == "us-2023-upper-196"
    assert artifact_key(2005, 100) == "senate-roll-2005-100.xml"
    assert artifact_key(2025, 659) == "senate-roll-2025-659.xml"
    assert session_of(109, 2005) == 1 and session_of(109, 2006) == 2


def test_new_roll_call_is_downloaded_registered_and_loaded_with_every_field(senate: FakeSenate) -> None:
    senate.publish(
        YEAR, 2,
        _vote_xml(2, tie=("Vice President of the United States", "Yea"), question="On the Amendment",
                  amendment=(
                      "<amendment><amendment_number>S.Amdt. 9</amendment_number>"
                      "<amendment_to_amendment_number>S.Amdt. 7</amendment_to_amendment_number>"
                      "<amendment_to_amendment_to_amendment_number>S.Amdt. 5</amendment_to_amendment_to_amendment_number>"
                      "<amendment_to_document_number>H.R. 2</amendment_to_document_number>"
                      "<amendment_to_document_short_title>Short</amendment_to_document_short_title>"
                      "<amendment_purpose>To improve it.</amendment_purpose></amendment>")),
        modified=MODIFIED,
    )
    connector = _sync(senate)

    assert senate.downloads == [_key(1), _key(2), _key(3)]
    result = connector.result
    assert result["chamber"] == "senate" and result["downloaded"] == 3 and result["roll_calls_inserted"] == 3
    assert result["partial"] is False and result["member_votes_written"] == 15
    assert result["roll_calls_enriched_from_openstates"] == 0 and result["disagreements_with_menu"] == []
    artifact = _artifact(2)
    xml = senate.files[(YEAR, 2)]
    assert artifact["status"] == "loaded" and artifact["artifact_version"] == 1
    assert artifact["checksum_sha256"] == hashlib.sha256(xml).hexdigest()
    assert artifact["remote_url"] == vote_url(CONGRESS, 1, 2)
    assert artifact["metadata"]["origin"] == "senate.gov" and artifact["metadata"]["remote_size"] == len(xml)
    assert artifact["metadata"]["remote_last_modified"] == MODIFIED
    assert Path(artifact["local_path"]).read_bytes() == xml and str(settings.data_root) in artifact["local_path"]
    assert sorted(p.suffix for p in Path(settings.data_root).rglob("*") if p.is_file()) == [".xml"] * 3

    roll = _roll(2)
    assert roll["chamber"] == "senate" and roll["metadata"] == {"source": "senate_gov"}
    assert (roll["roll_number"], roll["roll_year"], roll["congress_session"]) == (2, YEAR, "1st")
    assert (roll["question"], roll["vote_result"], roll["result"]) == ("On the Amendment", "Motion Agreed to", "pass")
    assert roll["vote_question_text"] == "On the Amendment (text 2)" and roll["vote_title"] == "Title 2"
    assert roll["vote_document_text"] == "Document text 2" and roll["vote_result_text"] == "Motion Agreed to (2-1)"
    assert roll["majority_requirement"] == "1/2" and roll["vote_type"] is None
    assert (roll["yea_total"], roll["nay_total"], roll["present_total"], roll["not_voting_total"]) == (2, 1, 1, 1)
    assert str(roll["action_date"]) == f"{YEAR}-01-02" and roll["action_time_etz"] == "14:02"
    assert roll["occurred_at"].astimezone(UTC) == datetime(YEAR, 1, 2, 19, 2, tzinfo=UTC)  # 14:02 EST
    assert roll["modified_at"].astimezone(UTC) == datetime(YEAR, 1, 2, 20, 2, tzinfo=UTC)
    assert (roll["document_congress"], roll["document_type"], roll["document_number"], roll["document_name"]) == (
        CONGRESS, "H.R.", "2", "H.R. 2")
    assert (roll["document_title"], roll["document_short_title"]) == ("A bill 2", None)
    assert (roll["amendment_number"], roll["amendment_to_amendment_number"],
            roll["amendment_to_amendment_to_amendment_number"]) == ("S.Amdt. 9", "S.Amdt. 7", "S.Amdt. 5")
    assert (roll["amendment_to_document_number"], roll["amendment_to_document_short_title"],
            roll["amendment_purpose"]) == ("H.R. 2", "Short", "To improve it.")
    assert (roll["tie_breaker_by"], roll["tie_breaker_vote"]) == ("Vice President of the United States", "Yea")
    assert roll["source_artifact_id"] == artifact["artifact_id"] and roll["legislative_session_id"] is not None
    assert _rows("SELECT count(*) FROM core.roll_call_party_total WHERE roll_call_id = %s", roll["roll_call_id"]) == [(0,)]
    assert _votes(2) == {
        "T997001": ("yes", "Yea", "R", "XX", "Person 0 (R-XX)"),
        "T997002": ("no", "Nay", "D", "XX", "Person 1 (D-XX)"),
        "T997003": ("yes", "Yea", "R", "XX", "Person 2 (R-XX)"),
        "T997004": ("not voting", "Not Voting", "D", "XX", "Person 3 (D-XX)"),
        "T997005": ("other", "Present", "R", "XX", "Person 4 (R-XX)"),
    }
    assert _rows(
        "SELECT v.last_name_at_vote, v.first_name_at_vote, v.lis_member_id_at_vote FROM fact.member_vote v "
        "WHERE v.roll_call_id = %s ORDER BY v.lis_member_id_at_vote LIMIT 1", roll["roll_call_id"]
    ) == [("Person0", "First0", "T997001")]
    # the vice president is in the roll call, not among the members
    assert _one("SELECT count(*) AS n FROM fact.member_vote WHERE roll_call_id = %s", roll["roll_call_id"]) == 5
    with connect() as conn:
        stored = conn.execute(
            "SELECT record, entry_count, typed_count, entries_without_id, unresolved_bioguide_ids "
            "FROM core.roll_call_source_record WHERE source_artifact_id = %s",
            (artifact["artifact_id"],),
        ).fetchone()
    assert stored["record"] == xml_to_record(ElementTree.fromstring(xml), SENATE_LIST_TAGS)
    assert (stored["entry_count"], stored["typed_count"], stored["entries_without_id"], stored["unresolved_bioguide_ids"]) == (5, 5, 0, [])
    assert _one(
        "SELECT count(*) AS n FROM fact.member_vote v JOIN core.roll_call r USING (roll_call_id) "
        "JOIN ingest.artifact a ON a.artifact_id = v.source_artifact_id "
        "WHERE r.legislative_session = '997' AND a.checksum_sha256 IS NOT NULL "
        "AND a.artifact_key LIKE 'senate-roll-378%' AND a.metadata->>'run_id' IS NOT NULL"
    ) == 15
    status, code_version = _run_status()
    assert status == "succeeded" and code_version
    assert _rows(
        "SELECT t.target, t.coverage_key, t.rows_inserted, t.rows_updated, t.status FROM ingest.run_target t "
        "JOIN ingest.run r USING (run_id) WHERE r.dataset_id = 'congress.senate_votes' "
        "AND r.parameters->'congresses' @> '[997]' ORDER BY 1"
    ) == [
        ("core.roll_call", "congress=997", 3, 0, "succeeded"),
        ("fact.member_vote", "congress=997", 15, 0, "succeeded"),
    ]


def test_unchanged_rerun_downloads_nothing_and_changes_nothing(senate: FakeSenate) -> None:
    _sync(senate)
    before = _state()
    versions = _one("SELECT count(*) AS n FROM ingest.artifact WHERE artifact_key LIKE 'senate-roll-378%'")

    connector = _sync(senate)

    assert senate.downloads == [_key(1), _key(2), _key(3)]  # only the first run fetched bytes
    assert connector.result["downloaded"] == 0 and connector.result["reused"] == 3
    assert connector.result["roll_calls_loaded"] == 0 and connector.result["member_votes_written"] == 0
    assert _state() == before
    assert _one("SELECT count(*) AS n FROM ingest.artifact WHERE artifact_key LIKE 'senate-roll-378%'") == versions
    assert _run_status()[0] == "succeeded"


def test_changed_origin_appends_a_version_and_replaces_the_old_rows_in_one_transaction(senate: FakeSenate) -> None:
    _sync(senate)
    roll_id = _roll(2)["roll_call_id"]
    old_artifact = _artifact(2)["artifact_id"]
    senate.publish(
        YEAR, 2,
        _vote_xml(2, [("T997001", "Nay"), ("T997002", "Nay"), ("T997003", "Yea")], question="On the Motion, Corrected"),
    )

    connector = _sync(senate)

    assert senate.downloads.count(_key(2)) == 2 and senate.downloads.count(_key(1)) == 1
    assert connector.result["downloaded"] == 1 and connector.result["reused"] == 2
    new_artifact = _artifact(2)
    assert new_artifact["artifact_version"] == 2 and new_artifact["artifact_id"] != old_artifact
    assert _roll(2)["roll_call_id"] == roll_id
    assert _roll(2)["question"] == "On the Motion, Corrected" and _roll(2)["source_artifact_id"] == new_artifact["artifact_id"]
    assert _votes(2) == {
        "T997001": ("no", "Nay", "R", "XX", "Person 0 (R-XX)"),
        "T997002": ("no", "Nay", "D", "XX", "Person 1 (D-XX)"),
        "T997003": ("yes", "Yea", "R", "XX", "Person 2 (R-XX)"),
    }
    assert _rows("SELECT source_artifact_id FROM core.roll_call_source_record WHERE roll_call_id = %s", roll_id) == [
        (new_artifact["artifact_id"],)
    ]
    assert connector.result["roll_calls_refreshed"] == 1 and connector.result["roll_calls_inserted"] == 0
    old = _rows("SELECT local_path FROM ingest.artifact WHERE artifact_id = %s", old_artifact)[0][0]
    assert Path(old).is_file()  # evidence is never deleted


def test_a_failed_refresh_leaves_the_old_rows_untouched(senate: FakeSenate, monkeypatch: pytest.MonkeyPatch) -> None:
    _sync(senate)
    before, votes = _state(), _votes(2)
    senate.publish(YEAR, 2, _vote_xml(2, [("T997001", "Nay")]))
    real = senate_votes.save_senate_roll_call

    def save_then_die(*args: Any, **kwargs: Any) -> Any:
        real(*args, **kwargs)  # the new rows and the deletes of the old ones are in the transaction ...
        raise RuntimeError("disk full")  # ... which now rolls back as a whole

    monkeypatch.setattr(senate_votes, "save_senate_roll_call", save_then_die)
    with pytest.raises(RuntimeError, match="disk full"):
        _sync(senate)

    assert _state() == before and _votes(2) == votes
    assert _run_status()[0] == "failed"


def test_an_openstates_roll_call_is_enriched_in_place_not_duplicated(senate: FakeSenate) -> None:
    roll_id = _openstates_roll(2, {"T997001": "no", "T997002": "no"}, payload=True)
    assert _one("SELECT count(*) AS n FROM fact.member_vote WHERE roll_call_id = %s AND source_payload_id IS NOT NULL", roll_id) == 2
    with connect() as conn:  # fields only a House-style row has must not survive on a replaced Senate vote
        conn.execute(
            "UPDATE fact.member_vote SET sort_name_at_vote = 's', unaccented_name_at_vote = 'u', role_at_vote = 'r' "
            "WHERE roll_call_id = %s", (roll_id,),
        )
        conn.commit()

    connector = _sync(senate)

    assert _roll_calls() == 3  # 2 new + the existing one; none duplicated
    roll = _roll(2)
    assert str(roll["roll_call_id"]) == roll_id
    assert roll["metadata"]["source"] == "openstates" and roll["ocd_id"] == "ocd-vote/test-997"
    assert roll["question"] == "On the Motion" and roll["result"] == "pass"  # official evidence wins
    assert roll["occurred_at"].astimezone(UTC) == datetime(YEAR, 1, 2, 19, 2, tzinfo=UTC)
    assert (roll["roll_number"], roll["yea_total"], roll["vote_result"], roll["vote_title"]) == (2, 2, "Motion Agreed to", "Title 2")
    assert connector.result["roll_calls_enriched_from_openstates"] == 1 and connector.result["roll_calls_inserted"] == 2
    assert _votes(2)["T997001"] == ("yes", "Yea", "R", "XX", "Person 0 (R-XX)")
    assert len(_votes(2)) == 5
    assert _one("SELECT count(*) AS n FROM fact.member_vote WHERE roll_call_id = %s AND source_payload_id IS NOT NULL", roll_id) == 0
    assert _one(
        "SELECT count(*) AS n FROM fact.member_vote WHERE roll_call_id = %s AND (sort_name_at_vote IS NOT NULL "
        "OR unaccented_name_at_vote IS NOT NULL OR role_at_vote IS NOT NULL)", roll_id,
    ) == 0
    assert _one(
        "SELECT count(*) AS n FROM fact.member_vote WHERE roll_call_id = %s AND source_artifact_id = %s",
        roll_id, _artifact(2)["artifact_id"],
    ) == 5
    assert _rows(
        "SELECT target, rows_inserted, rows_updated FROM ingest.run_target t JOIN ingest.run r USING (run_id) "
        "WHERE r.dataset_id = 'congress.senate_votes' AND r.parameters->'congresses' @> '[997]' "
        "AND target = 'core.roll_call'"
    ) == [("core.roll_call", 2, 1)]


def test_a_count_disagreement_with_existing_votes_is_reported_not_hidden(senate: FakeSenate) -> None:
    _add_people({"T997009": "Extra"})
    _openstates_roll(2, {"T997009": "yes"})

    connector = _sync(senate)

    assert connector.result["count_disagreements"] == 1
    assert connector.result["count_disagreement_examples"] == [
        {"roll": senate_external_id(YEAR, 2), "official": [2, 1, 1], "stored": [3, 1, 1]}
    ]
    assert len(_votes(2)) == 6 and connector.result["partial"] is False


def test_an_unknown_lis_id_is_reported_never_name_matched_and_retried_later(senate: FakeSenate) -> None:
    # a person with the very name the file prints exists, but holds no LIS id: still not matched
    _add_people({"T997998": "Person 5"})
    with connect() as conn:
        conn.execute("DELETE FROM core.person_identifier WHERE namespace = 'lis' AND external_id = 'T997998'")
        conn.commit()
    senate.publish(YEAR, 2, _vote_xml(2, [*DEFAULT_VOTES, ("T997999", "Yea")]), modified=MODIFIED)

    connector = _sync(senate)

    assert set(_votes(2)) == set(PEOPLE)  # no row for T997999
    assert connector.result["unresolved_lis_member_ids"] == {"T997999": [_key(2)]}
    assert connector.result["partial"] is True and _run_status()[0] == "partial"
    assert _one("SELECT unresolved_bioguide_ids FROM core.roll_call_source_record s JOIN core.roll_call r USING (roll_call_id) "
                "WHERE r.external_id = %s", senate_external_id(YEAR, 2)) == ["T997999"]
    assert _rows(
        "SELECT t.status FROM ingest.run_target t JOIN ingest.run r USING (run_id) WHERE r.dataset_id = 'congress.senate_votes' "
        "AND r.parameters->'congresses' @> '[997]' AND target = 'core.roll_call'"
    ) == [("partial",)]
    again = _sync(senate)
    assert again.result["unresolved_lis_member_ids"] == {"T997999": [_key(2)]} and again.result["downloaded"] == 0
    _add_people({"T997999": "Late Arrival"})
    fixed = _sync(senate)
    assert fixed.result["partial"] is False and fixed.result["unresolved_lis_member_ids"] == {}
    assert _votes(2)["T997999"][:2] == ("yes", "Yea") and senate.downloads.count(_key(2)) == 1


def test_a_senator_with_no_lis_id_is_listed_not_created_and_the_run_is_partial(senate: FakeSenate) -> None:
    senate.publish(YEAR, 2, _vote_xml(2, [*DEFAULT_VOTES, (None, "Nay")]), modified=MODIFIED)

    connector = _sync(senate)

    assert len(_votes(2)) == 5
    assert connector.result["entries_without_lis_member_id"] == 1 and connector.result["partial"] is True
    assert connector.result["unresolved_lis_member_ids"] == {"(no lis_member_id) Person 5 (D-XX)": [_key(2)]}
    assert _run_status()[0] == "partial"
    row = _rows(
        "SELECT entry_count, typed_count, entries_without_id, jsonb_array_length(record->'members'->'member') "
        "FROM core.roll_call_source_record s JOIN core.roll_call r USING (roll_call_id) WHERE r.external_id = %s",
        senate_external_id(YEAR, 2),
    )
    assert row == [(6, 5, 1, 6)]  # the entry stays in the record


def test_a_tie_break_is_typed_on_the_roll_call_and_the_vice_president_is_no_member(senate: FakeSenate) -> None:
    senate.publish(
        YEAR, 2,
        _vote_xml(2, [("T997001", "Yea"), ("T997002", "Nay")], tie=("Vice President of the United States", "Yea")),
        modified=MODIFIED,
    )
    connector = _sync(senate)

    roll = _roll(2)
    assert (roll["tie_breaker_by"], roll["tie_breaker_vote"]) == ("Vice President of the United States", "Yea")
    assert (roll["yea_total"], roll["nay_total"]) == (1, 1) and len(_votes(2)) == 2
    assert connector.result["partial"] is False
    assert _one("SELECT record->'tie_breaker'->>'by_whom' AS v FROM core.roll_call_source_record WHERE roll_call_id = %s",
                roll["roll_call_id"]) == "Vice President of the United States"
    assert _roll(1)["tie_breaker_by"] is None and _roll(1)["tie_breaker_vote"] is None


def test_guilty_and_not_guilty_keep_the_stated_word_and_are_not_reported_as_a_disagreement(senate: FakeSenate) -> None:
    senate.publish(
        YEAR, 2,
        _vote_xml(2, [("T997001", "Guilty"), ("T997002", "Not Guilty"), ("T997003", "Guilty")],
                  question="Guilty or Not Guilty", result="Not Guilty"),
        modified=MODIFIED,
    )

    connector = _sync(senate)

    assert _votes(2) == {
        "T997001": ("other", "Guilty", "R", "XX", "Person 0 (R-XX)"),
        "T997002": ("other", "Not Guilty", "D", "XX", "Person 1 (D-XX)"),
        "T997003": ("other", "Guilty", "R", "XX", "Person 2 (R-XX)"),
    }
    assert _roll(2)["vote_result"] == "Not Guilty" and _roll(2)["result"] is None
    assert connector.result["count_disagreements"] == 0
    assert connector.result["parse_problems"] == {"result_not_normalized": {"count": 1, "examples": [_key(2)]}}
    assert connector.result["partial"] is False


def test_a_nomination_and_a_treaty_keep_their_blocks_and_link_to_no_bill(senate: FakeSenate) -> None:
    _add_bill("hr", 2)  # a bill numbered like the nomination must not attract it
    nomination = (
        f"<document><document_congress>{CONGRESS}</document_congress><document_type>PN</document_type>"
        "<document_number>2</document_number><document_name>PN2</document_name>"
        "<document_title>A. Person, to be a Judge</document_title><document_short_title/></document>"
    )
    treaty = (
        f"<document><document_congress>{CONGRESS}</document_congress><document_type/><document_number/>"
        "<document_name/><document_title/><document_short_title/></document>"
    )
    treaty_amendment = (
        "<amendment><amendment_number>S.Amdt. 4895</amendment_number>"
        "<amendment_to_document_number>Treaty Doc. 997-5</amendment_to_document_number>"
        "<amendment_purpose>To provide an understanding.</amendment_purpose></amendment>"
    )
    senate.publish(YEAR, 2, _vote_xml(2, document=nomination, question="On the Nomination", result="Nomination Confirmed"), modified=MODIFIED)
    senate.publish(YEAR, 3, _vote_xml(3, document=treaty, amendment=treaty_amendment, question="On the Amendment"), modified=MODIFIED)

    connector = _sync(senate)

    nom, tre = _roll(2), _roll(3)
    assert (nom["document_type"], nom["document_number"], nom["document_name"]) == ("PN", "2", "PN2")
    assert nom["bill_id"] is None and nom["result"] == "pass" and nom["question"] == "On the Nomination"
    assert (tre["document_type"], tre["document_number"], tre["document_congress"]) == (None, None, CONGRESS)
    assert (tre["amendment_number"], tre["amendment_to_document_number"]) == ("S.Amdt. 4895", "Treaty Doc. 997-5")
    assert tre["bill_id"] is None and connector.result["partial"] is False


def test_a_roll_call_links_to_its_bill_by_congress_type_and_number_only(senate: FakeSenate) -> None:
    bill = _add_bill("hr", 1)
    other_congress = _add_bill("hr", 3, congress=996)  # same type and number, other Congress: not it

    connector = _sync(senate)

    assert str(_roll(1)["bill_id"]) == bill  # H.R. 1 of Congress 997
    assert _roll(2)["bill_id"] is None  # H.R. 2 is not in core.bill: never guessed
    assert _roll(3)["bill_id"] is None and other_congress
    assert connector.result["partial"] is False
    with connect() as conn:
        conn.execute("DELETE FROM core.bill WHERE bill_id = %s", (other_congress,))
        conn.commit()


def test_a_bill_loaded_after_its_roll_call_is_linked_by_the_next_run_without_a_download(senate: FakeSenate) -> None:
    _sync(senate)
    assert _roll(2)["bill_id"] is None
    late = _add_bill("hr", 2)

    connector = _sync(senate)

    assert str(_roll(2)["bill_id"]) == late and senate.downloads.count(_key(2)) == 1
    assert connector.result["linked_to_bills_at_end"] == 1


def test_an_older_file_that_names_no_document_congress_links_within_its_own_congress(senate: FakeSenate) -> None:
    old = (
        "<document><document_type>H.R.</document_type><document_number>2</document_number>"
        "<document_name>H.R. 2</document_name><document_title>Old</document_title><document_short_title/></document>"
    )
    senate.publish(YEAR, 2, _vote_xml(2, document=old, modify=False), modified=MODIFIED)
    bill = _add_bill("hr", 2)

    _sync(senate)

    roll = _roll(2)
    assert roll["document_congress"] is None and roll["modified_at"] is None  # the file did not say: NULL
    assert str(roll["bill_id"]) == bill


def test_a_link_already_made_survives_a_refreshed_file_that_cannot_make_it(senate: FakeSenate) -> None:
    bill = _add_bill("hr", 2)
    _sync(senate)
    assert str(_roll(2)["bill_id"]) == bill
    senate.publish(YEAR, 2, _vote_xml(2, document="<document><document_type>PN</document_type><document_number>9</document_number></document>"))

    _sync(senate)

    assert str(_roll(2)["bill_id"]) == bill and _roll(2)["document_type"] == "PN"


def test_a_vote_the_menu_lists_without_a_file_is_reported_and_is_not_an_error(senate: FakeSenate) -> None:
    senate.listed_extra = {(YEAR, 4)}

    connector = _sync(senate)

    assert connector.result["not_published"] == [_key(4)]
    assert connector.result["partial"] is False and _roll_calls() == 3 and connector.result["files_listed"] == 4
    assert _run_status()[0] == "succeeded"


def test_a_file_that_disagrees_with_the_menu_is_reported_and_the_run_is_partial(senate: FakeSenate) -> None:
    senate.menu_edits[(YEAR, 2)] = {"yeas": 99, "date": "31-Dec"}

    connector = _sync(senate)

    assert connector.result["disagreements_with_menu"] == [_key(2)] and connector.result["partial"] is True
    assert any("the menu lists 99 yeas, the file says 2" in p for p in connector.result["problems"])
    assert any("the menu dates it 31-Dec" in p for p in connector.result["problems"])
    assert _roll_calls() == 3 and _run_status()[0] == "partial"  # loaded, flagged
    assert _roll_target_status() == [("partial",)]


def test_a_killed_run_resumes_and_ends_equal_to_a_clean_load(senate: FakeSenate, monkeypatch: pytest.MonkeyPatch) -> None:
    real = senate_votes.save_senate_roll_call
    calls = {"n": 0}

    def die_on_third(*args: Any, **kwargs: Any) -> Any:
        calls["n"] += 1
        if calls["n"] == 3:
            raise RuntimeError("killed")
        return real(*args, **kwargs)

    monkeypatch.setattr(senate_votes, "save_senate_roll_call", die_on_third)
    with pytest.raises(RuntimeError, match="killed"):
        _sync(senate, batch_size=1)
    assert _roll_calls() == 2 and _run_status()[0] == "failed"
    assert _rows(
        "SELECT t.status, t.rows_inserted FROM ingest.run_target t JOIN ingest.run r USING (run_id) "
        "WHERE r.dataset_id = 'congress.senate_votes' AND r.parameters->'congresses' @> '[997]' AND target = 'core.roll_call'"
    ) == [("partial", 2)]
    monkeypatch.setattr(senate_votes, "save_senate_roll_call", real)

    resumed = _sync(senate, batch_size=1)

    assert resumed.result["roll_calls_loaded"] == 1 and resumed.result["downloaded"] == 0
    resumed_state = _state()
    assert len(resumed_state) == 3
    _remove_rows()
    _add_people(PEOPLE)
    _sync(FakeSenate(senate.tmp, {(YEAR, n): xml.decode() for (_, n), xml in senate.files.items()}))
    assert _state() == resumed_state


def test_download_only_registers_the_bytes_and_a_later_sync_loads_without_refetching(senate: FakeSenate) -> None:
    connector = _sync(senate, download_only=True)

    assert connector.result["downloaded"] == 3 and _roll_calls() == 0
    assert _artifact(1)["status"] == "downloaded"
    senate.downloads.clear()

    loaded = _sync(senate)

    assert senate.downloads == [] and _roll_calls() == 3 and _artifact(1)["status"] == "loaded"
    assert loaded.result["partial"] is False


def test_a_file_that_is_not_the_roll_call_its_name_promises_is_skipped_and_reported(senate: FakeSenate) -> None:
    senate.publish(YEAR, 3, _vote_xml(3, claims=9), modified=MODIFIED)

    connector = _sync(senate)

    assert connector.result["malformed"] == [_key(3)] and connector.result["partial"] is True
    assert _roll_calls() == 2 and any("roll 9" in p for p in connector.result["problems"])


def test_a_file_from_the_wrong_session_is_skipped_and_reported(senate: FakeSenate) -> None:
    senate.publish(YEAR, 3, _vote_xml(3, session=2), modified=MODIFIED)

    connector = _sync(senate)

    assert connector.result["malformed"] == [_key(3)] and _roll_calls() == 2


def test_both_sessions_of_a_congress_are_listed_and_keyed_by_calendar_year(tmp_path: Path) -> None:
    files = {**_files(1, 2), **_files(1, year=LATER_YEAR, session=2)}
    senate = FakeSenate(tmp_path, files)

    connector = _sync(senate)

    assert connector.result["files_listed"] == 3 and _roll_calls() == 3
    assert {r[0] for r in _rows("SELECT external_id FROM core.roll_call WHERE legislative_session = '997'")} == {
        senate_external_id(YEAR, 1), senate_external_id(YEAR, 2), senate_external_id(LATER_YEAR, 1),
    }
    assert _roll(1, LATER_YEAR)["congress_session"] == "2nd"
    assert connector.result["years"] == {YEAR: {"listed": 2, "served": 2}, LATER_YEAR: {"listed": 1, "served": 1}}


def test_one_failed_download_is_reported_and_the_rerun_fetches_only_that_file(senate: FakeSenate) -> None:
    senate.fail_downloads = {_key(2)}

    connector = _sync(senate)

    assert connector.result["partial"] is True and list(connector.result["failed"]) == [_key(2)]
    assert _roll_calls() == 2 and _run_status()[0] == "partial"
    assert _roll_target_status() == [("partial",)]
    senate.fail_downloads = set()
    senate.downloads.clear()

    fixed = _sync(senate)

    assert senate.downloads == [_key(2)] and fixed.result["partial"] is False and _roll_calls() == 3


def test_a_non_redirect_failure_on_one_file_is_failed_not_unpublished_and_a_rerun_picks_it_up(senate: FakeSenate) -> None:
    senate.head_errors = {(YEAR, 2)}

    connector = _sync(senate)

    assert list(connector.result["failed"]) == [_key(2)] and connector.result["not_published"] == []
    assert connector.result["partial"] is True and _roll_calls() == 2
    senate.head_errors = set()

    fixed = _sync(senate)

    assert fixed.result["partial"] is False and _roll_calls() == 3


def test_a_truncated_menu_is_reported_as_unlisted_and_the_run_is_partial(senate: FakeSenate) -> None:
    senate.listing = {YEAR: [1, 3]}

    connector = _sync(senate)

    assert connector.result["unlisted"] == {YEAR: [2]} and connector.result["partial"] is True
    assert _run_status()[0] == "partial" and _roll_calls() == 2
    assert _roll_target_status() == [("partial",)]


def test_same_bytes_with_a_new_last_modified_keeps_the_version_and_reloads_nothing(senate: FakeSenate) -> None:
    _sync(senate)
    before = _state()
    senate.modified[(YEAR, 2)] = LATER

    connector = _sync(senate)

    assert connector.result["downloaded"] == 1 and connector.result["roll_calls_loaded"] == 0
    assert _artifact(2)["artifact_version"] == 1 and _artifact(2)["metadata"]["remote_last_modified"] == LATER
    assert _state() == before and _artifact(2)["status"] == "loaded"


def test_a_second_sync_at_the_same_time_is_refused_at_once(senate: FakeSenate) -> None:
    first = SenateVotesConnector([CONGRESS], senate=senate, downloader=senate.download)  # type: ignore[arg-type]
    first._acquire_lock()
    try:
        with pytest.raises(RuntimeError, match="another sync-votes run for the Senate"):
            _sync(senate)
    finally:
        first._lock.close()
    assert _one("SELECT count(*) AS n FROM ingest.run WHERE dataset_id = 'congress.senate_votes' "
                "AND parameters->'congresses' @> '[997]'") == 0


def test_the_house_and_senate_syncs_do_not_block_each_other(senate: FakeSenate) -> None:
    from opendiscourse_research.ingestion.house_votes import HouseVotesConnector

    house = HouseVotesConnector()
    house._acquire_lock()
    try:
        assert _sync(senate).result["partial"] is False
    finally:
        house._lock.close()


def test_the_capacity_gate_stops_before_any_download(senate: FakeSenate) -> None:
    refusal = {"approved": False, "reason": "insufficient capacity", "path": "/x",
               "peak_required_bytes": 10, "filesystem_free_bytes": 1}
    with (
        patch.object(roll_call_votes, "storage_preview", return_value=refusal),
        pytest.raises(RuntimeError, match="capacity gate"),
    ):
        _sync(senate)
    assert senate.downloads == [] and _roll_calls() == 0 and _run_status()[0] == "failed"


def test_new_roll_calls_link_to_the_senate_organization_and_an_existing_link_is_kept(senate: FakeSenate) -> None:
    # runs on a database that already has the Senate organization too: then that one is used, unchanged
    existing = _rows("SELECT organization_id FROM core.organization_identifier WHERE namespace = 'ocd' AND external_id = %s", SENATE_OCD_ORGANIZATION)
    senate_org = str(existing[0][0]) if existing else _org("Senate", SENATE_OCD_ORGANIZATION)
    other = _org("Some other body", "ocd-organization/test-997")
    roll = _openstates_roll(2, {"T997001": "no"})
    with connect() as conn:
        conn.execute("UPDATE core.roll_call SET organization_id = %s WHERE roll_call_id = %s", (other, roll))
        conn.commit()

    connector = _sync(senate)

    assert str(_roll(1)["organization_id"]) == senate_org and str(_roll(3)["organization_id"]) == senate_org
    assert str(_roll(2)["organization_id"]) == other  # the provider's row keeps what it had
    assert not any("organization" in p for p in connector.result["problems"])


def test_a_missing_senate_organization_is_reported_and_the_roll_calls_still_load(senate: FakeSenate) -> None:
    # on a database that has the Senate organization, hide its identifier for the run and put it back after
    hidden = _senate_org_exists()
    move = "UPDATE core.organization_identifier SET external_id = %s WHERE namespace = 'ocd' AND external_id = %s"
    if hidden:
        with connect() as conn:
            conn.execute(move, (SENATE_OCD_ORGANIZATION + "-hidden-test997", SENATE_OCD_ORGANIZATION))
            conn.commit()
    try:
        connector = _sync(senate)
    finally:
        if hidden:
            with connect() as conn:
                conn.execute(move, (SENATE_OCD_ORGANIZATION, SENATE_OCD_ORGANIZATION + "-hidden-test997"))
                conn.commit()

    assert any("Senate organization" in p and SENATE_OCD_ORGANIZATION in p for p in connector.result["problems"])
    assert _roll(1)["organization_id"] is None and _roll_calls() == 3
    assert _senate_org_exists() == hidden


def test_the_migration_refuses_to_downgrade_while_senate_rows_exist(senate: FakeSenate) -> None:
    _sync(senate)

    with pytest.raises(RuntimeError, match=r"3 Senate rows in core\.roll_call_source_record"):
        command.downgrade(_alembic_config(), "d5a1f8c37e26")

    assert _one("SELECT version_num AS v FROM alembic_version") == "c9e4a1b27d83"
    assert _roll_calls() == 3 and len(_votes(2)) == 5  # nothing was dropped


def test_the_migration_also_refuses_for_an_enriched_row_without_a_vote_title_or_a_bare_source_record(senate: FakeSenate) -> None:
    roll = _openstates_roll(2, {})
    with connect() as conn:  # enriched by a file that had no vote title: only a tie-breaker landed
        conn.execute("UPDATE core.roll_call SET tie_breaker_by = 'Vice President' WHERE roll_call_id = %s", (roll,))
        conn.commit()
    with pytest.raises(RuntimeError, match=r"core\.roll_call rows carry Senate detail"):
        command.downgrade(_alembic_config(), "d5a1f8c37e26")
    assert _one("SELECT version_num AS v FROM alembic_version") == "c9e4a1b27d83"

    with connect() as conn:  # no roll-call column set, but a Senate source record exists
        conn.execute("UPDATE core.roll_call SET tie_breaker_by = NULL WHERE roll_call_id = %s", (roll,))
        art = register_artifact(
            "congress.senate_votes", "https://www.senate.gov/x", "virtual://senate-997", "senate-roll-3781-777.xml",
            content_type="text/xml",
        )
        conn.execute(
            "INSERT INTO core.roll_call_source_record (roll_call_id, source_artifact_id, record, record_sha256) "
            "VALUES (%s, %s, '{}'::jsonb, 'x')", (roll, art["artifact_id"]),
        )
        conn.commit()
    with pytest.raises(RuntimeError, match=r"Senate rows in core\.roll_call_source_record"):
        command.downgrade(_alembic_config(), "d5a1f8c37e26")
    assert _one("SELECT version_num AS v FROM alembic_version") == "c9e4a1b27d83"


def test_the_official_result_replaces_a_stale_provider_result_even_when_it_is_not_pass_or_fail(senate: FakeSenate) -> None:
    roll_id = _openstates_roll(2, {})
    with connect() as conn:
        conn.execute("UPDATE core.roll_call SET result = 'pass' WHERE roll_call_id = %s", (roll_id,))
        conn.commit()
    senate.publish(YEAR, 2, _vote_xml(2, result="Point of Order Well Taken"), modified=MODIFIED)

    _sync(senate)

    roll = _roll(2)
    assert str(roll["roll_call_id"]) == roll_id
    assert roll["vote_result"] == "Point of Order Well Taken" and roll["result"] is None


def test_guilty_is_counted_whatever_its_letter_case(senate: FakeSenate) -> None:
    xml = _vote_xml(2, [("T997001", "Guilty"), ("T997002", "Not Guilty")], question="Guilty or Not Guilty")
    senate.publish(YEAR, 2, xml.replace(">Guilty<", ">GUILTY<").replace(">Not Guilty<", ">NOT GUILTY<"), modified=MODIFIED)

    connector = _sync(senate)

    assert {v[1] for v in _votes(2).values()} == {"GUILTY", "NOT GUILTY"}
    assert connector.result["count_disagreements"] == 0


def test_a_listed_roll_with_no_menu_line_is_reported_as_a_disagreement_not_skipped(senate: FakeSenate) -> None:
    real = senate.roll_info

    def without_menu(congress: int, session: int, year: int, number: int) -> SenateRemoteRoll:
        info = real(congress, session, year, number)
        return SenateRemoteRoll(info.year, info.number, info.url, info.size, info.last_modified, info.session, None) if number == 2 else info

    senate.roll_info = without_menu  # type: ignore[method-assign]

    connector = _sync(senate)

    assert connector.result["disagreements_with_menu"] == [_key(2)] and connector.result["partial"] is True
    assert any("no line for it" in p for p in connector.result["problems"]) and _roll_calls() == 3


BILL_DOCUMENTS = [
    ("H.R.", "hr"), ("S.", "s"), ("H.Res.", "hres"), ("S.Res.", "sres"),
    ("H.Con.Res.", "hconres"), ("S.Con.Res.", "sconres"), ("H.J.Res.", "hjres"), ("S.J.Res.", "sjres"),
]


@pytest.mark.parametrize(("document_type", "bill_type"), BILL_DOCUMENTS, ids=[d for d, _ in BILL_DOCUMENTS])
def test_every_bill_document_type_links_at_insert_and_again_at_the_end_of_a_later_run(
    senate: FakeSenate, document_type: str, bill_type: str
) -> None:
    def document(number: int) -> str:
        return (
            f"<document><document_congress>{CONGRESS}</document_congress><document_type>{document_type}</document_type>"
            f"<document_number>{number}</document_number><document_name>{document_type} {number}</document_name>"
            "<document_title>T</document_title><document_short_title/></document>"
        )

    for number in (1, 2):
        senate.publish(YEAR, number, _vote_xml(number, document=document(number)), modified=MODIFIED)
    first = _add_bill(bill_type, 1)

    connector = _sync(senate)

    assert str(_roll(1)["bill_id"]) == first  # linked when the roll call was written ...
    assert _roll(2)["bill_id"] is None and connector.result["linked_to_bills_at_end"] == 0
    second = _add_bill(bill_type, 2)

    again = _sync(senate)

    assert str(_roll(2)["bill_id"]) == second and again.result["linked_to_bills_at_end"] == 1  # ... and at the end of a run
    assert str(_roll(1)["bill_id"]) == first


class _Origin:
    """The real ``SenateVotes`` client's ``send``: menus and HEAD answers for a fake Senate's files."""

    def __init__(self, senate: FakeSenate) -> None:
        self.senate = senate
        self.menu_edits: dict[int, dict[str, str]] = {}
        self.requests: list[tuple[str, str]] = []

    def __call__(self, method: str, url: str) -> httpx.Response:
        self.requests.append((method, url))
        request = httpx.Request(method, url)
        if match := re.search(r"vote_menu_997_(\d)\.xml$", url):
            year = (YEAR, LATER_YEAR)[int(match[1]) - 1]
            numbers = sorted(n for (y, n) in self.senate.files if y == year)
            if not numbers:  # the second session has no menu yet
                return httpx.Response(302, headers={"location": "https://www.senate.gov/pagelayout/general/one_item_and_teasers/file_not_found.htm"}, request=request)
            lines = ""
            for n in numbers:
                roll = parse_senate_vote(self.senate.files[(year, n)]).roll
                yeas = self.menu_edits.get(n, {}).get("yeas", roll["yea_total"])
                lines += (
                    f"<vote><vote_number>{n:05d}</vote_number><vote_date>{roll['action_date'].day}-{roll['action_date'].strftime('%b')}</vote_date>"
                    f"<issue>x</issue><question>q</question><result>r</result><vote_tally><yeas>{yeas}</yeas><nays>{roll['nay_total']}</nays></vote_tally><title>t</title></vote>"
                )
            xml = f"<vote_summary><congress>997</congress><session>{match[1]}</session><congress_year>{year}</congress_year><votes>{lines}</votes></vote_summary>"
            return httpx.Response(200, content=xml.encode(), request=request)
        match = re.search(r"vote_997_1_(\d{5})\.xml$", url)
        assert match, url
        data = self.senate.files[(YEAR, int(match[1]))]
        return httpx.Response(
            200, headers={"content-length": str(len(data)), "last-modified": MODIFIED, "content-type": "text/xml"}, request=request
        )


def _sync_real_client(senate: FakeSenate, origin: _Origin) -> SenateVotesConnector:
    from datetime import date

    from opendiscourse_research.providers.senate import SenateVotes

    client = SenateVotes(send=origin, pace_seconds=0, sleep=lambda _s: None, today=lambda: date(2026, 9, 20))
    connector = SenateVotesConnector([CONGRESS], senate=client, downloader=senate.download, sleep=lambda _s: None)
    run_connector(connector)
    return connector


def test_the_real_client_lists_checks_and_feeds_the_connector_and_a_menu_tally_edit_is_reported(senate: FakeSenate) -> None:
    origin = _Origin(senate)

    clean = _sync_real_client(senate, origin)

    assert clean.result["partial"] is False and clean.result["disagreements_with_menu"] == [] and _roll_calls() == 3
    assert clean.result["files_listed"] == 3 and clean.result["downloaded"] == 3
    assert {m for m, _ in origin.requests} == {"GET", "HEAD"}  # the menu by GET, each file by HEAD
    assert _artifact(2)["metadata"]["remote_size"] == len(senate.files[(YEAR, 2)])

    _remove_rows()  # start again, so the file is loaded and cross-checked once more
    _add_people(PEOPLE)
    origin.menu_edits[2] = {"yeas": "77"}
    fresh = _sync_real_client(senate, origin)
    assert fresh.result["disagreements_with_menu"] == [_key(2)] and fresh.result["partial"] is True
    assert any("the menu lists 77 yeas, the file says 2" in p for p in fresh.result["problems"])


# -- the real downloader (ingestion.bulk.download) against a mock transport ------------------
class MockOrigin:
    """Serves the fake Senate's files over ``httpx.MockTransport``."""

    def __init__(self, senate: FakeSenate) -> None:
        self.senate = senate
        self.requests: list[str] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request.url.path)
        match = re.search(r"vote_(\d+)_(\d)_(\d{5})\.xml$", request.url.path)
        assert match, request.url.path
        year = (YEAR, LATER_YEAR)[int(match[2]) - 1]
        return httpx.Response(
            200, content=self.senate.files[(year, int(match[3]))], headers={"content-type": "text/xml"}, request=request
        )


def test_the_real_downloader_retains_exactly_the_served_bytes_under_the_official_file_name(
    senate: FakeSenate, monkeypatch: pytest.MonkeyPatch
) -> None:
    origin = MockOrigin(senate)
    monkeypatch.setattr(
        bulk, "client", lambda: httpx.Client(transport=httpx.MockTransport(origin.handler), follow_redirects=True)
    )
    connector = SenateVotesConnector([CONGRESS], senate=senate, sleep=lambda _s: None)  # type: ignore[arg-type]
    run_connector(connector)

    assert connector.result["partial"] is False and _roll_calls() == 3
    files = sorted(p for p in Path(settings.data_root).rglob("*") if p.is_file())
    assert [f.suffix for f in files] == [".xml"] * 3  # no .lock, no .part
    assert all(re.fullmatch(r"vote_997_1_0000[123]\.[0-9a-f]{64}\.xml", f.name) for f in files)
    assert all(f.parent.name == str(YEAR) and "senate_votes" in f.parts for f in files)
    for number in (1, 2, 3):
        artifact = _artifact(number)
        assert Path(artifact["local_path"]).read_bytes() == senate.files[(YEAR, number)]
    assert sorted(origin.requests) == [f"/legislative/LIS/roll_call_votes/vote9971/vote_997_1_0000{n}.xml" for n in (1, 2, 3)]
