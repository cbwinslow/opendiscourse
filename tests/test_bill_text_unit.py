"""Story 11.3: BILLS Connector logic that needs neither network nor database."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from opendiscourse_research.config import settings
from opendiscourse_research.coverage import FIRST_BILLS_CONGRESS, LAST_CONGRESS
from opendiscourse_research.ingestion.bill_text import (
    FIRST_CONGRESS,
    BillTextConnector,
    _matches_origin,
    xml_artifact_key,
)
from opendiscourse_research.ingestion.bill_text import (
    LAST_CONGRESS as BILLS_LAST_CONGRESS,
)
from opendiscourse_research.ingestion.bulk import ArtifactSpec, artifact_path
from opendiscourse_research.providers.govinfo import RemoteZip
from opendiscourse_research.repositories.bill_text import document_source_key

CHANGED = "Sun, 21 Jan 2024 03:00:00 GMT"
REMOTE = RemoteZip(119, "hr", "https://example/x.zip", 100, CHANGED, session=1)


def _partial(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mtime: float) -> Path:
    monkeypatch.setattr(settings, "data_root", str(tmp_path))
    spec = ArtifactSpec("congress.govinfo_bills", "k.zip", "https://example/x.zip", "119/1/k.zip")
    target = artifact_path(spec)
    part = target.with_suffix(target.suffix + ".part")
    part.write_bytes(b"half")
    os.utime(part, (mtime, mtime))
    BillTextConnector._discard_stale_partial(spec, REMOTE)
    return part


def test_a_partial_started_before_the_origin_changed_is_discarded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert not _partial(tmp_path, monkeypatch, mtime=1705806000 - 3600).exists()


def test_a_partial_started_after_the_last_change_is_kept_for_resume(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert _partial(tmp_path, monkeypatch, mtime=1705806000 + 3600).read_bytes() == b"half"


@pytest.mark.parametrize(
    ("metadata", "expected"),
    [
        ({"remote_size": 100, "remote_last_modified": CHANGED}, True),
        ({"remote_size": 101, "remote_last_modified": CHANGED}, False),
        ({}, False),
        (None, False),
    ],
)
def test_origin_match_needs_both_size_and_last_modified(metadata, expected: bool) -> None:
    assert _matches_origin(metadata, REMOTE) is expected


def test_discovery_bounds_come_from_coverage() -> None:
    assert FIRST_CONGRESS == FIRST_BILLS_CONGRESS == 113
    assert BILLS_LAST_CONGRESS == LAST_CONGRESS


def test_document_source_key_includes_the_session() -> None:
    assert document_source_key(1, "hr/BILLS-119hr1ih.xml") == "1/BILLS-119hr1ih.xml"
    assert document_source_key(2, "BILLS-119hr1ih.xml") == "2/BILLS-119hr1ih.xml"


def test_fallback_xml_artifact_key_includes_congress_session_and_type() -> None:
    assert xml_artifact_key(119, 1, "hr", "BILLS-119hr1ih.xml") == "BILLS-119-1-hr/BILLS-119hr1ih.xml"
    assert xml_artifact_key(119, 2, "hr", "BILLS-119hr1ih.xml") == "BILLS-119-2-hr/BILLS-119hr1ih.xml"
    assert xml_artifact_key(119, 1, "hr", "BILLS-119hr1ih.xml") != xml_artifact_key(
        119, 2, "hr", "BILLS-119hr1ih.xml"
    )


def test_constructor_rejects_congresses_before_the_113th_and_unknown_types() -> None:
    with pytest.raises(ValueError, match="starts at Congress 113"):
        BillTextConnector([108])
    with pytest.raises(ValueError, match="unknown bill type"):
        BillTextConnector([119], bill_types=("hr", "bogus"))
    with pytest.raises(ValueError, match="batch_size"):
        BillTextConnector([119], batch_size=0)


class _Stub:
    source_id = "congress.govinfo_bills"
    seen: dict = {}

    def __init__(self, *args, **kwargs) -> None:
        type(self).seen = dict(kwargs)
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

    monkeypatch.setattr(cli, "BillTextConnector", _Stub)
    monkeypatch.setattr(cli, "run_connector", fake_run)
    out = CliRunner().invoke(cli.app, ["sync-bill-text", "--congress", "119"])
    assert out.exit_code == code, out.output
    if code == 1:
        assert "sync-bill-text failed" in out.output and "rerun" in out.output


def test_cli_forwards_download_only(monkeypatch: pytest.MonkeyPatch) -> None:
    from typer.testing import CliRunner

    from opendiscourse_research import cli

    monkeypatch.setattr(cli, "BillTextConnector", _Stub)
    monkeypatch.setattr(cli, "run_connector", lambda connector: None)
    out = CliRunner().invoke(
        cli.app, ["sync-bill-text", "--congress", "119", "--download-only"]
    )
    assert out.exit_code == 0, out.output
    assert _Stub.seen["download_only"] is True
