"""Story 11.1 database contract: the House votes Connector, download -> inventory -> ingest.

A fake Clerk serves small synthetic roll calls for Congress 998 (calendar years 3783 and 3784), a
Congress that does not exist, so nothing here can touch real rows. Every test starts and ends with
those rows removed: CI runs every DB module against one shared database. The tests below cover the
spec's I/O matrix row by row.
"""

from __future__ import annotations

import hashlib
import os
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import patch

import httpx
import pytest
from alembic import command
from psycopg.types.json import Jsonb

from opendiscourse_research.catalog import sync_inventory
from opendiscourse_research.config import settings
from opendiscourse_research.db import _alembic_config, _engine, apply_migrations, connect
from opendiscourse_research.ingestion import bulk, house_votes, roll_call_votes
from opendiscourse_research.ingestion.billstatus_record import xml_to_record
from opendiscourse_research.ingestion.bulk import ArtifactSpec, register_local
from opendiscourse_research.ingestion.connector import Connector, run_connector
from opendiscourse_research.ingestion.house_vote_parse import HOUSE_LIST_TAGS
from opendiscourse_research.ingestion.house_votes import HouseVotesConnector, artifact_key
from opendiscourse_research.providers.clerk import ClerkError, ClerkNotFound, RemoteRoll, roll_url
from opendiscourse_research.repositories.legislation import register_artifact
from opendiscourse_research.repositories.votes import HOUSE_OCD_ORGANIZATION, house_external_id

CONGRESS = 998
YEAR = 3783  # 1789 + 2 * (998 - 1)
LATER_YEAR = YEAR + 1
MODIFIED = "Tue, 01 Sep 2020 12:06:52 GMT"
LATER = "Wed, 02 Sep 2020 12:06:52 GMT"
PEOPLE = {f"T998{n:03d}": f"Person {n}" for n in range(1, 6)}
OPENSTATES_KEY = "test-openstates-998"


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


_ROLLS = "(SELECT roll_call_id FROM core.roll_call WHERE jurisdiction = 'us' AND legislative_session = '998')"


def _remove_rows() -> None:
    """Delete everything Congress 998 and its test people created, children before parents."""
    with connect() as conn:
        for statement in (
            f"DELETE FROM fact.member_vote WHERE roll_call_id IN {_ROLLS}",
            f"DELETE FROM core.roll_call_party_total WHERE roll_call_id IN {_ROLLS}",
            f"DELETE FROM core.roll_call_source_record WHERE roll_call_id IN {_ROLLS}",
            "DELETE FROM core.roll_call WHERE jurisdiction = 'us' AND legislative_session = '998'",
            (
                "WITH gone AS (DELETE FROM core.person_identifier WHERE namespace = 'bioguide' "
                "AND external_id LIKE 'T998%' RETURNING person_id) "
                "DELETE FROM core.person WHERE person_id IN (SELECT person_id FROM gone)"
            ),
            "DELETE FROM core.legislative_session WHERE identifier = '998'",
            "DELETE FROM ingest.raw_payload WHERE source_url = 'https://test-998'",
            "DELETE FROM ingest.run WHERE parameters @> '{\"test998\": true}'",
            "DELETE FROM core.organization_identifier WHERE metadata @> '{\"test998\": true}'",
            "DELETE FROM core.organization WHERE metadata @> '{\"test998\": true}'",
            (
                "DELETE FROM ingest.run_target WHERE run_id IN (SELECT run_id FROM ingest.run "
                "WHERE dataset_id = 'congress.house_votes' AND parameters->'congresses' @> '[998]')"
            ),
            (
                "DELETE FROM ingest.run WHERE dataset_id = 'congress.house_votes' "
                "AND parameters->'congresses' @> '[998]'"
            ),
            "DELETE FROM ingest.artifact WHERE dataset_id = 'congress.house_votes' AND artifact_key LIKE 'house-roll-378%'",
            f"DELETE FROM ingest.artifact WHERE artifact_key = '{OPENSTATES_KEY}'",
        ):
            conn.execute(statement)
        conn.commit()


@pytest.fixture(autouse=True)
def _clean(
    catalog_database: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[None]:
    monkeypatch.setattr(settings, "data_root", str(tmp_path / "lake" / "raw"))
    monkeypatch.setattr(house_votes, "FIRST_CONGRESS", CONGRESS)
    monkeypatch.setattr(house_votes, "LAST_CONGRESS", CONGRESS)
    _remove_rows()
    _add_people(PEOPLE)
    yield
    _remove_rows()


def _add_people(bioguide_ids: dict[str, str]) -> None:
    with connect() as conn:
        for bioguide, name in bioguide_ids.items():
            person = conn.execute(
                "INSERT INTO core.person (full_name) VALUES (%s) RETURNING person_id", (name,)
            ).fetchone()
            conn.execute(
                "INSERT INTO core.person_identifier (person_id, namespace, external_id) "
                "VALUES (%s, 'bioguide', %s)",
                (person["person_id"], bioguide),
            )
        conn.commit()


def _one(sql: str, *params: object):
    with connect() as conn:
        row = conn.execute(sql, params or None).fetchone()
    assert row is not None
    return next(iter(row.values()))


def _rows(sql: str, *params: object) -> list[tuple]:
    with connect() as conn:
        return [tuple(r.values()) for r in conn.execute(sql, params or None).fetchall()]


# -- synthetic origin ---------------------------------------------------------
Votes = list[tuple[str | None, str]]  # (bioguide id or None, the word the Clerk printed)
DEFAULT_VOTES: Votes = [
    ("T998001", "Yea"),
    ("T998002", "Nay"),
    ("T998003", "Aye"),
    ("T998004", "Not Voting"),
    ("T998005", "Present"),
]


def _roll_xml(
    number: int,
    votes: Votes | None = None,
    *,
    year: int = YEAR,
    question: str = "On Passage",
    result: str = "Passed",
    claims: int | None = None,
    parties: tuple[str, ...] = ("Republican",),
    etz: str | None = None,
) -> str:
    votes = DEFAULT_VOTES if votes is None else votes
    yea = sum(w in {"Yea", "Aye"} for _, w in votes)
    nay = sum(w in {"Nay", "No"} for _, w in votes)
    present = sum(w == "Present" for _, w in votes)
    absent = sum(w == "Not Voting" for _, w in votes)
    by_party = "".join(
        f"<totals-by-party><party>{name}</party><yea-total>{yea}</yea-total><nay-total>{nay}</nay-total>"
        f"<present-total>{present}</present-total><not-voting-total>{absent}</not-voting-total></totals-by-party>\n"
        for name in parties
    )
    entries = "".join(
        "<recorded-vote><legislator "
        + (f'name-id="{b}" ' if b else "")
        + f'sort-field="P{i}" unaccented-name="P{i}" party="{"D" if i % 2 else "R"}" state="XX" '
        f'role="legislator">P{i}</legislator><vote>{word}</vote></recorded-vote>\n'
        for i, (b, word) in enumerate(votes)
    )
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rollcall-vote>
<vote-metadata>
<majority>R</majority>
<congress>{CONGRESS}</congress>
<session>1st</session>
<chamber>U.S. House of Representatives</chamber>
<rollcall-num>{claims or number}</rollcall-num>
<legis-num>H R {number}</legis-num>
<vote-question>{question}</vote-question>
<vote-type>YEA-AND-NAY</vote-type>
<vote-result>{result}</vote-result>
<action-date>{number}-Jan-{year}</action-date>
<action-time time-etz="{etz or f"14:{number:02d}"}">2:{number:02d} PM</action-time>
<vote-desc>Bill number {number}</vote-desc>
<vote-totals>
<totals-by-party-header><party-header>Party</party-header></totals-by-party-header>
{by_party}<totals-by-vote><total-stub>Totals</total-stub><yea-total>{yea}</yea-total><nay-total>{nay}</nay-total><present-total>{present}</present-total><not-voting-total>{absent}</not-voting-total></totals-by-vote>
</vote-totals>
</vote-metadata>
<vote-data>
{entries}</vote-data>
</rollcall-vote>"""


class FakeClerk:
    """Stands in for the Clerk: the listing, HEAD, and the download itself."""

    def __init__(self, tmp: Path, files: dict[tuple[int, int], str]) -> None:
        self.tmp = tmp
        self.files = {k: v.encode() for k, v in files.items()}
        self.modified: dict[tuple[int, int], str] = {}
        self.listed_extra: set[tuple[int, int]] = set()  # in the index but not served (vacated)
        self.downloads: list[str] = []
        self.heads = 0
        self.fail_downloads: set[str] = set()
        self.head_errors: set[tuple[int, int]] = set()  # a non-404 failure on HEAD
        self.listing: dict[int, list[int]] = {}  # replaces the listing of a year (a truncated page)

    def publish(self, year: int, number: int, xml: str, modified: str = LATER) -> None:
        self.files[(year, number)] = xml.encode()
        self.modified[(year, number)] = modified

    # ClerkHouseVotes surface
    def roll_numbers(self, year: int) -> list[int]:
        if year in self.listing:
            return self.listing[year]
        return sorted({n for (y, n) in [*self.files, *self.listed_extra] if y == year})

    def roll_info(self, year: int, number: int) -> RemoteRoll:
        self.heads += 1
        if (year, number) in self.head_errors:
            raise ClerkError(f"{number}: 503")
        if (year, number) not in self.files:
            raise ClerkNotFound(f"{number}: 404")
        return RemoteRoll(
            year,
            number,
            roll_url(year, number),
            len(self.files[(year, number)]),
            self.modified.get((year, number), MODIFIED),
        )

    # Downloader surface (what bulk.download does, without HTTP)
    def download(self, spec: ArtifactSpec, *, overwrite: bool = False) -> Path:
        self.downloads.append(spec.artifact_key)
        if spec.artifact_key in self.fail_downloads:
            raise httpx.ConnectError("connection reset")
        _, _, year, tail = spec.artifact_key.split("-")  # house-roll-<year>-<number>.xml
        source = self.tmp / f"{spec.artifact_key}.src"
        source.write_bytes(self.files[(int(year), int(tail.split(".")[0]))])
        return register_local(spec, source)


def _files(*numbers: int, year: int = YEAR, **kwargs: Any) -> dict[tuple[int, int], str]:
    return {(year, n): _roll_xml(n, year=year, **kwargs) for n in numbers}


@pytest.fixture
def clerk(tmp_path: Path) -> FakeClerk:
    return FakeClerk(tmp_path, _files(1, 2, 3))


def _sync(clerk: FakeClerk, **kwargs: Any) -> HouseVotesConnector:
    connector = HouseVotesConnector(
        [CONGRESS],
        clerk=clerk,  # type: ignore[arg-type]
        downloader=clerk.download,
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
        "SELECT status, code_version FROM ingest.run WHERE dataset_id = 'congress.house_votes' "
        "AND parameters->'congresses' @> '[998]' ORDER BY started_at DESC LIMIT 1"
    )[0]


def _roll(number: int, year: int = YEAR) -> dict:
    with connect() as conn:
        return conn.execute(
            "SELECT * FROM core.roll_call WHERE jurisdiction = 'us' AND legislative_session = '998' "
            "AND external_id = %s",
            (house_external_id(year, number),),
        ).fetchone()


def _votes(number: int, year: int = YEAR) -> dict[str, tuple]:
    """bioguide id -> (position, position_raw, party, state, name) for one roll call."""
    return {
        r[0]: r[1:]
        for r in _rows(
            "SELECT i.external_id, v.position, v.position_raw, v.party_at_vote, v.state_at_vote, v.name_at_vote "
            "FROM fact.member_vote v JOIN core.person_identifier i "
            "ON i.person_id = v.person_id AND i.namespace = 'bioguide' "
            "JOIN core.roll_call r ON r.roll_call_id = v.roll_call_id "
            "WHERE r.legislative_session = '998' AND r.external_id = %s",
            house_external_id(year, number),
        )
    }


def _roll_calls() -> int:
    return _one("SELECT count(*) AS n FROM core.roll_call WHERE legislative_session = '998'")


def _state() -> list[tuple]:
    """Everything loaded, without ids or timestamps: equal states mean equal loads."""
    return _rows(
        "SELECT r.external_id, r.occurred_at, r.question, r.result, r.vote_result, r.yea_total, "
        "r.legislative_number, s.record_sha256, s.entry_count, s.typed_count, "
        "(SELECT count(*) FROM fact.member_vote v WHERE v.roll_call_id = r.roll_call_id), "
        "(SELECT count(*) FROM core.roll_call_party_total p WHERE p.roll_call_id = r.roll_call_id) "
        "FROM core.roll_call r JOIN core.roll_call_source_record s USING (roll_call_id) "
        "WHERE r.legislative_session = '998' ORDER BY r.external_id"
    )


def _org(name: str, ocd: str | None) -> str:
    """An organization (with its OCD identifier when given); removed again by ``_remove_rows``."""
    with connect() as conn:
        org = conn.execute(
            "INSERT INTO core.organization (organization_type, name, metadata) VALUES ('lower', %s, %s) "
            "RETURNING organization_id",
            (name, Jsonb({"test998": True})),
        ).fetchone()
        if ocd:
            conn.execute(
                "INSERT INTO core.organization_identifier (organization_id, namespace, external_id, metadata) "
                "VALUES (%s, 'ocd', %s, %s)",
                (org["organization_id"], ocd, Jsonb({"test998": True})),
            )
        conn.commit()
    return str(org["organization_id"])


def _house_org_exists() -> bool:
    return bool(_rows("SELECT 1 FROM core.organization_identifier WHERE namespace = 'ocd' AND external_id = %s", HOUSE_OCD_ORGANIZATION))


def _openstates_roll(number: int, votes: dict[str, str], *, payload: bool = False, organization_id: str | None = None) -> str:
    """A roll call OpenStates created earlier, with its own (older, partial) votes."""
    art = register_artifact(
        "openstates.legislation", "https://v3.openstates.org/x", "virtual://openstates-998", OPENSTATES_KEY,
        content_type="application/json",
    )
    with connect() as conn:
        roll = conn.execute(
            "INSERT INTO core.roll_call (jurisdiction, legislative_session, chamber, external_id, "
            "occurred_at, question, result, metadata, ocd_id) VALUES ('us', '998', 'house', %s, "
            "'3783-01-01 00:00+00', 'On Passage (provider text)', 'fail', %s, 'ocd-vote/test-998') "
            "RETURNING roll_call_id",
            (house_external_id(YEAR, number), Jsonb({"source": "openstates"})),
        ).fetchone()
        if organization_id:
            conn.execute(
                "UPDATE core.roll_call SET organization_id = %s WHERE roll_call_id = %s",
                (organization_id, roll["roll_call_id"]),
            )
        payload_id = None
        if payload:
            run = conn.execute(
                "INSERT INTO ingest.run (dataset_id, mode, status, parameters) "
                "VALUES ('openstates.legislation', 'manual', 'succeeded', %s) RETURNING run_id",
                (Jsonb({"test998": True}),),
            ).fetchone()
            payload_id = conn.execute(
                "INSERT INTO ingest.raw_payload (run_id, source_url, http_status, checksum_sha256, payload) "
                "VALUES (%s, 'https://test-998', 200, 'test-998', '{}'::jsonb) RETURNING payload_id",
                (run["run_id"],),
            ).fetchone()["payload_id"]
        for bioguide, position in votes.items():
            conn.execute(
                "INSERT INTO fact.member_vote (roll_call_id, person_id, position, source_artifact_id, source_payload_id) "
                "SELECT %s, person_id, %s, %s, %s FROM core.person_identifier "
                "WHERE namespace = 'bioguide' AND external_id = %s",
                (roll["roll_call_id"], position, art["artifact_id"], payload_id, bioguide),
            )
        conn.commit()
    return str(roll["roll_call_id"])


# -- the workflow -------------------------------------------------------------
def test_house_votes_connector_satisfies_the_connector_protocol() -> None:
    assert isinstance(HouseVotesConnector(), Connector)


def test_it_refuses_a_congress_outside_the_supported_range(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(house_votes, "FIRST_CONGRESS", 108)
    monkeypatch.setattr(house_votes, "LAST_CONGRESS", 119)
    with pytest.raises(ValueError, match="108-119"):
        HouseVotesConnector([500])


def test_new_roll_call_is_downloaded_registered_and_loaded_with_every_field(clerk: FakeClerk) -> None:
    connector = _sync(clerk)

    assert clerk.downloads == [_key(1), _key(2), _key(3)]
    result = connector.result
    assert result["downloaded"] == 3 and result["roll_calls_inserted"] == 3 and result["partial"] is False
    assert result["member_votes_written"] == 15 and result["roll_calls_enriched_from_openstates"] == 0
    artifact = _artifact(2)
    xml = clerk.files[(YEAR, 2)]
    assert artifact["status"] == "loaded" and artifact["artifact_version"] == 1
    assert artifact["checksum_sha256"] == hashlib.sha256(xml).hexdigest()
    assert artifact["remote_url"] == roll_url(YEAR, 2)
    assert artifact["metadata"]["remote_size"] == len(xml)
    assert artifact["metadata"]["remote_last_modified"] == MODIFIED
    assert Path(artifact["local_path"]).read_bytes() == xml
    assert str(settings.data_root) in artifact["local_path"]
    # only the retained evidence stays in the lake: no lock or partial files beside it
    assert sorted(p.suffix for p in Path(settings.data_root).rglob("*") if p.is_file()) == [".xml"] * 3

    roll = _roll(2)
    assert roll["chamber"] == "house" and roll["metadata"] == {"source": "house_clerk"}
    assert (roll["roll_number"], roll["roll_year"], roll["congress_session"]) == (2, YEAR, "1st")
    assert (roll["legislative_number"], roll["vote_type"], roll["vote_result"]) == ("H R 2", "YEA-AND-NAY", "Passed")
    assert (roll["majority_party"], roll["vote_description"], roll["question"], roll["result"]) == (
        "R", "Bill number 2", "On Passage", "pass",
    )
    assert (roll["yea_total"], roll["nay_total"], roll["present_total"], roll["not_voting_total"]) == (2, 1, 1, 1)
    assert str(roll["action_date"]) == f"{YEAR}-01-02" and roll["action_time_etz"] == "14:02"
    assert roll["occurred_at"].astimezone(UTC) == datetime(YEAR, 1, 2, 19, 2, tzinfo=UTC)  # 14:02 EST
    assert roll["source_artifact_id"] == artifact["artifact_id"]
    assert roll["legislative_session_id"] is not None
    assert _rows("SELECT party, yea_total FROM core.roll_call_party_total WHERE roll_call_id = %s", roll["roll_call_id"]) == [("Republican", 2)]
    assert _votes(2) == {
        "T998001": ("yes", "Yea", "R", "XX", "P0"),
        "T998002": ("no", "Nay", "D", "XX", "P1"),
        "T998003": ("yes", "Aye", "R", "XX", "P2"),
        "T998004": ("not voting", "Not Voting", "D", "XX", "P3"),
        "T998005": ("other", "Present", "R", "XX", "P4"),
    }
    # the whole record, equal to the XML
    with connect() as conn:
        stored = conn.execute(
            "SELECT record, entry_count, typed_count, unresolved_bioguide_ids "
            "FROM core.roll_call_source_record WHERE source_artifact_id = %s",
            (artifact["artifact_id"],),
        ).fetchone()
    from xml.etree import ElementTree

    assert stored["record"] == xml_to_record(ElementTree.fromstring(xml), HOUSE_LIST_TAGS)
    assert (stored["entry_count"], stored["typed_count"], stored["unresolved_bioguide_ids"]) == (5, 5, [])
    # every fact resolves to a retained artifact and to the run
    assert _one(
        "SELECT count(*) AS n FROM fact.member_vote v JOIN core.roll_call r USING (roll_call_id) "
        "JOIN ingest.artifact a ON a.artifact_id = v.source_artifact_id "
        "WHERE r.legislative_session = '998' AND a.checksum_sha256 IS NOT NULL "
        "AND a.artifact_key LIKE 'house-roll-378%' AND a.metadata->>'run_id' IS NOT NULL"
    ) == 15
    status, code_version = _run_status()
    assert status == "succeeded" and code_version
    assert _rows(
        "SELECT t.target, t.coverage_key, t.rows_inserted, t.rows_updated, t.status FROM ingest.run_target t "
        "JOIN ingest.run r USING (run_id) WHERE r.dataset_id = 'congress.house_votes' "
        "AND r.parameters->'congresses' @> '[998]' ORDER BY 1"
    ) == [
        ("core.roll_call", "congress=998", 3, 0, "succeeded"),
        ("fact.member_vote", "congress=998", 15, 0, "succeeded"),
    ]


def test_unchanged_rerun_downloads_nothing_and_changes_nothing(clerk: FakeClerk) -> None:
    _sync(clerk)
    before = _state()
    versions = _one("SELECT count(*) AS n FROM ingest.artifact WHERE artifact_key LIKE 'house-roll-378%'")

    connector = _sync(clerk)

    assert clerk.downloads == [_key(1), _key(2), _key(3)]  # only the first run fetched bytes
    assert connector.result["downloaded"] == 0 and connector.result["reused"] == 3
    assert connector.result["roll_calls_loaded"] == 0 and connector.result["member_votes_written"] == 0
    assert _state() == before
    assert _one("SELECT count(*) AS n FROM ingest.artifact WHERE artifact_key LIKE 'house-roll-378%'") == versions
    assert _run_status()[0] == "succeeded"


def test_changed_origin_appends_a_version_and_replaces_the_old_rows_in_one_transaction(clerk: FakeClerk) -> None:
    _sync(clerk)
    roll_id = _roll(2)["roll_call_id"]
    old_artifact = _artifact(2)["artifact_id"]
    # a member drops out, another changes vote, the question is corrected
    clerk.publish(
        YEAR, 2,
        _roll_xml(2, [("T998001", "Nay"), ("T998002", "Nay"), ("T998003", "Aye")], question="On Passage, as Amended"),
    )

    connector = _sync(clerk)

    assert clerk.downloads.count(_key(2)) == 2 and clerk.downloads.count(_key(1)) == 1
    assert connector.result["downloaded"] == 1 and connector.result["reused"] == 2
    new_artifact = _artifact(2)
    assert new_artifact["artifact_version"] == 2 and new_artifact["artifact_id"] != old_artifact
    assert new_artifact["metadata"]["remote_last_modified"] == LATER
    assert _roll(2)["roll_call_id"] == roll_id  # same row, enriched again
    assert _roll(2)["question"] == "On Passage, as Amended" and _roll(2)["source_artifact_id"] == new_artifact["artifact_id"]
    assert _votes(2) == {
        "T998001": ("no", "Nay", "R", "XX", "P0"),
        "T998002": ("no", "Nay", "D", "XX", "P1"),
        "T998003": ("yes", "Aye", "R", "XX", "P2"),
    }  # no duplicates and nothing left from the old file
    assert _rows("SELECT source_artifact_id FROM core.roll_call_source_record WHERE roll_call_id = %s", roll_id) == [
        (new_artifact["artifact_id"],)
    ]
    assert connector.result["roll_calls_refreshed"] == 1 and connector.result["roll_calls_inserted"] == 0
    # the retained old bytes are still there: evidence is never deleted
    old = _rows("SELECT local_path FROM ingest.artifact WHERE artifact_id = %s", old_artifact)[0][0]
    assert Path(old).is_file()


def test_a_failed_refresh_leaves_the_old_rows_untouched(
    clerk: FakeClerk, monkeypatch: pytest.MonkeyPatch
) -> None:
    _sync(clerk)
    before, votes = _state(), _votes(2)
    clerk.publish(YEAR, 2, _roll_xml(2, [("T998001", "Nay")]))
    real = house_votes.save_house_roll_call

    def save_then_die(*args: Any, **kwargs: Any) -> Any:
        real(*args, **kwargs)  # the new rows and the deletes of the old ones are in the transaction ...
        raise RuntimeError("disk full")  # ... which now rolls back as a whole

    monkeypatch.setattr(house_votes, "save_house_roll_call", save_then_die)
    with pytest.raises(RuntimeError, match="disk full"):
        _sync(clerk)

    assert _state() == before and _votes(2) == votes
    assert _run_status()[0] == "failed"


def test_a_refreshed_file_that_no_longer_parses_is_reported_and_writes_nothing(clerk: FakeClerk) -> None:
    _sync(clerk)
    before = _state()
    clerk.files[(YEAR, 2)] = b"<html>Request Rejected</html>"
    clerk.modified[(YEAR, 2)] = LATER

    connector = _sync(clerk)

    assert connector.result["partial"] is True and connector.result["malformed"] == [_key(2)]
    assert _state() == before  # old rows stand
    assert _run_status()[0] == "partial"


def test_an_openstates_roll_call_is_enriched_in_place_not_duplicated(clerk: FakeClerk) -> None:
    # OpenStates has 2 of the file's 5 votes, one of them different, and one the file does not have
    roll_id = _openstates_roll(2, {"T998001": "no", "T998002": "no"}, payload=True)
    assert _one("SELECT count(*) AS n FROM fact.member_vote WHERE roll_call_id = %s AND source_payload_id IS NOT NULL", roll_id) == 2

    connector = _sync(clerk)

    assert _roll_calls() == 3  # 2 new + the existing one; none duplicated
    roll = _roll(2)
    assert str(roll["roll_call_id"]) == roll_id  # same identity
    assert roll["metadata"]["source"] == "openstates" and roll["ocd_id"] == "ocd-vote/test-998"
    assert roll["question"] == "On Passage" and roll["result"] == "pass"  # official evidence wins
    assert roll["occurred_at"].astimezone(UTC) == datetime(YEAR, 1, 2, 19, 2, tzinfo=UTC)
    assert (roll["roll_number"], roll["yea_total"], roll["vote_result"]) == (2, 2, "Passed")
    assert connector.result["roll_calls_enriched_from_openstates"] == 1 and connector.result["roll_calls_inserted"] == 2
    assert _votes(2)["T998001"] == ("yes", "Yea", "R", "XX", "P0")  # replaced by the official vote
    assert len(_votes(2)) == 5
    # a replaced provider vote keeps no pointer to the provider's payload beside the official artifact
    assert _one("SELECT count(*) AS n FROM fact.member_vote WHERE roll_call_id = %s AND source_payload_id IS NOT NULL", roll_id) == 0
    # every vote of that roll now points at the official artifact
    assert _one(
        "SELECT count(*) AS n FROM fact.member_vote WHERE roll_call_id = %s AND source_artifact_id = %s",
        roll_id, _artifact(2)["artifact_id"],
    ) == 5
    assert _rows(
        "SELECT target, rows_inserted, rows_updated FROM ingest.run_target t JOIN ingest.run r USING (run_id) "
        "WHERE r.dataset_id = 'congress.house_votes' AND r.parameters->'congresses' @> '[998]' "
        "AND target = 'core.roll_call'"
    ) == [("core.roll_call", 2, 1)]


def test_the_official_result_replaces_a_stale_provider_result_even_when_it_is_not_pass_or_fail(clerk: FakeClerk) -> None:
    roll_id = _openstates_roll(2, {})
    with connect() as conn:
        conn.execute("UPDATE core.roll_call SET result = 'pass' WHERE roll_call_id = %s", (roll_id,))
        conn.commit()
    clerk.publish(YEAR, 2, _roll_xml(2, result="Tabled"), modified=MODIFIED)

    _sync(clerk)

    roll = _roll(2)
    assert str(roll["roll_call_id"]) == roll_id
    assert roll["vote_result"] == "Tabled" and roll["result"] is None


def test_a_count_disagreement_with_existing_votes_is_reported_not_hidden(clerk: FakeClerk) -> None:
    # a provider vote by a person the official file does not list makes the stored yes-count differ
    _add_people({"T998009": "Extra"})
    _openstates_roll(2, {"T998009": "yes"})

    connector = _sync(clerk)

    assert connector.result["count_disagreements"] == 1
    assert connector.result["count_disagreement_examples"] == [
        {"roll": house_external_id(YEAR, 2), "official": [2, 1, 1], "stored": [3, 1, 1]}
    ]
    assert len(_votes(2)) == 6  # the provider's vote stays; nothing is wiped
    assert connector.result["partial"] is False  # reported, not a failure


def test_an_unknown_bioguide_id_is_reported_never_name_matched_and_retried_later(clerk: FakeClerk) -> None:
    clerk.publish(YEAR, 2, _roll_xml(2, [*DEFAULT_VOTES, ("T998999", "Yea")]), modified=MODIFIED)

    connector = _sync(clerk)

    assert set(_votes(2)) == set(PEOPLE)  # no row for T998999
    assert connector.result["unresolved_bioguide_ids"] == {"T998999": [_key(2)]}
    assert connector.result["partial"] is True and _run_status()[0] == "partial"
    assert _one("SELECT unresolved_bioguide_ids FROM core.roll_call_source_record s JOIN core.roll_call r USING (roll_call_id) "
                "WHERE r.external_id = %s", house_external_id(YEAR, 2)) == ["T998999"]
    assert _one("SELECT entry_count FROM core.roll_call_source_record s JOIN core.roll_call r USING (roll_call_id) "
                "WHERE r.external_id = %s", house_external_id(YEAR, 2)) == 6
    assert _rows(
        "SELECT t.status FROM ingest.run_target t JOIN ingest.run r USING (run_id) WHERE r.dataset_id = 'congress.house_votes' "
        "AND r.parameters->'congresses' @> '[998]' AND target = 'core.roll_call'"
    ) == [("partial",)]
    # a rerun still reports it (the record row does not hide it) and downloads nothing
    again = _sync(clerk)
    assert again.result["unresolved_bioguide_ids"] == {"T998999": [_key(2)]} and again.result["downloaded"] == 0
    # once the person is known, the rerun takes the vote and the run is clean, without any download
    _add_people({"T998999": "Late Arrival"})
    fixed = _sync(clerk)
    assert fixed.result["partial"] is False and fixed.result["unresolved_bioguide_ids"] == {}
    assert _votes(2)["T998999"][:2] == ("yes", "Yea") and clerk.downloads.count(_key(2)) == 1


def test_entries_without_a_name_id_stay_in_the_record_and_are_counted(clerk: FakeClerk) -> None:
    clerk.publish(YEAR, 2, _roll_xml(2, [*DEFAULT_VOTES, (None, "Nay")]), modified=MODIFIED)

    connector = _sync(clerk)

    assert connector.result["entries_without_bioguide_id"] == 1 and connector.result["partial"] is False
    assert len(_votes(2)) == 5
    row = _rows(
        "SELECT entry_count, typed_count, entries_without_id, jsonb_array_length(record->'vote-data'->'recorded-vote') "
        "FROM core.roll_call_source_record s JOIN core.roll_call r USING (roll_call_id) WHERE r.external_id = %s",
        house_external_id(YEAR, 2),
    )
    assert row == [(6, 5, 1, 6)]


def test_a_vacated_roll_the_index_lists_is_reported_and_is_not_an_error(clerk: FakeClerk) -> None:
    clerk.listed_extra = {(YEAR, 4)}

    connector = _sync(clerk)

    assert connector.result["not_published"] == [_key(4)]
    assert connector.result["partial"] is False and _roll_calls() == 3
    assert connector.result["files_listed"] == 4
    assert _run_status()[0] == "succeeded"


def test_a_killed_run_resumes_and_ends_equal_to_a_clean_load(
    clerk: FakeClerk, monkeypatch: pytest.MonkeyPatch
) -> None:
    real = house_votes.save_house_roll_call
    calls = {"n": 0}

    def die_on_third(*args: Any, **kwargs: Any) -> Any:
        calls["n"] += 1
        if calls["n"] == 3:
            raise RuntimeError("killed")
        return real(*args, **kwargs)

    monkeypatch.setattr(house_votes, "save_house_roll_call", die_on_third)
    with pytest.raises(RuntimeError, match="killed"):
        _sync(clerk, batch_size=1)
    assert _roll_calls() == 2 and _run_status()[0] == "failed"  # two committed batches survived
    assert _rows(
        "SELECT t.status, t.rows_inserted FROM ingest.run_target t JOIN ingest.run r USING (run_id) "
        "WHERE r.dataset_id = 'congress.house_votes' AND r.parameters->'congresses' @> '[998]' AND target = 'core.roll_call'"
    ) == [("partial", 2)]  # the ledger shows the real committed work
    monkeypatch.setattr(house_votes, "save_house_roll_call", real)

    resumed = _sync(clerk, batch_size=1)

    assert resumed.result["roll_calls_loaded"] == 1 and resumed.result["downloaded"] == 0
    resumed_state = _state()
    assert len(resumed_state) == 3
    _remove_rows()
    _add_people(PEOPLE)
    _sync(FakeClerk(clerk.tmp, {(YEAR, n): xml.decode() for (_, n), xml in clerk.files.items()}))
    assert _state() == resumed_state


def test_download_only_registers_the_bytes_and_a_later_sync_loads_without_refetching(clerk: FakeClerk) -> None:
    _sync(clerk, download_only=True)
    assert _roll_calls() == 0 and _artifact(1)["status"] == "downloaded"

    _sync(clerk)

    assert clerk.downloads == [_key(1), _key(2), _key(3)] and _roll_calls() == 3
    assert _artifact(1)["status"] == "loaded"


def test_a_file_that_is_not_the_roll_call_its_name_promises_is_skipped_and_reported(clerk: FakeClerk) -> None:
    clerk.publish(YEAR, 3, _roll_xml(3, claims=9), modified=MODIFIED)

    connector = _sync(clerk)

    assert connector.result["malformed"] == [_key(3)] and connector.result["partial"] is True
    assert _roll_calls() == 2 and any("roll 9" in p for p in connector.result["problems"])


def test_one_failed_download_is_reported_and_the_rerun_fetches_only_that_file(clerk: FakeClerk) -> None:
    clerk.fail_downloads = {_key(2)}

    connector = _sync(clerk)

    assert connector.result["partial"] is True and list(connector.result["failed"]) == [_key(2)]
    assert _roll_calls() == 2 and _run_status()[0] == "partial"
    clerk.fail_downloads = set()
    clerk.downloads.clear()

    fixed = _sync(clerk)

    assert clerk.downloads == [_key(2)] and fixed.result["partial"] is False and _roll_calls() == 3


def test_a_truncated_download_never_loads(clerk: FakeClerk) -> None:
    original = clerk.download

    def truncated(spec: ArtifactSpec, *, overwrite: bool = False) -> Path:
        path = original(spec, overwrite=overwrite)
        with path.open("r+b") as handle:  # cut the bytes after they were registered
            handle.truncate(10)
        return path

    connector = _sync_with(clerk, truncated)

    assert connector.result["partial"] is True and set(connector.result["failed"]) == {_key(1), _key(2), _key(3)}
    assert _roll_calls() == 0


def _sync_with(clerk: FakeClerk, downloader: Callable[..., Path], **kwargs: Any) -> HouseVotesConnector:
    connector = HouseVotesConnector(
        [CONGRESS], clerk=clerk, downloader=downloader, sleep=lambda _s: None, **kwargs  # type: ignore[arg-type]
    )
    run_connector(connector)
    return connector


def test_same_bytes_with_a_new_last_modified_keeps_the_version_and_reloads_nothing(clerk: FakeClerk) -> None:
    _sync(clerk)
    before = _state()
    clerk.modified[(YEAR, 2)] = LATER

    connector = _sync(clerk)

    assert connector.result["downloaded"] == 1 and connector.result["roll_calls_loaded"] == 0
    assert _artifact(2)["artifact_version"] == 1 and _artifact(2)["metadata"]["remote_last_modified"] == LATER
    assert _state() == before
    assert _artifact(2)["status"] == "loaded"


def test_a_second_sync_at_the_same_time_is_refused_at_once(clerk: FakeClerk) -> None:
    first = HouseVotesConnector([CONGRESS], clerk=clerk, downloader=clerk.download)  # type: ignore[arg-type]
    first._acquire_lock()
    try:
        with pytest.raises(RuntimeError, match="another sync-votes run"):
            _sync(clerk)
    finally:
        first._lock.close()
    assert _one("SELECT count(*) AS n FROM ingest.run WHERE dataset_id = 'congress.house_votes' "
                "AND parameters->'congresses' @> '[998]'") == 0


def test_the_openstates_key_form_is_year_and_roll_number() -> None:
    # verified live 2026-09-20 on five rolls: us-2024-lower-28, us-2023-lower-100, us-2023-lower-500,
    # us-2024-lower-98 and us-2025-lower-10 equal the Clerk's roll of that calendar year and number
    assert house_external_id(2024, 28) == "us-2024-lower-28"
    assert artifact_key(2024, 28) == "house-roll-2024-028.xml"
    assert artifact_key(2007, 1186) == "house-roll-2007-1186.xml"


def test_the_migration_refuses_to_downgrade_while_official_rows_exist(clerk: FakeClerk) -> None:
    _sync(clerk)
    rows = _one("SELECT count(*) AS n FROM core.roll_call_source_record")

    with pytest.raises(RuntimeError, match=rf"core\.roll_call_source_record holds {rows} rows"):
        command.downgrade(_alembic_config(), "b7e4c2a19d63")

    assert _one("SELECT version_num AS v FROM alembic_version") == "c4e8a1b93d27"
    assert _roll_calls() == 3 and len(_votes(2)) == 5  # nothing was dropped


# -- review follow-ups ----------------------------------------------------------
def test_a_disagreement_only_in_not_voting_is_flagged(clerk: FakeClerk) -> None:
    # yes and no counts stay equal to the file (2 and 1); only not-voting differs (2 stored, 1 official)
    _add_people({"T998009": "Extra"})
    _openstates_roll(2, {"T998009": "not voting"})

    connector = _sync(clerk)

    assert connector.result["count_disagreements"] == 1
    assert connector.result["count_disagreement_examples"] == [
        {"roll": house_external_id(YEAR, 2), "official": [2, 1, 1], "stored": [2, 1, 2]}
    ]


def test_new_roll_calls_link_to_the_house_organization_and_an_existing_link_is_kept(clerk: FakeClerk) -> None:
    house = _org("House", HOUSE_OCD_ORGANIZATION)
    other = _org("Some other body", "ocd-organization/test-998")
    _openstates_roll(2, {"T998001": "no"}, organization_id=other)

    connector = _sync(clerk)

    assert str(_roll(1)["organization_id"]) == house and str(_roll(3)["organization_id"]) == house
    assert str(_roll(2)["organization_id"]) == other  # the provider's row keeps what it had
    assert not any("organization" in p for p in connector.result["problems"])


def test_a_missing_house_organization_is_reported_and_the_roll_calls_still_load(clerk: FakeClerk) -> None:
    if _house_org_exists():
        pytest.skip("this database already has the House organization")

    connector = _sync(clerk)

    assert any("House organization" in p and HOUSE_OCD_ORGANIZATION in p for p in connector.result["problems"])
    assert _roll(1)["organization_id"] is None and _roll_calls() == 3


def test_the_capacity_gate_stops_before_any_download(clerk: FakeClerk) -> None:
    refusal = {
        "approved": False,
        "reason": "insufficient capacity",
        "path": "/x",
        "peak_required_bytes": 10,
        "filesystem_free_bytes": 1,
    }
    with (
        patch.object(roll_call_votes, "storage_preview", return_value=refusal),
        pytest.raises(RuntimeError, match="capacity gate"),
    ):
        _sync(clerk)
    assert clerk.downloads == [] and _roll_calls() == 0 and _run_status()[0] == "failed"


def test_a_non_404_clerk_error_on_one_roll_is_failed_not_unpublished_and_a_rerun_picks_it_up(clerk: FakeClerk) -> None:
    clerk.head_errors = {(YEAR, 2)}

    connector = _sync(clerk)

    assert list(connector.result["failed"]) == [_key(2)] and connector.result["not_published"] == []
    assert connector.result["partial"] is True and _run_status()[0] == "partial"
    assert _roll_calls() == 2 and clerk.downloads == [_key(1), _key(3)]
    clerk.head_errors = set()

    fixed = _sync(clerk)

    assert fixed.result["partial"] is False and _roll_calls() == 3
    assert clerk.downloads == [_key(1), _key(3), _key(2)]  # only the missing one was fetched


def test_a_damaged_retained_file_is_refetched_but_never_overwritten_and_is_reported(clerk: FakeClerk) -> None:
    _sync(clerk)
    before = _state()
    path = Path(_artifact(2)["local_path"])
    path.write_bytes(path.read_bytes()[:10])  # damaged evidence

    connector = _sync(clerk)

    # the damage is seen (the file is fetched again) ...
    assert clerk.downloads.count(_key(2)) == 2
    # ... but retained bytes are evidence: never replaced, so this file is reported and the run is partial
    assert list(connector.result["failed"]) == [_key(2)] and connector.result["partial"] is True
    assert path.read_bytes()[:10] == path.read_bytes() and len(path.read_bytes()) == 10
    assert _state() == before  # the loaded rows are untouched


def test_a_deleted_retained_file_is_fetched_again_and_then_loaded(clerk: FakeClerk) -> None:
    _sync(clerk, download_only=True)
    Path(_artifact(3)["local_path"]).unlink()

    connector = _sync(clerk)

    assert clerk.downloads.count(_key(3)) == 2 and clerk.downloads.count(_key(1)) == 1
    assert _roll_calls() == 3 and connector.result["partial"] is False
    assert Path(_artifact(3)["local_path"]).read_bytes() == clerk.files[(YEAR, 3)]


def test_a_registered_file_with_no_recorded_origin_state_is_verified_by_downloading(clerk: FakeClerk) -> None:
    source = clerk.tmp / "legacy.xml"
    source.write_bytes(clerk.files[(YEAR, 2)])
    register_local(
        ArtifactSpec("congress.house_votes", _key(2), roll_url(YEAR, 2), f"{YEAR}/roll002.xml", metadata={}), source
    )
    assert "remote_size" not in _artifact(2)["metadata"]

    connector = _sync(clerk)

    assert clerk.downloads.count(_key(2)) == 1  # never trusted, fetched once
    assert _artifact(2)["metadata"]["remote_size"] == len(clerk.files[(YEAR, 2)])
    assert _artifact(2)["artifact_version"] == 1 and _roll_calls() == 3 and connector.result["partial"] is False


def test_a_refresh_that_changes_the_party_set_leaves_no_stale_party_row(clerk: FakeClerk) -> None:
    clerk.publish(YEAR, 2, _roll_xml(2, parties=("Republican", "Democratic")), modified=MODIFIED)
    _sync(clerk)
    roll_id = _roll(2)["roll_call_id"]
    parties = "SELECT party FROM core.roll_call_party_total WHERE roll_call_id = %s ORDER BY 1"
    assert _rows(parties, roll_id) == [("Democratic",), ("Republican",)]
    clerk.publish(YEAR, 2, _roll_xml(2, parties=("Republican", "Independent")))

    _sync(clerk)

    assert _rows(parties, roll_id) == [("Independent",), ("Republican",)]


def test_a_truncated_listing_is_reported_as_unlisted_and_the_run_is_partial(clerk: FakeClerk) -> None:
    clerk.listing = {YEAR: [1, 3]}  # roll 2 exists, but the index page that lists it was cut

    connector = _sync(clerk)

    assert connector.result["unlisted"] == {YEAR: [2]} and connector.result["partial"] is True
    assert _run_status()[0] == "partial" and _roll_calls() == 2
    clerk.listing = {}

    fixed = _sync(clerk)

    assert fixed.result["unlisted"] == {} and fixed.result["partial"] is False and _roll_calls() == 3


def test_a_year_with_no_roll_calls_yet_does_not_abort_the_sync(clerk: FakeClerk) -> None:
    assert clerk.roll_numbers(LATER_YEAR) == []  # the second year of the Congress has nothing yet

    connector = _sync(clerk)

    assert connector.result["partial"] is False and connector.result["files_listed"] == 3 and _roll_calls() == 3


def test_an_unusable_time_and_an_odd_result_are_loaded_but_counted_in_the_result(clerk: FakeClerk) -> None:
    clerk.publish(YEAR, 2, _roll_xml(2, etz="soon", result="Tabled"), modified=MODIFIED)

    connector = _sync(clerk)

    assert connector.result["partial"] is False and _roll_calls() == 3
    assert connector.result["parse_problems"] == {
        "result_not_normalized": {"count": 1, "examples": [_key(2)]},
        "time_unusable": {"count": 1, "examples": [_key(2)]},
    }
    assert any(p.startswith("time_unusable: 1") for p in connector.result["problems"])
    roll = _roll(2)
    assert roll["occurred_at"] is None and roll["action_time_etz"] == "soon" and roll["vote_result"] == "Tabled"
    assert roll["result"] is None


# -- the real downloader (ingestion.bulk.download) against a mock transport ------------------
class MockOrigin:
    """Serves the fake Clerk's files over ``httpx.MockTransport``, honouring Range like a real server."""

    def __init__(self, clerk: FakeClerk) -> None:
        self.clerk = clerk
        self.requests: list[tuple[str, str | None]] = []
        self.status: int | None = None  # force an error status on GET

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append((request.url.path, request.headers.get("range")))
        if self.status:
            return httpx.Response(self.status, request=request)
        year, name = request.url.path.split("/")[-2:]
        data = self.clerk.files[(int(year), int(name[4:].split(".")[0]))]
        if (rng := request.headers.get("range")):
            start = int(rng.split("=")[1].rstrip("-"))
            return httpx.Response(206, content=data[start:], headers={"content-type": "text/xml"}, request=request)
        return httpx.Response(200, content=data, headers={"content-type": "text/xml"}, request=request)


@pytest.fixture
def real_download(clerk: FakeClerk, monkeypatch: pytest.MonkeyPatch) -> MockOrigin:
    origin = MockOrigin(clerk)
    monkeypatch.setattr(
        bulk, "client", lambda: httpx.Client(transport=httpx.MockTransport(origin.handler), follow_redirects=True)
    )
    return origin


def _sync_real(clerk: FakeClerk) -> HouseVotesConnector:
    connector = HouseVotesConnector([CONGRESS], clerk=clerk, sleep=lambda _s: None)  # type: ignore[arg-type]
    run_connector(connector)
    return connector


def _lake_files() -> list[Path]:
    return sorted(p for p in Path(settings.data_root).rglob("*") if p.is_file())


def _current(number: int) -> dict:
    with connect() as conn:
        return conn.execute(
            "SELECT artifact_version, checksum_sha256, local_path FROM ingest.current_artifact WHERE artifact_key = %s",
            (_key(number),),
        ).fetchone()


def test_the_real_downloader_retains_exactly_the_served_bytes_and_leaves_nothing_else(
    clerk: FakeClerk, real_download: MockOrigin
) -> None:
    connector = _sync_real(clerk)

    assert connector.result["partial"] is False and _roll_calls() == 3
    files = _lake_files()
    assert [f.suffix for f in files] == [".xml"] * 3  # no .lock, no .part
    for number in (1, 2, 3):
        artifact = _artifact(number)
        assert Path(artifact["local_path"]).read_bytes() == clerk.files[(YEAR, number)]
        assert artifact["checksum_sha256"] == hashlib.sha256(clerk.files[(YEAR, number)]).hexdigest()
    assert all(rng is None for _, rng in real_download.requests)


def test_a_stale_part_file_is_not_resumed_onto_a_changed_file_and_the_old_version_stays_intact(
    clerk: FakeClerk, real_download: MockOrigin
) -> None:
    _sync_real(clerk)
    old = _current(2)
    old_bytes = Path(old["local_path"]).read_bytes()
    clerk.publish(YEAR, 2, _roll_xml(2, [("T998001", "Nay"), ("T998002", "Nay")]))
    new_bytes = clerk.files[(YEAR, 2)]
    stale = Path(settings.data_root) / "congress" / "house_votes" / str(YEAR) / "roll002.xml.part"
    stale.write_bytes(old_bytes[:40])  # a partial from before the file changed
    real_download.requests.clear()

    connector = _sync_real(clerk)

    assert connector.result["failed"] == {} and connector.result["downloaded"] == 1
    assert all(rng is None for _, rng in real_download.requests)  # never asked to resume
    new = _current(2)
    assert new["artifact_version"] == 2 and Path(new["local_path"]).read_bytes() == new_bytes
    assert new["checksum_sha256"] == hashlib.sha256(new_bytes).hexdigest()
    # the old version's file and checksum are still there, byte for byte
    with connect() as conn:
        first = conn.execute(
            "SELECT checksum_sha256, local_path FROM ingest.artifact WHERE artifact_key = %s AND artifact_version = 1",
            (_key(2),),
        ).fetchone()
    assert first["checksum_sha256"] == old["checksum_sha256"] == hashlib.sha256(old_bytes).hexdigest()
    assert Path(first["local_path"]).read_bytes() == old_bytes and first["local_path"] != new["local_path"]
    assert not stale.exists() and all(f.suffix == ".xml" for f in _lake_files())  # no .part, no .lock
    assert set(_votes(2)) == {"T998001", "T998002"}


def test_a_failed_refresh_keeps_the_old_version_and_rows_and_a_rerun_completes_it(
    clerk: FakeClerk, real_download: MockOrigin
) -> None:
    _sync_real(clerk)
    old, before, votes = _current(2), _state(), _votes(2)
    clerk.publish(YEAR, 2, _roll_xml(2, [("T998001", "Nay")]))
    real_download.status = 503

    connector = _sync_real(clerk)

    assert list(connector.result["failed"]) == [_key(2)] and connector.result["partial"] is True
    assert _current(2) == old  # the verified old version is still the current one
    assert Path(old["local_path"]).is_file() and _state() == before and _votes(2) == votes
    assert all(f.suffix == ".xml" for f in _lake_files())
    real_download.status = None

    fixed = _sync_real(clerk)

    assert fixed.result["partial"] is False and fixed.result["failed"] == {}
    assert _current(2)["artifact_version"] == 2 and set(_votes(2)) == {"T998001"}
    assert Path(old["local_path"]).is_file()
