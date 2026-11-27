"""Downloaded bytes reach evidence storage through a staging file no other call shares."""

from __future__ import annotations

import os
import stat
from hashlib import sha256
from pathlib import Path

import pytest

from opendiscourse_research import artifact_storage
from opendiscourse_research.artifact_storage import retain_downloaded_bytes, retained_path

BODY = b"publisher bytes"
DIGEST = sha256(BODY).hexdigest()


def _destination(tmp_path: Path) -> Path:
    return retained_path(tmp_path / "keep" / "members.yaml", DIGEST)


def test_bytes_are_kept_readable_and_no_staging_file_remains(tmp_path: Path) -> None:
    kept = retain_downloaded_bytes(BODY, DIGEST, _destination(tmp_path))

    assert kept == _destination(tmp_path)
    assert kept.read_bytes() == BODY
    assert stat.S_IMODE(kept.stat().st_mode) == 0o644
    assert [path.name for path in kept.parent.iterdir()] == [kept.name]


def test_each_call_stages_under_its_own_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    staged: list[Path] = []
    link = os.link

    def watched(source, target):
        staged.append(Path(source))
        link(source, target)

    monkeypatch.setattr(artifact_storage.os, "link", watched)
    for folder in ("first", "first-again"):
        retain_downloaded_bytes(BODY, DIGEST, _destination(tmp_path / folder))
    _destination(tmp_path / "first").unlink()
    retain_downloaded_bytes(BODY, DIGEST, _destination(tmp_path / "first"))

    assert len({path.name for path in staged}) == 3


def test_a_leftover_staging_link_is_never_written_to(tmp_path: Path) -> None:
    """A run killed between link and unlink leaves a second name for the retained file."""
    kept = retain_downloaded_bytes(BODY, DIGEST, _destination(tmp_path))
    leftover = kept.parent / f".members.yaml.{DIGEST}.incoming"
    os.link(kept, leftover)
    before = leftover.stat().st_mtime_ns

    retain_downloaded_bytes(BODY, DIGEST, kept)

    assert kept.read_bytes() == BODY
    assert leftover.stat().st_mtime_ns == before


def test_bytes_that_do_not_match_the_checksum_are_refused(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="checksum"):
        retain_downloaded_bytes(b"other bytes", DIGEST, _destination(tmp_path))
    assert not _destination(tmp_path).exists()


def test_damaged_evidence_is_reported_not_overwritten(tmp_path: Path) -> None:
    destination = _destination(tmp_path)
    destination.parent.mkdir(parents=True)
    destination.write_bytes(b"damaged")

    with pytest.raises(ValueError, match="never overwritten"):
        retain_downloaded_bytes(BODY, DIGEST, destination)

    assert destination.read_bytes() == b"damaged"
    assert [path.name for path in destination.parent.iterdir()] == [destination.name]
