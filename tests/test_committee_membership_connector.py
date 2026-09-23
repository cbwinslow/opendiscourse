"""Committee membership: download the three YAML files from a fake origin and load them.

Nothing here contacts GitHub. Every test removes the rows it wrote: CI runs database
tests against one shared database.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest
from typer.testing import CliRunner

from opendiscourse_research.catalog import sync_inventory
from opendiscourse_research.cli import app
from opendiscourse_research.config import settings
from opendiscourse_research.db import _engine, apply_migrations, connect
from opendiscourse_research.ingestion import committee_membership as membership
from opendiscourse_research.ingestion.committee_membership import (
    COMMIT_DATE,
    FILES,
    CommitteeMembershipConnector,
    parse_committee_files,
)
from opendiscourse_research.ingestion.connector import run_connector
from opendiscourse_research.repositories.committees import publish_committee_membership

ORIGIN = "https://example.test/legislators"
COMMIT = "abc123def4567890abcd"
VINTAGE = "2024-01-15"
PEOPLE = {
    "C000001": "Database Ann",
    "C000002": "Database Bob",
    "C000003": "Database Cara",
    "C000004": "Database Dan",
    "C000005": "Database Eve",
    "C000006": "Database Frank",
}

CURRENT = """
- type: senate
  name: Senate Agriculture
  thomas_id: SSAF
  url: https://example.test/ssaf
  minority_url: https://example.test/ssaf-min
  senate_committee_id: SSAF
  address: "1 Capitol"
  phone: "202-1"
  rss_url: https://example.test/rss
  minority_rss_url: https://example.test/rss-min
  jurisdiction: Farming
  jurisdiction_source: https://example.test/jurisdiction
  wikipedia: Senate Agriculture Committee
  youtube_id: UCtest
  subcommittees:
    - name: Nutrition
      thomas_id: "13"
      wikipedia: Nutrition Subcommittee
- type: house
  name: House One
  thomas_id: HS01
  house_committee_id: "01"
  subcommittees:
    - name: Shared Code
      thomas_id: "01"
- type: senate
  name: Senate One
  thomas_id: SS01
  senate_committee_id: SS01
  subcommittees:
    - name: Other Shared Code
      thomas_id: "01"
- type: joint
  name: Joint Tax
  thomas_id: JSTX
  house_committee_id: IT
  senate_committee_id: JSTX
"""

HISTORICAL = """
- type: senate
  name: Senate Agriculture Old
  thomas_id: SSAF
  senate_committee_id: SSAF
  congresses: [110, 111]
  names:
    110: Agriculture
  subcommittees:
    - name: Nutrition Old
      thomas_id: "13"
      congresses: [110]
      names:
        110: Nutrition
- type: house
  name: District of Columbia
  thomas_id: HSDT
  house_committee_id: DT
  congresses: [93, 94]
  names:
    93: District of Columbia
    94: District of Columbia
  subcommittees:
    - name: Fiscal Affairs
      thomas_id: "01"
      congresses: [97]
      names:
        97: Fiscal Affairs
"""

MEMBERSHIP = """
SSAF:
- name: Printed Ann
  party: majority
  rank: 1
  title: Chair
  bioguide: C000001
SSAF13:
- name: Printed Bob
  party: minority
  rank: 1
  title: Ranking Member
  bioguide: C000002
HS0101:
- name: Printed Cara
  party: majority
  rank: 1
  bioguide: C000003
SS0101:
- name: Printed Dan
  party: minority
  rank: 2
  bioguide: C000004
JSTX:
- name: Printed Eve
  party: majority
  rank: 1
  title: Chair
  chamber: house
  bioguide: C000005
- name: Printed Frank
  party: minority
  rank: 1
  title: Ranking Member
  chamber: senate
  bioguide: C000006
"""


def _files() -> dict[str, bytes]:
    return {
        "committees-current.yaml": CURRENT.encode(),
        "committees-historical.yaml": HISTORICAL.encode(),
        "committee-membership-current.yaml": MEMBERSHIP.encode(),
    }


class _Origin:
    """Serves the three files, or fails, without leaving the machine."""

    def __init__(self, files: dict[str, bytes]) -> None:
        self.files = files
        self.fail = False

    def transport(self, request: httpx.Request) -> httpx.Response:
        if self.fail:
            return httpx.Response(404)
        name = request.url.path.rsplit("/", 1)[-1]
        body = self.files[name]
        if request.method == "HEAD":
            return httpx.Response(200, headers={"Content-Length": str(len(body))})
        return httpx.Response(200, content=body)


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


def _remove_rows() -> None:
    with connect() as conn:
        for statement in (
            "DELETE FROM core.person_name_source WHERE dataset_id = 'congress.committee_membership'",
            "DELETE FROM core.committee_assignment",
            "DELETE FROM core.committee_source_record",
            "DELETE FROM core.committee",
            (
                "WITH gone AS (DELETE FROM core.person_identifier WHERE namespace = 'bioguide' "
                "AND external_id LIKE 'C00000%' RETURNING person_id) "
                "DELETE FROM core.person WHERE person_id IN (SELECT person_id FROM gone)"
            ),
            (
                "DELETE FROM ingest.run_target WHERE run_id IN "
                "(SELECT run_id FROM ingest.run WHERE dataset_id = 'congress.committee_membership')"
            ),
            "DELETE FROM ingest.run WHERE dataset_id = 'congress.committee_membership'",
            "DELETE FROM ingest.artifact WHERE dataset_id = 'congress.committee_membership'",
        ):
            conn.execute(statement)
        conn.commit()


@pytest.fixture(autouse=True)
def _clean(catalog_database: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setattr(settings, "data_root", str(tmp_path / "lake" / "raw"))
    _remove_rows()
    _add_people()
    yield
    _remove_rows()


def _add_people() -> None:
    with connect() as conn:
        for bioguide, name in PEOPLE.items():
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


def _rows(sql: str) -> list[tuple]:
    with connect() as conn:
        return [tuple(row.values()) for row in conn.execute(sql).fetchall()]


def _sync(origin: _Origin) -> CommitteeMembershipConnector:
    client = httpx.Client(transport=httpx.MockTransport(origin.transport))
    connector = CommitteeMembershipConnector(
        origin=ORIGIN, commit=COMMIT, vintage=VINTAGE, http=client
    )
    run_connector(connector)
    return connector


def _snapshot() -> dict[str, list[tuple]]:
    return {
        "committees": _rows(
            "SELECT thomas_key, parent_thomas_key, kind, chamber, name, url, "
            "congresses::text, former_names::text, committee_id::text "
            "FROM core.committee ORDER BY thomas_key"
        ),
        "assignments": _rows(
            "SELECT c.thomas_key, a.bioguide, a.person_id IS NOT NULL, a.stated_name, "
            "a.party, a.rank, a.title, a.chamber, a.committee_assignment_id::text "
            "FROM core.committee_assignment a "
            "JOIN core.committee c ON c.committee_id = a.committee_id "
            "ORDER BY c.thomas_key, a.bioguide"
        ),
        "names": _rows(
            "SELECT i.external_id, p.full_name, p.name_source_id IS NULL "
            "FROM core.person p "
            "JOIN core.person_identifier i ON i.person_id = p.person_id "
            "WHERE i.namespace = 'bioguide' AND i.external_id LIKE 'C00000%' "
            "ORDER BY i.external_id"
        ),
        "roster": _rows(
            "SELECT full_name FROM core.person_name_source "
            "WHERE dataset_id = 'congress.committee_membership' AND name_kind = 'roster' "
            "ORDER BY full_name"
        ),
    }


def test_happy_path_loads_keys_and_a_rerun_changes_nothing() -> None:
    origin = _Origin(_files())
    first = _sync(origin)
    assert first.result["partial"] is False
    assert first.result["unknown_bioguide_ids"] == []
    assert first.result["committees"] == 9
    assert first.result["assignments"] == 6
    assert first.result["committees_inserted"] == 9
    assert first.result["assignments_inserted"] == 6
    keys = {row[0] for row in _rows("SELECT thomas_key FROM core.committee")}
    assert keys == {
        "SSAF",
        "SSAF13",
        "HS01",
        "HS0101",
        "SS01",
        "SS0101",
        "JSTX",
        "HSDT",
        "HSDT01",
    }
    # The same short code under two parents stays two committees.
    members = {
        row[0]: row[1]
        for row in _rows(
            "SELECT c.thomas_key, a.bioguide FROM core.committee_assignment a "
            "JOIN core.committee c ON c.committee_id = a.committee_id "
            "WHERE c.thomas_key IN ('HS0101', 'SS0101')"
        )
    }
    assert members == {"HS0101": "C000003", "SS0101": "C000004"}
    agriculture = _rows(
        "SELECT name, url, congresses::text, former_names::text FROM core.committee "
        "WHERE thomas_key = 'SSAF'"
    )[0]
    assert agriculture[0] == "Senate Agriculture"
    assert agriculture[1] == "https://example.test/ssaf"
    assert agriculture[2] == "{110,111}"
    assert "Agriculture" in agriculture[3]
    evidence = _rows(
        "SELECT c.thomas_key, s.metadata->>'file' AS source_file, "
        "h.metadata->>'file' AS history_file "
        "FROM core.committee c "
        "JOIN ingest.artifact s ON s.artifact_id = c.source_artifact_id "
        "LEFT JOIN ingest.artifact h ON h.artifact_id = c.history_artifact_id "
        "WHERE c.thomas_key IN ('SSAF', 'HSDT') ORDER BY c.thomas_key"
    )
    assert evidence == [
        ("HSDT", "committees-historical.yaml", None),
        ("SSAF", "committees-current.yaml", "committees-historical.yaml"),
    ]
    historical = _rows(
        "SELECT name, congresses::text, "
        "(SELECT count(*) FROM core.committee_assignment a "
        " WHERE a.committee_id = core.committee.committee_id) "
        "FROM core.committee WHERE thomas_key = 'HSDT'"
    )[0]
    assert historical == ("District of Columbia", "{93,94}", 0)
    joint = _rows(
        "SELECT a.bioguide, a.chamber FROM core.committee_assignment a "
        "JOIN core.committee c ON c.committee_id = a.committee_id "
        "WHERE c.thomas_key = 'JSTX' ORDER BY a.bioguide"
    )
    assert joint == [("C000005", "house"), ("C000006", "senate")]
    assert _rows(
        "SELECT count(*) FROM core.committee_source_record"
    ) == [(17,)]
    parent = _rows(
        "SELECT record::text FROM core.committee_source_record "
        "WHERE source_file = 'committees-current.yaml' AND thomas_key = 'SSAF'"
    )[0][0]
    assert "subcommittees" in parent
    assert _snapshot()["names"] == [(bioguide, name, True) for bioguide, name in sorted(PEOPLE.items())]
    assert _snapshot()["roster"] == [
        ("Printed Ann",),
        ("Printed Bob",),
        ("Printed Cara",),
        ("Printed Dan",),
        ("Printed Eve",),
        ("Printed Frank",),
    ]
    before = _snapshot()
    second = _sync(origin)
    assert second.result["committees_inserted"] == 0
    assert second.result["committees_updated"] == 0
    assert second.result["committees_deleted"] == 0
    assert second.result["assignments_inserted"] == 0
    assert second.result["assignments_updated"] == 0
    assert second.result["assignments_deleted"] == 0
    assert second.result["roster_inserted"] == 0
    assert second.result["roster_updated"] == 0
    assert second.result["roster_deleted"] == 0
    assert _snapshot() == before
    assert _rows("SELECT count(*) FROM ingest.artifact WHERE dataset_id = 'congress.committee_membership'") == [(3,)]


def test_a_member_who_leaves_is_removed_and_the_committee_stays() -> None:
    origin = _Origin(_files())
    _sync(origin)
    kept = _rows(
        "SELECT a.committee_assignment_id::text FROM core.committee_assignment a "
        "JOIN core.committee c ON c.committee_id = a.committee_id "
        "WHERE c.thomas_key = 'SSAF' AND a.bioguide = 'C000001'"
    )[0][0]
    origin.files["committee-membership-current.yaml"] = MEMBERSHIP.replace(
        """SSAF13:
- name: Printed Bob
  party: minority
  rank: 1
  title: Ranking Member
  bioguide: C000002
""",
        "SSAF13: []\n",
    ).encode()
    again = _sync(origin)
    assert again.result["assignments_deleted"] == 1
    assert _rows(
        "SELECT a.bioguide FROM core.committee_assignment a "
        "JOIN core.committee c ON c.committee_id = a.committee_id WHERE c.thomas_key = 'SSAF13'"
    ) == []
    assert _rows("SELECT count(*) FROM core.committee WHERE thomas_key = 'SSAF13'") == [(1,)]
    assert _rows(
        "SELECT a.committee_assignment_id::text FROM core.committee_assignment a "
        "JOIN core.committee c ON c.committee_id = a.committee_id "
        "WHERE c.thomas_key = 'SSAF' AND a.bioguide = 'C000001'"
    ) == [(kept,)]
    assert _rows(
        "SELECT full_name FROM core.person_name_source "
        "WHERE name_kind = 'roster' AND full_name = 'Printed Bob'"
    ) == []


def test_an_unknown_bioguide_is_kept_without_a_person_or_a_roster_name() -> None:
    files = _files()
    files["committee-membership-current.yaml"] = MEMBERSHIP.replace(
        "  bioguide: C000001\n",
        "  bioguide: C000001\n"
        "- name: Printed Stranger\n"
        "  party: majority\n"
        "  rank: 2\n"
        "  bioguide: Z000009\n",
    ).encode()
    result = _sync(_Origin(files))
    assert result.result["partial"] is True
    assert result.result["unknown_bioguide_ids"] == ["Z000009"]
    row = _rows(
        "SELECT person_id IS NULL, stated_name FROM core.committee_assignment WHERE bioguide = 'Z000009'"
    )
    assert row == [(True, "Printed Stranger")]
    assert _rows(
        "SELECT count(*) FROM core.person_name_source WHERE full_name = 'Printed Stranger'"
    ) == [(0,)]
    assert _rows(
        "SELECT full_name, name_source_id IS NULL FROM core.person p "
        "JOIN core.person_identifier i ON i.person_id = p.person_id "
        "WHERE i.external_id = 'C000001'"
    ) == [("Database Ann", True)]


def test_a_bad_file_writes_nothing_and_a_rerun_is_safe() -> None:
    origin = _Origin(_files())
    _sync(origin)
    before = _snapshot()
    artifacts = _rows(
        "SELECT count(*) FROM ingest.artifact WHERE dataset_id = 'congress.committee_membership'"
    )
    origin.files["committee-membership-current.yaml"] = b"- name: nobody\n"
    with pytest.raises(ValueError, match="bioguide|mapping"):
        _sync(origin)
    assert _snapshot() == before
    assert _rows(
        "SELECT count(*) FROM ingest.artifact WHERE dataset_id = 'congress.committee_membership'"
    ) == artifacts
    origin.files["committee-membership-current.yaml"] = MEMBERSHIP.encode()
    again = _sync(origin)
    assert again.result["assignments_inserted"] == 0
    assert _snapshot() == before


def test_a_missing_origin_promotes_nothing_and_keeps_retained_files() -> None:
    origin = _Origin(_files())
    _sync(origin)
    retained = _rows(
        "SELECT local_path FROM ingest.artifact WHERE dataset_id = 'congress.committee_membership' "
        "ORDER BY artifact_key"
    )
    assert retained and all(Path(row[0]).is_file() for row in retained)
    before = _snapshot()
    origin.fail = True
    with pytest.raises(RuntimeError, match="could not download"):
        _sync(origin)
    assert _snapshot() == before
    assert all(Path(row[0]).is_file() for row in retained)


def test_a_publish_failure_rolls_back_and_a_rerun_does_not_duplicate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    origin = _Origin(_files())
    calls = {"n": 0}
    real = publish_committee_membership

    def boom(*args: object, **kwargs: object) -> dict:
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("stopped before commit")
        return real(*args, **kwargs)

    monkeypatch.setattr(membership, "publish_committee_membership", boom)
    with pytest.raises(RuntimeError, match="stopped"):
        _sync(origin)
    assert _rows("SELECT count(*) FROM core.committee") == [(0,)]
    monkeypatch.setattr(membership, "publish_committee_membership", real)
    _sync(origin)
    assert _rows("SELECT count(*) FROM core.committee") == [(9,)]
    assert _rows("SELECT count(*) FROM core.committee_assignment") == [(6,)]
    assert _rows(
        "SELECT count(*) FROM ingest.artifact WHERE dataset_id = 'congress.committee_membership'"
    ) == [(3,)]


def test_command_exits_match_the_run(monkeypatch: pytest.MonkeyPatch) -> None:
    class Partial:
        def __init__(self, report: object = None) -> None:
            self.result = {"partial": True, "unknown_bioguide_ids": ["Z000009"]}

    monkeypatch.setattr(
        "opendiscourse_research.cli.CommitteeMembershipConnector", Partial
    )
    monkeypatch.setattr("opendiscourse_research.cli.run_connector", lambda connector: None)
    assert CliRunner().invoke(app, ["sync-committee-membership"]).exit_code == 2

    class Broken:
        def __init__(self, report: object = None) -> None:
            self.result = {}

    def explode(connector: object) -> None:
        raise ValueError("member has no bioguide")

    monkeypatch.setattr("opendiscourse_research.cli.CommitteeMembershipConnector", Broken)
    monkeypatch.setattr("opendiscourse_research.cli.run_connector", explode)
    failed = CliRunner().invoke(app, ["sync-committee-membership"])
    assert failed.exit_code == 1
    assert "no bioguide" in failed.stderr


def test_current_chamber_wins_when_the_historical_file_disagrees() -> None:
    """The Helsinki Commission is joint now and senate in the historical file."""
    files = _files()
    files["committees-historical.yaml"] = files["committees-historical.yaml"].replace(
        b"- type: senate\n  name: Senate Agriculture Old\n  thomas_id: SSAF",
        b"- type: house\n  name: Senate Agriculture Old\n  thomas_id: SSAF",
        1,
    )
    snapshot = parse_committee_files(files)
    agriculture = next(row for row in snapshot.committees if row["thomas_key"] == "SSAF")
    assert agriculture["chamber"] == "senate"
    assert agriculture["name"] == "Senate Agriculture"
    assert agriculture["congresses"] == [110, 111]
    assert agriculture["preferred_file"] == "committees-current.yaml"


def test_a_padded_bioguide_is_stripped_before_it_is_stored() -> None:
    files = _files()
    files["committee-membership-current.yaml"] = files["committee-membership-current.yaml"].replace(
        b"bioguide: C000001", b"bioguide: ' C000001 '", 1
    )
    snapshot = parse_committee_files(files)
    ann = next(member for member in snapshot.members if member.thomas_key == "SSAF")
    assert ann.bioguide == "C000001"


def test_parse_rejects_a_member_without_a_bioguide() -> None:
    files = _files()
    files["committee-membership-current.yaml"] = b"SSAF:\n- name: Nobody\n  party: majority\n  rank: 1\n"
    with pytest.raises(ValueError, match="bioguide"):
        parse_committee_files(files)


def test_downloads_ask_for_uncompressed_bytes() -> None:
    """GitHub reports the gzip size when compression is accepted, which would fail the size check."""
    connector = CommitteeMembershipConnector()
    try:
        assert connector._client().headers["accept-encoding"] == "identity"
    finally:
        connector._client().close()


def test_files_constant_is_the_three_upstream_names() -> None:
    assert FILES == (
        "committees-current.yaml",
        "committees-historical.yaml",
        "committee-membership-current.yaml",
    )
    assert COMMIT_DATE == "2026-09-03"
