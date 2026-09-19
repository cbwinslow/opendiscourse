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
