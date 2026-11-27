"""The restore drill must not call a backup good when part of it failed to restore."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "ops" / "restore_drill.sh"

# Stand-in for docker: the server is ready at once, pg_restore prints FAKE_RESTORE_LOG, counts match.
_DOCKER = """#!/bin/sh
case "$*" in
  logs*) echo 'ready to accept connections'; echo 'ready to accept connections';;
  *pg_restore*) cat "$FAKE_RESTORE_LOG" >&2; exit 1;;
  *alembic_version*) echo head1;;
  *'count(*)'*) echo 5;;
esac
"""

_MISSING_PGVECTOR = """pg_restore: error: could not execute query: ERROR:  extension "vector" is not available
Command was: CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA public;
pg_restore: error: could not execute query: ERROR:  extension "vector" does not exist
Command was: COMMENT ON EXTENSION vector IS 'vector data type';
"""
_MISSING_MAPPING_ROLE = """pg_restore: error: could not execute query: ERROR:  role "someone" does not exist
Command was: CREATE USER MAPPING FOR someone SERVER openstates_server;
"""
_BROKEN_LINK = """pg_restore: error: could not execute query: ERROR:  insert or update on table "child" violates foreign key constraint "child_parent_fkey"
Command was: ALTER TABLE ONLY core.child ADD CONSTRAINT child_parent_fkey FOREIGN KEY (a) REFERENCES core.parent(a);
"""
_MISSING_OTHER_ROLE = """pg_restore: error: could not execute query: ERROR:  role "someone" does not exist
Command was: ALTER TABLE core.child OWNER TO someone;
"""


def _drill(tmp_path: Path, log: str) -> subprocess.CompletedProcess[str]:
    tools = tmp_path / "bin"
    tools.mkdir()
    (tools / "docker").write_text(_DOCKER)
    (tools / "docker").chmod(0o755)
    (tmp_path / "od.dump").write_text("dump")
    (tmp_path / "od.manifest.json").write_text(json.dumps({"counts": {"core.bill": 5}, "alembic_head": "head1"}))
    (tmp_path / "restore.log").write_text(log)
    return subprocess.run(
        ["bash", str(SCRIPT), str(tmp_path / "od.dump")],
        env={"PATH": f"{tools}:{os.environ['PATH']}", "FAKE_RESTORE_LOG": str(tmp_path / "restore.log")},
        capture_output=True,
        text=True,
        timeout=60,
    )


def test_the_errors_a_throwaway_server_must_produce_still_pass(tmp_path: Path) -> None:
    done = _drill(tmp_path, _MISSING_PGVECTOR + _MISSING_MAPPING_ROLE)

    assert done.returncode == 0, done.stdout + done.stderr
    assert "DRILL PASSED" in done.stdout


@pytest.mark.parametrize("unexpected", [_BROKEN_LINK, _MISSING_OTHER_ROLE], ids=["broken link", "missing role"])
def test_any_other_restore_error_fails_the_drill_even_when_counts_match(tmp_path: Path, unexpected: str) -> None:
    done = _drill(tmp_path, _MISSING_PGVECTOR + unexpected)

    assert done.returncode == 1, done.stdout
    assert unexpected.splitlines()[0] in done.stdout and "DRILL PASSED" not in done.stdout
