"""The shared PostGIS template gives every caller a private, migrated database."""

from __future__ import annotations

import pytest
from db_cluster import cloned_database, cluster_start_count, database_url_for

from opendiscourse_research.db import connect


def test_database_url_for_replaces_only_the_database_name() -> None:
    """A password and host stay put when the database name changes."""
    original = "postgresql://tester:secret@127.0.0.1:5432/postgres"
    cloned = database_url_for(original, "od_clone_1")
    assert cloned == "postgresql://tester:secret@127.0.0.1:5432/od_clone_1"


def test_database_url_for_refuses_an_unsafe_name() -> None:
    """Database names are interpolated into SQL, so only a plain identifier is accepted."""
    with pytest.raises(ValueError):
        database_url_for("postgresql://tester@127.0.0.1/postgres", "bad-name")


@pytest.mark.db
def test_each_clone_is_migrated_and_does_not_see_the_previous_copy() -> None:
    """One server serves two private copies, and a table in the first is absent from the second."""
    with cloned_database() as first, connect() as conn:
        assert conn.execute("SELECT version_num FROM alembic_version").fetchone()["version_num"]
        conn.execute("CREATE TABLE public.clone_probe (id integer)")
        conn.commit()
    with cloned_database() as second, connect() as conn:
        assert second != first
        found = conn.execute("SELECT to_regclass('public.clone_probe') AS name").fetchone()["name"]
        assert found is None
    assert cluster_start_count() == 1
