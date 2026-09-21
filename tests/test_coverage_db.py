"""Story 9.3: loaded-side coverage counts read the warehouse and never write to it."""

from __future__ import annotations

import os
from collections.abc import Iterator
from datetime import date

import pytest

from opendiscourse_research.catalog import sync_inventory
from opendiscourse_research.config import settings
from opendiscourse_research.coverage import OfficialCache, build_report, congress_span
from opendiscourse_research.db import _engine, apply_migrations, connect
from opendiscourse_research.repositories.coverage import loaded_counts

TEST_JURISDICTION = "ocd-jurisdiction/country:zz/coverage-test"
CONGRESS = "9999"  # far outside any real Congress; cleaned up afterwards
TERM_CONGRESS = "4000"  # the last Congress whose dates Python can represent (year 9787)
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
        term_people = [
            row["person_id"]
            for row in conn.execute(
                "SELECT person_id FROM core.person_identifier "
                "WHERE namespace = 'bioguide' AND external_id LIKE 'COVTERM%'"
            ).fetchall()
        ]
        conn.execute("DELETE FROM core.membership WHERE person_id = ANY(%s)", (term_people,))
        conn.execute("DELETE FROM core.person_identifier WHERE person_id = ANY(%s)", (term_people,))
        conn.execute("DELETE FROM core.person WHERE person_id = ANY(%s)", (term_people,))
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
        conn.execute("DELETE FROM core.bill_text_source_record WHERE congress = %s", (int(CONGRESS),))
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
        conn.execute(
            "INSERT INTO core.bill_text_source_record ("
            "source_artifact_id, source_member, congress, session, bill_type, "
            "bill_number, version_code, record, record_sha256) "
            "VALUES (%s, 'BILLS-9999hr1ih.xml', %s, 1, 'hr', '1', 'ih', '{}'::jsonb, 'abc')",
            (artifact, int(CONGRESS)),
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
        assert loaded["bill_text"][number] == 1
    finally:
        _cleanup()


def test_a_term_counts_for_every_congress_it_overlaps_by_date(database):
    """Story 3.3 stores one membership per term (no session id); coverage reads it by dates.

    The expectation side (`expected_members`) counts a person for a Congress when a term
    overlaps it, so the loaded side must too: a six-year Senate term covers three Congresses.
    """
    _cleanup()
    first, after = congress_span(int(TERM_CONGRESS))
    year = first.year
    with connect() as conn:
        artifact = conn.execute(
            "INSERT INTO ingest.artifact (dataset_id, remote_url, local_path, artifact_key, status) "
            "VALUES ('congress.legislators', 'x', '/x', 'coverage-term-test', 'downloaded') "
            "RETURNING artifact_id"
        ).fetchone()["artifact_id"]
        conn.execute(
            "INSERT INTO core.jurisdiction (jurisdiction_id, name, classification) "
            "VALUES (%s, 'Coverage Test', 'country') ON CONFLICT DO NOTHING",
            (TEST_JURISDICTION,),
        )
        conn.execute(
            "INSERT INTO core.legislative_session (jurisdiction_id, identifier, classification, source_artifact_id) "
            "VALUES (%s, %s, 'congress', %s)",
            (TEST_JURISDICTION, TERM_CONGRESS, artifact),
        )
        organization = conn.execute(
            "INSERT INTO core.organization (organization_type, name) VALUES ('legislature', 'Coverage Term Org') "
            "RETURNING organization_id"
        ).fetchone()["organization_id"]
        terms = {
            "COVTERM1": (date(year - 4, 1, 3), date(year + 2, 1, 3)),  # a six-year term covering this Congress
            "COVTERM2": (date(year + 1, 6, 1), None),  # started mid-Congress, no end date recorded
            "COVTERM3": (date(year - 2, 1, 3), first),  # ended on the first day: not in this Congress
            "COVTERM4": (after, date(year + 6, 1, 3)),  # started the day after it ended
        }
        for bioguide, (start, end) in terms.items():
            person = conn.execute(
                "INSERT INTO core.person (full_name) VALUES (%s) RETURNING person_id", (bioguide,)
            ).fetchone()["person_id"]
            conn.execute(
                "INSERT INTO core.person_identifier (person_id, namespace, external_id) VALUES (%s, 'bioguide', %s)",
                (person, bioguide),
            )
            conn.execute(
                "INSERT INTO core.membership (person_id, organization_id, role, start_date, end_date, source_artifact_id) "
                "VALUES (%s, %s, 'senator', %s, %s, %s)",
                (person, organization, start, end, artifact),
            )
        conn.commit()
    try:
        assert loaded_counts()["memberships"][int(TERM_CONGRESS)] == {"COVTERM1", "COVTERM2"}
    finally:
        with connect() as conn:  # children first; the module cleanup then removes the people
            conn.execute("DELETE FROM core.membership WHERE organization_id = %s", (organization,))
            conn.execute("DELETE FROM core.organization WHERE organization_id = %s", (organization,))
            conn.execute("DELETE FROM core.legislative_session WHERE identifier = %s", (TERM_CONGRESS,))
            conn.execute("DELETE FROM ingest.artifact WHERE artifact_key = 'coverage-term-test'")
            conn.commit()
        _cleanup()
