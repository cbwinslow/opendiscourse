"""Story 9.5: BILLSTATUS Connector logic that needs neither network nor database."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from opendiscourse_research.config import settings
from opendiscourse_research.ingestion.billstatus import (
    BillStatusConnector,
    _matches_origin,
)
from opendiscourse_research.ingestion.bulk import ArtifactSpec, artifact_path
from opendiscourse_research.providers.govinfo import RemoteZip

CHANGED = "Sun, 21 Jan 2024 03:00:00 GMT"  # 1705806000
REMOTE = RemoteZip(108, "hr", "https://example/x.zip", 100, CHANGED)


def _partial(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mtime: float) -> Path:
    monkeypatch.setattr(settings, "data_root", str(tmp_path))
    spec = ArtifactSpec("congress.govinfo_billstatus", "k.zip", "https://example/x.zip", "108/k.zip")
    target = artifact_path(spec)
    part = target.with_suffix(target.suffix + ".part")
    part.write_bytes(b"half")
    os.utime(part, (mtime, mtime))
    BillStatusConnector._discard_stale_partial(spec, REMOTE)
    return part


def test_a_partial_started_before_the_origin_changed_is_discarded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert not _partial(tmp_path, monkeypatch, mtime=1705806000 - 3600).exists()


def test_a_partial_started_after_the_last_change_is_kept_for_resume(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert _partial(tmp_path, monkeypatch, mtime=1705806000 + 3600).read_bytes() == b"half"


def test_a_partial_is_discarded_when_the_origin_date_cannot_be_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "data_root", str(tmp_path))
    spec = ArtifactSpec("congress.govinfo_billstatus", "k.zip", "https://example/x.zip", "108/k.zip")
    target = artifact_path(spec)
    part = target.with_suffix(target.suffix + ".part")
    part.write_bytes(b"half")
    BillStatusConnector._discard_stale_partial(spec, RemoteZip(108, "hr", "u", 1, "not a date"))
    assert not part.exists()


@pytest.mark.parametrize(
    ("metadata", "expected"),
    [
        ({"remote_size": 100, "remote_last_modified": CHANGED}, True),
        ({"remote_size": 101, "remote_last_modified": CHANGED}, False),
        ({"remote_size": 100, "remote_last_modified": "Mon, 01 Jan 2024 00:00:00 GMT"}, False),
        ({}, False),  # a legacy registry row records no origin state
        (None, False),
    ],
)
def test_origin_match_needs_both_size_and_last_modified(metadata, expected: bool) -> None:
    assert _matches_origin(metadata, REMOTE) is expected


def test_constructor_rejects_unknown_bill_types_and_bad_batches() -> None:
    with pytest.raises(ValueError, match="unknown bill type"):
        BillStatusConnector(bill_types=("hr", "bogus"))
    with pytest.raises(ValueError, match="batch_size"):
        BillStatusConnector(batch_size=0)


def test_repeated_bill_types_are_de_duplicated() -> None:
    assert BillStatusConnector(bill_types=("hr", "s", "hr")).bill_types == ("hr", "s")


class _Stub:
    """Stands in for BillStatusConnector so the CLI's exit codes can be checked."""

    source_id = "congress.govinfo_billstatus"

    def __init__(self, *args, **kwargs) -> None:
        self.result: dict = {}


@pytest.mark.parametrize(
    ("raises", "result", "code"),
    [
        (None, {"partial": False}, 0),
        (None, {"partial": True}, 2),
        (RuntimeError("GovInfo is down"), {}, 1),
        (OSError("disk full"), {}, 1),
    ],
)
def test_cli_exit_codes_distinguish_success_partial_and_failure(
    monkeypatch: pytest.MonkeyPatch, raises: BaseException | None, result: dict, code: int
) -> None:
    from typer.testing import CliRunner

    from opendiscourse_research import cli

    def fake_run(connector) -> None:
        if raises is not None:
            raise raises
        connector.result = result

    monkeypatch.setattr(cli, "BillStatusConnector", _Stub)
    monkeypatch.setattr(cli, "run_connector", fake_run)
    out = CliRunner().invoke(cli.app, ["sync-billstatus", "--congress", "108"])
    assert out.exit_code == code, out.output
    if code == 1:
        assert "sync-billstatus failed" in out.output and "rerun" in out.output
