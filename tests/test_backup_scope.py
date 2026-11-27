"""What the backup leaves out must not strand rows that point into it."""

from __future__ import annotations

import re
from fnmatch import fnmatchcase
from pathlib import Path

import pytest
from db_cluster import cloned_database

from opendiscourse_research.db import connect

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "ops" / "backup_opendiscourse.sh"


def _left_out() -> list[str]:
    default = re.search(r'EXCLUDE_DATA="\$\{OPENDISCOURSE_BACKUP_EXCLUDE_DATA:-([^}]*)\}"', SCRIPT.read_text())
    assert default, "the backup script no longer states its default left-out tables"
    return default.group(1).split()


@pytest.mark.db
def test_no_backed_up_table_links_into_a_table_whose_rows_are_left_out() -> None:
    patterns = _left_out()
    with cloned_database(), connect() as conn:
        links = conn.execute(
            "SELECT cn.nspname || '.' || c.relname AS child, pn.nspname || '.' || p.relname AS parent "
            "FROM pg_constraint k "
            "JOIN pg_class c ON c.oid = k.conrelid JOIN pg_namespace cn ON cn.oid = c.relnamespace "
            "JOIN pg_class p ON p.oid = k.confrelid JOIN pg_namespace pn ON pn.oid = p.relnamespace "
            "WHERE k.contype = 'f'"
        ).fetchall()

    def left_out(table: str) -> bool:
        return any(fnmatchcase(table, pattern) for pattern in patterns)

    assert links
    assert [link for link in links if left_out(link["parent"]) and not left_out(link["child"])] == []
