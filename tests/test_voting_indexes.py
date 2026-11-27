"""Database contract for the voting lookup indexes (voting repair, R4)."""

from __future__ import annotations

import pytest
from alembic import command
from db_cluster import cloned_database

from opendiscourse_research.db import _alembic_config, connect

pytestmark = [pytest.mark.db, pytest.mark.integration]

INDEXES = ("fact.member_vote_person_idx", "core.roll_call_bill_idx")


def _definitions() -> dict[str, tuple[bool, str]]:
    found = {}
    with connect() as conn:
        for name in INDEXES:
            row = conn.execute(
                "SELECT i.indisvalid AS valid, pg_get_indexdef(i.indexrelid) AS ddl "
                "FROM pg_index i WHERE i.indexrelid = to_regclass(%s)",
                (name,),
            ).fetchone()
            if row is not None:
                found[name] = (row["valid"], row["ddl"])
    return found


def test_both_indexes_exist_after_migrating_and_survive_a_downgrade_and_upgrade() -> None:
    with cloned_database():
        built = _definitions()
        assert set(built) == set(INDEXES) and all(valid for valid, _ in built.values())
        assert '(person_id, roll_call_id) INCLUDE ("position")' in built["fact.member_vote_person_idx"][1]
        assert "(bill_id)" in built["core.roll_call_bill_idx"][1]

        command.downgrade(_alembic_config(), "a1d4c8e6f372")
        assert _definitions() == {}
        command.upgrade(_alembic_config(), "head")
        assert _definitions() == built
