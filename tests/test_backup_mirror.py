"""The backup script's second copy (voting repair, R13), run against stand-in database tools."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "ops" / "backup_opendiscourse.sh"

# A server version no machine has installed, so the script takes pg_dump from PATH: the stand-in.
_TOOLS = {
    "psql": '#!/bin/sh\ncase "$*" in *server_version_num*) echo 990000;; *) echo \'{"counts": {}}\';; esac\n',
    "pg_dump": (
        "#!/bin/sh\n"
        'if [ "$1" = "--version" ]; then echo "pg_dump (PostgreSQL) 99.0"; exit 0; fi\n'
        'for a in "$@"; do case "$a" in --file=*) printf "%s" "${FAKE_DUMP:-dump}" > "${a#--file=}";; esac; done\n'
    ),
    "pg_restore": "#!/bin/sh\nexit 0\n",
    "df": (
        "#!/bin/sh\n"
        'for last in "$@"; do :; done\n'
        'echo Avail\ncase "$last" in */mirror) echo "${FAKE_MIRROR_FREE_GB:-100}";; *) echo 100;; esac\n'
    ),
}


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A throwaway checkout holding only the script, so no real .env is read."""
    ops = tmp_path / "repo" / "scripts" / "ops"
    ops.mkdir(parents=True)
    shutil.copy(SCRIPT, ops / SCRIPT.name)
    tools = tmp_path / "bin"
    tools.mkdir()
    for name, body in _TOOLS.items():
        (tools / name).write_text(body)
        (tools / name).chmod(0o755)
    return tmp_path


def _backup(repo: Path, **env: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(repo / "repo" / "scripts" / "ops" / SCRIPT.name)],
        env={
            "PATH": f"{repo / 'bin'}:{os.environ['PATH']}",
            "OPENDISCOURSE_BACKUP_DIR": str(repo / "primary"),
            "ALLOW_ROOT_BACKUP": "1",
            **env,
        },
        capture_output=True,
        text=True,
        timeout=30,
    )


def _copy(directory: Path) -> tuple[str, str]:
    return (directory / "opendiscourse.dump").read_text(), (directory / "opendiscourse.manifest.json").read_text()


def test_without_a_mirror_only_the_one_backup_is_written(repo: Path) -> None:
    done = _backup(repo)

    assert done.returncode == 0, done.stderr
    assert _copy(repo / "primary")[0] == "dump" and not (repo / "mirror").exists()


def test_the_mirror_holds_exactly_the_verified_backup_and_its_manifest(repo: Path) -> None:
    mirror = repo / "mirror"
    for contents in ("first", "second"):
        done = _backup(repo, OPENDISCOURSE_BACKUP_MIRROR_DIR=str(mirror), FAKE_DUMP=contents)
        assert done.returncode == 0, done.stderr

    assert _copy(mirror) == _copy(repo / "primary") and _copy(mirror)[0] == "second"
    assert sorted(p.name for p in mirror.iterdir()) == ["opendiscourse.dump", "opendiscourse.manifest.json"]
    assert (mirror / "opendiscourse.dump").stat().st_mode & 0o077 == 0


def test_a_full_mirror_disk_fails_loudly_and_keeps_the_previous_mirror(repo: Path) -> None:
    mirror = repo / "mirror"
    _backup(repo, OPENDISCOURSE_BACKUP_MIRROR_DIR=str(mirror), FAKE_DUMP="first")

    done = _backup(
        repo, OPENDISCOURSE_BACKUP_MIRROR_DIR=str(mirror), FAKE_DUMP="second", FAKE_MIRROR_FREE_GB="3"
    )

    assert done.returncode != 0 and "mirror" in done.stderr
    assert _copy(mirror)[0] == "first" and _copy(repo / "primary")[0] == "second"


def test_an_unusable_mirror_path_fails_loudly_after_the_backup_itself_is_saved(repo: Path) -> None:
    blocked = repo / "mirror"
    blocked.write_text("a file, not a folder")

    done = _backup(repo, OPENDISCOURSE_BACKUP_MIRROR_DIR=str(blocked))

    assert done.returncode != 0 and "mirror" in done.stderr
    assert _copy(repo / "primary")[0] == "dump"
