"""Story 9.3: loaded-side coverage counts read the warehouse and never write to it."""

from __future__ import annotations

import os
from collections.abc import Iterator
from datetime import date

import pytest

from opendiscourse_research.catalog import sync_inventory
from opendiscourse_research.config import settings
from opendiscourse_research.coverage import OfficialCache, build_report
from opendiscourse_research.db import _engine, apply_migrations, connect
from opendiscourse_research.repositories.coverage import loaded_counts

TEST_JURISDICTION = "ocd-jurisdiction/country:zz/coverage-test"
CONGRESS = "9999"  # far outside any real Congress; cleaned up afterwards
TABLES = ("core.bill", "core.roll_call", "fact.member_vote", "core.membership", "ingest.run")


@pytest.fixture(scope="module")
def database() -> Iterator[None]:
    """CI's shared PostGIS service, or a disposable local one."""
    original = settings.database_url
    external = os.environ.get("OPENDISCOURSE_TEST_DATABASE_URL")
    container = None
    if external:
        settings.database_url = external
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
        _cleanup()
        settings.database_url = original
        _engine.cache_clear()
        if container is not None:
            container.stop()


def _cleanup() -> None:
    with connect() as conn:
        conn.execute(
            "DELETE FROM fact.member_vote WHERE roll_call_id IN "
            "(SELECT roll_call_id FROM core.roll_call WHERE legislative_session = %s)",
            (CONGRESS,),
        )
        conn.execute(
            "DELETE FROM core.membership WHERE legislative_session_id IN "
            "(SELECT legislative_session_id FROM core.legislative_session WHERE identifier = %s)",
            (CONGRESS,),
        )
        conn.execute(
            "DELETE FROM core.bill_action WHERE bill_id IN "
            "(SELECT bill_id FROM core.bill WHERE legislative_session = %s)",
            (CONGRESS,),
        )
        conn.execute("DELETE FROM core.roll_call WHERE legislative_session = %s", (CONGRESS,))
        conn.execute("DELETE FROM core.bill WHERE legislative_session = %s", (CONGRESS,))
        conn.execute("DELETE FROM core.legislative_session WHERE identifier = %s", (CONGRESS,))
        conn.execute(
            "DELETE FROM core.jurisdiction WHERE jurisdiction_id = %s", (TEST_JURISDICTION,)
        )
        conn.execute("DELETE FROM core.person_identifier WHERE external_id = 'COVTEST1'")
        conn.execute("DELETE FROM core.person WHERE full_name = 'Coverage Test'")
        conn.execute("DELETE FROM core.organization WHERE name = 'Coverage Test Org'")
        conn.execute("DELETE FROM ingest.artifact WHERE artifact_key = 'coverage-test'")
        conn.commit()


def _counts() -> dict[str, int]:
    with connect() as conn:
        return {t: conn.execute(f"SELECT count(*) AS n FROM {t}").fetchone()["n"] for t in TABLES}


def test_loaded_counts_see_bills_and_roll_calls_without_votes(database):
    with connect() as conn:
        conn.execute(
            "INSERT INTO core.bill (jurisdiction, legislative_session, bill_type, bill_number) "
            "VALUES ('us', %s, 'hr', '1'), ('us', %s, 's', '1')",
            (CONGRESS, CONGRESS),
        )
        conn.execute(
            "INSERT INTO core.roll_call (jurisdiction, legislative_session, chamber, external_id) "
            "VALUES ('us', %s, 'Senate', 'cov-1')",
            (CONGRESS,),
        )
        conn.commit()
    try:
        loaded = loaded_counts()
        assert loaded["bills"][int(CONGRESS)] == {"hr": 1, "s": 1}
        assert loaded["roll_calls"][int(CONGRESS)]["senate"] == {
            "roll_calls": 1,
            "without_votes": 1,
        }
        assert loaded["runs_total"] >= loaded["runs_unattributed"] >= 0
    finally:
        _cleanup()


def test_report_does_not_write_to_the_warehouse(database, tmp_path):
    class Fake:
        def first_billstatus_congress(self):
            return 108

        def billstatus(self, congress, bill_type):
            return 1

        def senate_votes(self, congress, session):
            return 1

        def house_rolls(self, year):
            return 1

    before = _counts()
    build_report(
        [118],
        official=Fake(),
        cache=OfficialCache(tmp_path / "o.json"),
        loaded=loaded_counts(),
        lake=lambda c: None,
        members={118: set()},
        today=date(2026, 9, 19),
    )
    assert _counts() == before


def test_loaded_counts_read_actions_votes_and_memberships(database):
    """Seed one row of every kind and assert what each loaded-side query returns."""
    _cleanup()
    with connect() as conn:
        artifact = conn.execute(
            "INSERT INTO ingest.artifact (dataset_id, remote_url, local_path, artifact_key, status) "
            "VALUES ('congress.legislators', 'x', '/x', 'coverage-test', 'downloaded') "
            "RETURNING artifact_id"
        ).fetchone()["artifact_id"]
        person = conn.execute(
            "INSERT INTO core.person (full_name) VALUES ('Coverage Test') RETURNING person_id"
        ).fetchone()["person_id"]
        conn.execute(
            "INSERT INTO core.person_identifier (person_id, namespace, external_id) "
            "VALUES (%s, 'bioguide', 'COVTEST1')",
            (person,),
        )
        organization = conn.execute(
            "INSERT INTO core.organization (organization_type, name) "
            "VALUES ('legislature', 'Coverage Test Org') RETURNING organization_id"
        ).fetchone()["organization_id"]
        conn.execute(
            "INSERT INTO core.jurisdiction (jurisdiction_id, name, classification) "
            "VALUES (%s, 'Coverage Test', 'country')",
            (TEST_JURISDICTION,),
        )
        session_id = conn.execute(
            "INSERT INTO core.legislative_session "
            "(jurisdiction_id, identifier, classification, source_artifact_id) "
            "VALUES (%s, %s, 'congress', %s) "
            "RETURNING legislative_session_id",
            (TEST_JURISDICTION, CONGRESS, artifact),
        ).fetchone()["legislative_session_id"]
        conn.execute(
            "INSERT INTO core.membership "
            "(person_id, organization_id, legislative_session_id, role, source_artifact_id) "
            "VALUES (%s, %s, %s, 'member', %s)",
            (person, organization, session_id, artifact),
        )
        bill = conn.execute(
            "INSERT INTO core.bill (jurisdiction, legislative_session, bill_type, bill_number) "
            "VALUES ('us', %s, 'HR', '1') RETURNING bill_id",
            (CONGRESS,),
        ).fetchone()["bill_id"]
        conn.execute(
            "INSERT INTO core.bill_action (bill_id, description, source_artifact_id) "
            "VALUES (%s, 'a', %s), (%s, 'b', %s)",
            (bill, artifact, bill, artifact),
        )
        voted, _unvoted = [
            conn.execute(
                "INSERT INTO core.roll_call (jurisdiction, legislative_session, chamber, external_id) "
                "VALUES ('us', %s, 'House', %s) RETURNING roll_call_id",
                (CONGRESS, name),
            ).fetchone()["roll_call_id"]
            for name in ("cov-voted", "cov-unvoted")
        ]
        conn.execute(
            "INSERT INTO fact.member_vote (roll_call_id, person_id, position, source_artifact_id) "
            "VALUES (%s, %s, 'yea', %s)",
            (voted, person, artifact),
        )
        conn.commit()
    try:
        loaded = loaded_counts()
        number = int(CONGRESS)
        assert loaded["bills"][number] == {"hr": 1}  # bill_type is lower-cased
        assert loaded["actions"][number] == 2
        assert loaded["roll_calls"][number]["house"] == {
            "roll_calls": 2,
            "without_votes": 1,
            "member_votes": 1,
        }
        assert loaded["memberships"][number] == {"COVTEST1"}
        assert "COVTEST1" in loaded["bioguide_ids"]
    finally:
        _cleanup()
