"""Story 9.3: loaded-side coverage counts read the warehouse and never write to it."""

from __future__ import annotations

import os
from collections.abc import Iterator
from datetime import date

import pytest

from opendiscourse_research.config import settings
from opendiscourse_research.coverage import OfficialCache, build_report
from opendiscourse_research.db import _engine, apply_migrations, connect
from opendiscourse_research.repositories.coverage import loaded_counts

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
        yield
    finally:
        _cleanup()
        settings.database_url = original
        _engine.cache_clear()
        if container is not None:
            container.stop()


def _cleanup() -> None:
    with connect() as conn:
        conn.execute("DELETE FROM core.roll_call WHERE legislative_session = %s", (CONGRESS,))
        conn.execute("DELETE FROM core.bill WHERE legislative_session = %s", (CONGRESS,))
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
