"""Filesystem-level immutable evidence publication and verification checks."""

from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256

import pytest

from opendiscourse_research.artifact_storage import retain_artifact_bytes


def test_concurrent_retention_never_links_mutable_source(tmp_path):
    source = tmp_path / "source.zip"
    source.write_bytes(b"original bytes")
    checksum = sha256(b"original bytes").hexdigest()
    with ThreadPoolExecutor(max_workers=4) as pool:
        paths = list(
            pool.map(lambda _: retain_artifact_bytes(source, checksum), range(4))
        )
    assert len(set(paths)) == 1
    source.write_bytes(b"later mutation")
    assert paths[0].read_bytes() == b"original bytes"
    assert not list(tmp_path.glob(".retain-*"))


def test_retention_refuses_changed_source_and_corrupt_destination(tmp_path):
    source = tmp_path / "source.zip"
    source.write_bytes(b"wrong bytes")
    checksum = sha256(b"expected bytes").hexdigest()
    with pytest.raises(ValueError, match="changed during retention"):
        retain_artifact_bytes(source, checksum)
    assert not list(tmp_path.glob(".retain-*"))
    source.write_bytes(b"expected bytes")
    destination = tmp_path / f"source.{checksum}.zip"
    destination.write_bytes(b"existing corrupt evidence")
    with pytest.raises(ValueError, match="checksum-specific"):
        retain_artifact_bytes(source, checksum)
    assert destination.read_bytes() == b"existing corrupt evidence"
    assert not list(tmp_path.glob(".retain-*"))


def _checksum(data: bytes) -> str:
    return sha256(data).hexdigest()


def test_rerun_neither_rewrites_retained_bytes_nor_leaves_temp_files(tmp_path):
    source = tmp_path / "source.zip"
    source.write_bytes(b"stable evidence")
    checksum = _checksum(b"stable evidence")
    first = retain_artifact_bytes(source, checksum)
    before = first.stat()
    second = retain_artifact_bytes(source, checksum)
    after = second.stat()
    assert second == first
    assert (after.st_ino, after.st_mtime_ns) == (before.st_ino, before.st_mtime_ns)
    assert not list(tmp_path.glob(".retain-*"))


def test_move_publishes_a_staging_file_without_copying_it(tmp_path):
    staging = tmp_path / "file.zip.part"
    staging.write_bytes(b"downloaded bytes")
    inode = staging.stat().st_ino
    checksum = _checksum(b"downloaded bytes")
    destination = tmp_path / f"file.{checksum}.zip"
    retained = retain_artifact_bytes(staging, checksum, destination=destination, move=True)
    assert retained == destination
    assert retained.stat().st_ino == inode  # the same inode: nothing was copied
    assert not staging.exists()
    assert not list(tmp_path.glob(".retain-*"))


def test_move_onto_existing_retained_file_keeps_that_evidence(tmp_path):
    checksum = _checksum(b"same bytes")
    destination = tmp_path / f"file.{checksum}.zip"
    destination.write_bytes(b"same bytes")
    inode = destination.stat().st_ino
    staging = tmp_path / "file.zip.part"
    staging.write_bytes(b"same bytes")
    retain_artifact_bytes(staging, checksum, destination=destination, move=True)
    assert destination.stat().st_ino == inode
    assert not staging.exists()


def test_copy_fails_closed_when_the_volume_would_fill(tmp_path, monkeypatch):
    import shutil
    from collections import namedtuple

    usage = namedtuple("usage", "total used free")
    monkeypatch.setattr(shutil, "disk_usage", lambda _path: usage(100, 100, 0))
    source = tmp_path / "source.zip"
    source.write_bytes(b"needs space")
    with pytest.raises(OSError, match="not enough free space"):
        retain_artifact_bytes(source, _checksum(b"needs space"))
    assert sorted(path.name for path in tmp_path.iterdir()) == ["source.zip"]


def test_damaged_retained_file_is_reported_actionably_and_never_overwritten(tmp_path):
    checksum = _checksum(b"expected")
    destination = tmp_path / f"source.{checksum}.zip"
    destination.write_bytes(b"truncated")
    source = tmp_path / "source.zip"
    source.write_bytes(b"expected")
    with pytest.raises(ValueError, match="never overwritten automatically") as error:
        retain_artifact_bytes(source, checksum)
    assert str(destination) in str(error.value)
    assert destination.read_bytes() == b"truncated"
