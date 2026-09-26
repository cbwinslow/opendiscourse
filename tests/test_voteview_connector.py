"""Voteview: download the three files from a fake origin and load them.

Nothing here contacts voteview.com. Every test removes the rows it wrote: CI runs
database tests against one shared database. Congress 998 is not a real Congress.
"""

from __future__ import annotations

import csv
import io
import json
import os
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest
from alembic import command
from typer.testing import CliRunner

from opendiscourse_research.catalog import sync_inventory
from opendiscourse_research.cli import app
from opendiscourse_research.config import settings
from opendiscourse_research.db import (
    _alembic_config,
    _engine,
    apply_migrations,
    connect,
)
from opendiscourse_research.ingestion import voteview as voteview_module
from opendiscourse_research.ingestion.connector import run_connector
from opendiscourse_research.ingestion.voteview import (
    VoteviewConnector,
    parse_voteview_files,
)
from opendiscourse_research.providers.voteview import (
    MEMBERS,
    PARTIES,
    ROLLCALLS,
    VOTES,
    VoteviewClient,
    file_url,
)
from opendiscourse_research.repositories.names import resolve_names
from opendiscourse_research.repositories.voteview import publish_voteview

ORIGIN = "https://example.test/voteview"
MODIFIED = "Tue, 22 Sep 2026 06:18:49 GMT"
LATER = "Wed, 23 Sep 2026 06:18:49 GMT"
HEAD = "e8c2a9d14b59"
CONGRESS = 998

MEMBER_FIELDS = (
    "congress",
    "chamber",
    "icpsr",
    "state_icpsr",
    "district_code",
    "state_abbrev",
    "party_code",
    "occupancy",
    "last_means",
    "bioname",
    "bioguide_id",
    "born",
    "died",
    "nominate_dim1",
    "nominate_dim2",
    "nominate_log_likelihood",
    "nominate_geo_mean_probability",
    "nominate_number_of_votes",
    "nominate_number_of_errors",
    "conditional",
    "nokken_poole_dim1",
    "nokken_poole_dim2",
    "future_field",
)
PARTY_FIELDS = (
    "congress",
    "chamber",
    "party_code",
    "party_name",
    "n_members",
    "nominate_dim1_median",
    "nominate_dim2_median",
    "nominate_dim1_mean",
    "nominate_dim2_mean",
)
ROLL_FIELDS = (
    "congress",
    "chamber",
    "rollnumber",
    "date",
    "session",
    "clerk_rollnumber",
    "majority_requirement",
    "yea_count",
    "nay_count",
    "nominate_mid_1",
    "nominate_mid_2",
    "nominate_spread_1",
    "nominate_spread_2",
    "nominate_log_likelihood",
    "bill_number",
    "vote_result",
    "vote_desc",
    "vote_question",
    "dtl_desc",
    "issue_codes",
    "peltzman_codes",
    "clausen_codes",
    "crs_policy_area",
    "crs_subjects",
    "congress_url",
    "source_documents",
)


def _csv(fields: tuple[str, ...], rows: list[dict[str, object]]) -> bytes:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fields, lineterminator="\n", extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({field: "" if row.get(field) is None else row.get(field) for field in fields})
    return buffer.getvalue().encode()


def _member(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "congress": CONGRESS,
        "chamber": "House",
        "icpsr": 998001,
        "state_icpsr": 1,
        "district_code": 1,
        "state_abbrev": "CT",
        "party_code": 100,
        "occupancy": 0,
        "last_means": 1,
        "bioname": "LINKED, Ann",
        "bioguide_id": "V998001",
        "born": 1736.0,
        "died": "",
        "nominate_dim1": 0.1,
        "nominate_dim2": -0.2,
        "nominate_log_likelihood": -1.5,
        "nominate_geo_mean_probability": 0.8,
        "nominate_number_of_votes": 10,
        "nominate_number_of_errors": 1,
        "conditional": "",
        "nokken_poole_dim1": 0.3,
        "nokken_poole_dim2": -0.4,
        "future_field": "kept",
    }
    row.update(overrides)
    return row


def _party(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "congress": CONGRESS,
        "chamber": "House",
        "party_code": 100,
        "party_name": "Democrat",
        "n_members": 10,
        "nominate_dim1_median": 0.2,
        "nominate_dim2_median": "",
        "nominate_dim1_mean": 0.25,
        "nominate_dim2_mean": "",
    }
    row.update(overrides)
    return row


def _roll(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {field: None for field in ROLL_FIELDS}
    row.update(
        {
            "congress": CONGRESS,
            "chamber": "Senate",
            "rollnumber": 897,
            "date": "2026-09-17",
            "session": 2,
            "clerk_rollnumber": 238,
            "majority_requirement": "1/2",
            "yea_count": 49,
            "nay_count": 45,
            "vote_question": "On the Nomination",
            "vote_result": "Nomination Confirmed",
            "issue_codes": ["Tariffs"],
            "source_documents": ["note"],
            "future_field": 1,
        }
    )
    row.update(overrides)
    return row


def _files(
    members: list[dict[str, object]] | None = None,
    rolls: list[dict[str, object]] | None = None,
    parties: list[dict[str, object]] | None = None,
) -> dict[str, bytes]:
    members = [_member(), _member(chamber="President", icpsr=998009, bioguide_id="", bioname="PRESIDENT, Pat", state_abbrev="USA")] if members is None else members
    rolls = [
        _roll(),
        _roll(chamber="House", rollnumber=1, session=1, clerk_rollnumber=7, vote_question="On Passage"),
        _roll(
            chamber="House",
            rollnumber=2,
            session=1,
            clerk_rollnumber=None,
            vote_question="No Clerk",
        ),
        _roll(
            chamber="Senate",
            rollnumber=50,
            session=2,
            clerk_rollnumber=None,
            vote_question="Senate No Clerk",
        ),
        _roll(
            chamber="Senate",
            rollnumber=12,
            session=3,
            clerk_rollnumber=238,
            vote_question="Wrong Session",
        ),
    ] if rolls is None else rolls
    parties = [_party()] if parties is None else parties
    return {
        MEMBERS: _csv(MEMBER_FIELDS, members),
        ROLLCALLS: json.dumps(rolls).encode(),
        PARTIES: _csv(PARTY_FIELDS, parties),
    }


class _Origin:
    """Serves the three files, or fails, without leaving the machine."""

    def __init__(self, files: dict[str, bytes]) -> None:
        self.files = files
        self.modified = dict.fromkeys(files, MODIFIED)
        self.calls: list[tuple[str, str]] = []
        self.fail_get = False

    def transport(self, request: httpx.Request) -> httpx.Response:
        if request.headers.get("accept-encoding") != "identity":
            return httpx.Response(400, content=b"encoding")
        name = request.url.path.rsplit("/", 1)[-1]
        self.calls.append((request.method, name))
        if name not in self.files:
            return httpx.Response(404)
        body = self.files[name]
        headers = {"content-length": str(len(body)), "last-modified": self.modified[name]}
        if request.method == "HEAD":
            return httpx.Response(200, headers=headers)
        if self.fail_get:
            return httpx.Response(500)
        return httpx.Response(200, content=body, headers=headers)


def _remove_rows() -> None:
    with connect() as conn:
        for statement in (
            "DELETE FROM core.person_name_source WHERE dataset_id = 'congress.voteview'",
            "DELETE FROM core.voteview_member",
            "DELETE FROM core.voteview_roll_call",
            "DELETE FROM core.voteview_party",
            "DELETE FROM core.roll_call WHERE external_id LIKE 'us-voteview-test-%'",
            (
                "DELETE FROM core.person_identifier WHERE "
                "(namespace = 'bioguide' AND external_id LIKE 'V998%') "
                "OR (namespace = 'icpsr' AND external_id IN "
                "('998001', '998002', '998003', '998004', '998009'))"
            ),
            (
                "DELETE FROM core.person WHERE full_name IN "
                "('Database Ann', 'Database Unknown', 'Bioguide Only Bea', 'Bioguide Only Cam') "
                "AND NOT EXISTS ("
                "SELECT 1 FROM core.person_identifier i WHERE i.person_id = core.person.person_id)"
            ),
            (
                "DELETE FROM ingest.run_target WHERE run_id IN "
                "(SELECT run_id FROM ingest.run WHERE dataset_id = 'congress.voteview')"
            ),
            "DELETE FROM ingest.run WHERE dataset_id = 'congress.voteview'",
            "DELETE FROM ingest.artifact WHERE dataset_id = 'congress.voteview'",
        ):
            conn.execute(statement)
        conn.commit()


@pytest.fixture(scope="module")
def catalog_database() -> Iterator[None]:
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


@pytest.fixture(autouse=True)
def _clean(catalog_database: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setattr(settings, "data_root", str(tmp_path / "lake" / "raw"))
    _remove_rows()
    yield
    _remove_rows()


def _rows(sql: str, params: tuple[object, ...] = ()) -> list[tuple]:
    with connect() as conn:
        return [tuple(row.values()) for row in conn.execute(sql, params).fetchall()]


def _add_bioguide(bioguide: str, name: str) -> None:
    with connect() as conn:
        person = conn.execute(
            "INSERT INTO core.person (full_name) VALUES (%s) RETURNING person_id",
            (name,),
        ).fetchone()
        conn.execute(
            "INSERT INTO core.person_identifier (person_id, namespace, external_id) "
            "VALUES (%s, 'bioguide', %s)",
            (person["person_id"], bioguide),
        )
        conn.commit()


def _add_person(bioguide: str, icpsr: str, name: str) -> None:
    with connect() as conn:
        person = conn.execute(
            "INSERT INTO core.person (full_name) VALUES (%s) RETURNING person_id",
            (name,),
        ).fetchone()
        conn.execute(
            "INSERT INTO core.person_identifier (person_id, namespace, external_id) VALUES "
            "(%s, 'bioguide', %s), (%s, 'icpsr', %s)",
            (person["person_id"], bioguide, person["person_id"], icpsr),
        )
        conn.commit()


def _add_roll(
    external_id: str,
    chamber: str,
    number: int,
    session: str,
    question: str,
    result: str,
) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT INTO core.roll_call ("
            "jurisdiction, legislative_session, chamber, external_id, roll_number, "
            "congress_session, question, result) VALUES "
            "('us', %s, %s, %s, %s, %s, %s, %s)",
            (str(CONGRESS), chamber, external_id, number, session, question, result),
        )
        conn.commit()


def _official() -> None:
    # 238 is the 2nd-session clerk number. 897 is Voteview's own roll number and must not link.
    _add_roll("us-voteview-test-senate-238", "senate", 238, "2nd", "Official Senate Question", "pass")
    _add_roll("us-voteview-test-senate-897", "senate", 897, "2nd", "Voteview Own Number", "fail")
    _add_roll("us-voteview-test-senate-50", "senate", 50, "2nd", "Senate Missing Clerk", "pass")
    _add_roll("us-voteview-test-house-7", "house", 7, "1st", "Official House Question", "pass")
    _add_roll("us-voteview-test-house-2", "house", 2, "1st", "Must Stay", "fail")


def _sync(origin: _Origin) -> VoteviewConnector:
    client = httpx.Client(transport=httpx.MockTransport(origin.transport))
    connector = VoteviewConnector(origin=ORIGIN, http=client)
    run_connector(connector)
    return connector


def _people() -> int:
    return _rows("SELECT count(*) FROM core.person")[0][0]


def test_individual_votes_are_refused_before_any_request() -> None:
    calls: list[str] = []

    def transport(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        return httpx.Response(200, content=b"nope")

    client = VoteviewClient(http=httpx.Client(transport=httpx.MockTransport(transport)))
    with pytest.raises(ValueError, match="HSall_votes.csv"):
        client.download(VOTES, 1)
    with pytest.raises(ValueError, match="HSall_votes.csv"):
        file_url(VOTES)
    assert calls == []


def test_happy_path_links_people_and_votes_without_changing_names_or_official_votes() -> None:
    _add_person("V998001", "998001", "Database Ann")
    _official()
    before_people = _people()
    origin = _Origin(_files())
    first = _sync(origin)
    assert first.result["partial"] is False
    assert first.result["unlinked_members"] == 0
    assert first.result["unlinked_presidents"] == 1
    assert first.result["bioguide_disagreements"] == 0
    assert first.result["votes_linked"] == 2
    assert first.result["votes_no_clerk_number"] == 2
    assert first.result["votes_unmatched"] == 1
    assert first.result["votes_ambiguous"] == 0
    assert first.result["members_inserted"] == 2
    assert first.result["parties_inserted"] == 1
    assert _rows("SELECT count(*) FROM core.voteview_party") == [(1,)]
    assert _people() == before_people
    linked = _rows(
        "SELECT chamber, (person_id IS NOT NULL) AS linked, bioname, "
        "record->>'future_field' AS extra "
        "FROM core.voteview_member ORDER BY chamber"
    )
    assert linked == [("house", True, "LINKED, Ann", "kept"), ("president", False, "PRESIDENT, Pat", "kept")]
    notes = _rows(
        "SELECT name_kind, source_vintage, full_name FROM core.person_name_source "
        "WHERE dataset_id = 'congress.voteview'"
    )
    assert notes == [("voteview", "0998", "LINKED, Ann")]
    shown = _rows(
        "SELECT full_name, name_source_id IS NULL FROM core.person WHERE full_name = 'Database Ann'"
    )
    assert shown == [("Database Ann", True)]
    links = _rows(
        "SELECT v.chamber, v.rollnumber, v.clerk_rollnumber, v.session, rc.external_id "
        "FROM core.voteview_roll_call v "
        "LEFT JOIN core.roll_call rc ON rc.roll_call_id = v.roll_call_id "
        "ORDER BY v.chamber, v.rollnumber"
    )
    assert links == [
        ("house", 1, 7, 1, "us-voteview-test-house-7"),
        ("house", 2, None, 1, None),
        ("senate", 12, 238, 3, None),
        ("senate", 50, None, 2, None),
        ("senate", 897, 238, 2, "us-voteview-test-senate-238"),
    ]
    official = _rows(
        "SELECT external_id, question, result FROM core.roll_call "
        "WHERE external_id LIKE 'us-voteview-test-%%' ORDER BY external_id"
    )
    assert official == [
        ("us-voteview-test-house-2", "Must Stay", "fail"),
        ("us-voteview-test-house-7", "Official House Question", "pass"),
        ("us-voteview-test-senate-238", "Official Senate Question", "pass"),
        ("us-voteview-test-senate-50", "Senate Missing Clerk", "pass"),
        ("us-voteview-test-senate-897", "Voteview Own Number", "fail"),
    ]
    assert _rows(
        "SELECT count(*) FROM catalog.name_display WHERE entity = 'person' AND name_kind = 'voteview'"
    ) == [(0,)]
    with connect() as conn:
        person = conn.execute(
            "SELECT person_id FROM core.person WHERE full_name = 'Database Ann'"
        ).fetchone()["person_id"]
        report = resolve_names(conn, "person", dry_run=True)
    assert person not in {row["person_id"] for row in report["rows"]}
    assert _rows(
        "SELECT full_name FROM core.person WHERE full_name = 'Database Ann'"
    ) == [("Database Ann",)]
    ids = _rows(
        "SELECT voteview_member_id::text FROM core.voteview_member ORDER BY chamber"
    )
    origin.calls.clear()
    second = _sync(origin)
    assert second.result["downloaded"] == []
    assert second.result["members_inserted"] == 0
    assert second.result["members_deleted"] == 0
    assert second.result["roll_calls_inserted"] == 0
    assert second.result["parties_inserted"] == 0
    assert second.result["names_inserted"] == 0
    assert second.result["names_updated"] == 0
    assert [method for method, _name in origin.calls] == ["HEAD", "HEAD", "HEAD"]
    assert ids == _rows(
        "SELECT voteview_member_id::text FROM core.voteview_member ORDER BY chamber"
    )
    assert VOTES not in {name for _method, name in origin.calls}


def test_an_unknown_house_member_is_kept_and_the_run_is_partial() -> None:
    before = _people()
    origin = _Origin(
        _files(
            members=[_member(icpsr=998002, bioguide_id="V998002", bioname="UNKNOWN, Uma")],
            rolls=[_roll(chamber="House", rollnumber=3, session=1, clerk_rollnumber=None)],
        )
    )
    loaded = _sync(origin)
    assert loaded.result["partial"] is True
    assert loaded.result["unlinked_members"] == 1
    assert loaded.result["unlinked_presidents"] == 0
    assert _rows(
        "SELECT person_id IS NULL, bioname FROM core.voteview_member"
    ) == [(True, "UNKNOWN, Uma")]
    assert _rows(
        "SELECT count(*) FROM core.person_name_source WHERE dataset_id = 'congress.voteview'"
    ) == [(0,)]
    assert _people() == before


def test_a_known_bioguide_with_no_icpsr_links_and_stores_the_number() -> None:
    _add_bioguide("V998003", "Bioguide Only Bea")
    origin = _Origin(
        _files(
            members=[_member(icpsr=998003, bioguide_id="V998003", bioname="BEA, Bioguide")],
            rolls=[_roll(chamber="House", rollnumber=8, session=1, clerk_rollnumber=None)],
        )
    )
    loaded = _sync(origin)
    assert loaded.result["partial"] is False
    assert loaded.result["unlinked_members"] == 0
    assert _rows(
        "SELECT person_id IS NOT NULL FROM core.voteview_member"
    ) == [(True,)]
    assert _rows(
        "SELECT namespace, external_id FROM core.person_identifier "
        "WHERE external_id IN ('V998003', '998003') ORDER BY namespace"
    ) == [("bioguide", "V998003"), ("icpsr", "998003")]
    again = _sync(origin)
    assert again.result["reused"] == [MEMBERS, ROLLCALLS, PARTIES]
    assert _rows(
        "SELECT count(*) FROM core.person_identifier WHERE namespace = 'icpsr' AND external_id = '998003'"
    ) == [(1,)]


def test_a_person_who_already_has_a_different_icpsr_is_not_relinked() -> None:
    _add_person("V998003", "998004", "Bioguide Only Bea")
    origin = _Origin(
        _files(
            members=[_member(icpsr=998003, bioguide_id="V998003", bioname="BEA, Bioguide")],
            rolls=[_roll(chamber="House", rollnumber=8, session=1, clerk_rollnumber=None)],
        )
    )
    loaded = _sync(origin)
    assert loaded.result["partial"] is True
    assert loaded.result["unlinked_members"] == 1
    assert _rows(
        "SELECT namespace, external_id FROM core.person_identifier "
        "WHERE external_id IN ('998004', '998003') ORDER BY external_id"
    ) == [("icpsr", "998004")]


def test_one_icpsr_is_not_given_to_two_people() -> None:
    _add_bioguide("V998003", "Bioguide Only Bea")
    _add_bioguide("V998004", "Bioguide Only Cam")
    origin = _Origin(
        _files(
            members=[
                _member(congress=119, icpsr=998003, bioguide_id="V998003", bioname="BEA, Bioguide"),
                _member(congress=119, chamber="Senate", icpsr=998003, bioguide_id="V998004", bioname="CAM, Bioguide"),
            ],
            rolls=[_roll(chamber="House", rollnumber=8, session=1, clerk_rollnumber=None)],
        )
    )
    loaded = _sync(origin)
    assert loaded.result["unlinked_members"] == 2
    assert _rows(
        "SELECT count(*) FROM core.person_identifier WHERE namespace = 'icpsr' AND external_id = '998003'"
    ) == [(0,)]


def test_a_shared_new_icpsr_does_not_attach_the_other_persons_row() -> None:
    _add_bioguide("V998003", "Bioguide Only Bea")
    _add_person("V998004", "998004", "Bioguide Only Cam")
    origin = _Origin(
        _files(
            members=[
                _member(congress=119, icpsr=998003, bioguide_id="V998003", bioname="BEA, Bioguide"),
                _member(
                    congress=119,
                    chamber="Senate",
                    icpsr=998003,
                    bioguide_id="V998004",
                    bioname="CAM, Bioguide",
                ),
            ],
            rolls=[_roll(chamber="House", rollnumber=8, session=1, clerk_rollnumber=None)],
        )
    )
    loaded = _sync(origin)
    assert loaded.result["unlinked_members"] == 1
    assert _rows(
        "SELECT bioguide, person_id IS NOT NULL FROM core.voteview_member ORDER BY bioguide"
    ) == [("V998003", True), ("V998004", False)]
    assert _rows(
        "SELECT external_id FROM core.person_identifier WHERE namespace = 'icpsr' "
        "AND external_id IN ('998003', '998004') ORDER BY external_id"
    ) == [("998003",), ("998004",)]
    assert _rows(
        "SELECT p.full_name FROM core.person_identifier i "
        "JOIN core.person p ON p.person_id = i.person_id "
        "WHERE i.namespace = 'icpsr' AND i.external_id = '998003'"
    ) == [("Bioguide Only Bea",)]


def test_a_member_file_from_the_old_rule_reloads_once() -> None:
    _add_bioguide("V998003", "Bioguide Only Bea")
    origin = _Origin(
        _files(
            members=[_member(icpsr=998003, bioguide_id="V998003", bioname="BEA, Bioguide")],
            rolls=[_roll(chamber="House", rollnumber=8, session=1, clerk_rollnumber=None)],
        )
    )
    _sync(origin)
    with connect() as conn:
        conn.execute(
            "UPDATE ingest.artifact SET metadata = metadata - 'link_rule' "
            "WHERE dataset_id = 'congress.voteview' AND artifact_key = %s",
            (MEMBERS,),
        )
        conn.commit()
    reloaded = _sync(origin)
    assert MEMBERS not in reloaded.result["reused"]
    assert reloaded.result["members_inserted"] == 1
    assert _rows(
        "SELECT metadata->>'link_rule' FROM ingest.artifact "
        "WHERE dataset_id = 'congress.voteview' AND artifact_key = %s "
        "ORDER BY artifact_version DESC LIMIT 1",
        (MEMBERS,),
    ) == [("bioguide-row-must-match",)]
    third = _sync(origin)
    assert MEMBERS in third.result["reused"]
    assert third.result["members_inserted"] == 0


def test_a_bioguide_disagreement_links_nobody_and_moves_no_identifier() -> None:
    _add_person("V998001", "998001", "Database Ann")
    origin = _Origin(
        _files(
            members=[_member(bioguide_id="V998009")],
            rolls=[_roll(chamber="House", rollnumber=4, session=1, clerk_rollnumber=None)],
        )
    )
    loaded = _sync(origin)
    assert loaded.result["partial"] is True
    assert loaded.result["bioguide_disagreements"] == 1
    assert loaded.result["unlinked_members"] == 1
    assert _rows("SELECT person_id IS NULL FROM core.voteview_member") == [(True,)]
    assert _rows(
        "SELECT namespace, external_id FROM core.person_identifier "
        "WHERE external_id IN ('V998001', 'V998009', '998001') ORDER BY namespace, external_id"
    ) == [("bioguide", "V998001"), ("icpsr", "998001")]


def test_two_official_rolls_leave_the_link_empty_and_the_votes_unchanged() -> None:
    _add_person("V998001", "998001", "Database Ann")
    _add_roll("us-voteview-test-senate-238", "senate", 238, "2nd", "First Wording", "pass")
    _add_roll("us-voteview-test-senate-238b", "senate", 238, "2nd", "Second Wording", "fail")
    _add_roll("us-voteview-test-senate-897", "senate", 897, "2nd", "Own Number", "pass")
    origin = _Origin(
        _files(
            members=[_member()],
            rolls=[_roll()],
        )
    )
    loaded = _sync(origin)
    assert loaded.result["votes_ambiguous"] == 1
    assert loaded.result["votes_linked"] == 0
    assert loaded.result["partial"] is False
    assert _rows("SELECT roll_call_id IS NULL FROM core.voteview_roll_call") == [(True,)]
    assert _rows(
        "SELECT question, result FROM core.roll_call WHERE external_id LIKE 'us-voteview-test-%%' "
        "ORDER BY external_id"
    ) == [("First Wording", "pass"), ("Second Wording", "fail"), ("Own Number", "pass")]


def test_a_changed_file_keeps_the_old_bytes_and_replaces_only_its_rows() -> None:
    _add_person("V998001", "998001", "Database Ann")
    _official()
    origin = _Origin(_files())
    _sync(origin)
    party = _rows("SELECT voteview_party_id::text FROM core.voteview_party")
    old = _rows(
        "SELECT local_path, checksum_sha256 FROM ingest.artifact "
        "WHERE dataset_id = 'congress.voteview' AND artifact_key = %s",
        (MEMBERS,),
    )[0]
    changed = _files(members=[
        _member(nominate_dim1=0.9),
        _member(chamber="President", icpsr=998009, bioguide_id="", bioname="PRESIDENT, Pat", state_abbrev="USA"),
    ])
    origin.files[MEMBERS] = changed[MEMBERS]
    origin.modified[MEMBERS] = LATER
    second = _sync(origin)
    assert second.result["members_deleted"] == 2
    assert second.result["members_inserted"] == 2
    assert second.result["roll_calls_deleted"] == 0
    assert second.result["parties_deleted"] == 0
    assert _rows("SELECT voteview_party_id::text FROM core.voteview_party") == party
    assert _rows("SELECT nominate_dim1 FROM core.voteview_member WHERE chamber = 'house'") == [(0.9,)]
    versions = _rows(
        "SELECT artifact_version, local_path FROM ingest.artifact "
        "WHERE dataset_id = 'congress.voteview' AND artifact_key = %s ORDER BY artifact_version",
        (MEMBERS,),
    )
    assert [row[0] for row in versions] == [1, 2]
    assert Path(old[0]).is_file()
    assert Path(old[0]).read_bytes() != Path(versions[1][1]).read_bytes()
    assert _rows(
        "SELECT question FROM core.roll_call WHERE external_id = 'us-voteview-test-senate-238'"
    ) == [("Official Senate Question",)]


def test_a_failed_refresh_does_not_hide_the_previous_file(monkeypatch: pytest.MonkeyPatch) -> None:
    _add_person("V998001", "998001", "Database Ann")
    _official()
    origin = _Origin(_files())
    _sync(origin)
    before = _rows(
        "SELECT artifact_version, checksum_sha256 FROM ingest.artifact "
        "WHERE dataset_id = 'congress.voteview' AND artifact_key = %s",
        (MEMBERS,),
    )
    origin.files[MEMBERS] = _files(members=[_member(nominate_dim1=0.7)])[MEMBERS]
    origin.modified[MEMBERS] = LATER

    def boom(*_args: object, **_kwargs: object) -> dict:
        raise RuntimeError("stopped before commit")

    monkeypatch.setattr(voteview_module, "publish_voteview", boom)
    with pytest.raises(RuntimeError, match="stopped"):
        _sync(origin)
    assert _rows(
        "SELECT artifact_version, checksum_sha256 FROM ingest.artifact "
        "WHERE dataset_id = 'congress.voteview' AND artifact_key = %s ORDER BY artifact_version",
        (MEMBERS,),
    ) == before
    assert _rows("SELECT nominate_dim1 FROM core.voteview_member WHERE chamber = 'house'") == [(0.1,)]
    monkeypatch.setattr(voteview_module, "publish_voteview", publish_voteview)
    _sync(origin)
    assert _rows("SELECT nominate_dim1 FROM core.voteview_member WHERE chamber = 'house'") == [(0.7,)]


def test_same_bytes_with_a_new_last_modified_do_not_change_rows() -> None:
    _add_person("V998001", "998001", "Database Ann")
    _official()
    origin = _Origin(_files())
    _sync(origin)
    ids = _rows("SELECT voteview_member_id::text FROM core.voteview_member ORDER BY chamber")
    origin.modified[MEMBERS] = LATER
    origin.calls.clear()
    second = _sync(origin)
    assert ("GET", MEMBERS) in origin.calls
    assert second.result["members_inserted"] == 0
    assert second.result["members_deleted"] == 0
    assert ids == _rows("SELECT voteview_member_id::text FROM core.voteview_member ORDER BY chamber")
    assert _rows(
        "SELECT artifact_version, metadata->>'remote_last_modified' FROM ingest.artifact "
        "WHERE dataset_id = 'congress.voteview' AND artifact_key = %s",
        (MEMBERS,),
    ) == [(1, LATER)]


def test_a_second_sync_at_the_same_time_is_refused() -> None:
    origin = _Origin(_files())
    holder = VoteviewConnector(origin=ORIGIN, http=httpx.Client(transport=httpx.MockTransport(origin.transport)))
    holder._acquire_lock()
    try:
        with pytest.raises(RuntimeError, match="another sync-voteview"):
            _sync(origin)
    finally:
        holder._lock.close()


def test_downgrade_refuses_while_rows_exist() -> None:
    _add_person("V998001", "998001", "Database Ann")
    _official()
    _sync(_Origin(_files()))
    with pytest.raises(RuntimeError, match=r"core\.voteview_member holds"):
        command.downgrade(_alembic_config(), "c4e8a1b93d27")
    assert _rows("SELECT version_num FROM alembic_version") == [(HEAD,)]
    assert _rows("SELECT count(*) FROM core.voteview_member") == [(2,)]


def test_command_exits_match_the_run(monkeypatch: pytest.MonkeyPatch) -> None:
    class Complete:
        def __init__(self, report: object = None) -> None:
            self.result = {"partial": False}

    monkeypatch.setattr("opendiscourse_research.cli.VoteviewConnector", Complete)
    monkeypatch.setattr("opendiscourse_research.cli.run_connector", lambda connector: None)
    assert CliRunner().invoke(app, ["sync-voteview"]).exit_code == 0

    class Partial:
        def __init__(self, report: object = None) -> None:
            self.result = {"partial": True, "unlinked_members": 1}

    monkeypatch.setattr("opendiscourse_research.cli.VoteviewConnector", Partial)
    monkeypatch.setattr("opendiscourse_research.cli.run_connector", lambda connector: None)
    assert CliRunner().invoke(app, ["sync-voteview"]).exit_code == 2

    class Broken:
        def __init__(self, report: object = None) -> None:
            self.result = {}

    def explode(_connector: object) -> None:
        raise ValueError("origin refused the file")

    monkeypatch.setattr("opendiscourse_research.cli.VoteviewConnector", Broken)
    monkeypatch.setattr("opendiscourse_research.cli.run_connector", explode)
    failed = CliRunner().invoke(app, ["sync-voteview"])
    assert failed.exit_code == 1
    assert "origin refused" in failed.stderr


def test_parse_keeps_an_extra_roll_call_key_and_refuses_a_duplicate() -> None:
    files = _files()
    parsed = parse_voteview_files(files)
    assert parsed[ROLLCALLS][0]["record"]["future_field"] == 1
    rolls = json.loads(files[ROLLCALLS])
    rolls.append(dict(rolls[0]))
    with pytest.raises(ValueError, match="repeats"):
        parse_voteview_files({**files, ROLLCALLS: json.dumps(rolls).encode()})
