"""Story 11.1: ``research-db sync-votes`` chooses its Connector from a registry, never by branching."""

from __future__ import annotations

from typer.testing import CliRunner

from opendiscourse_research.cli import app
from opendiscourse_research.ingestion.house_votes import HouseVotesConnector
from opendiscourse_research.ingestion.votes import VOTE_CONNECTORS

runner = CliRunner()


def test_the_house_connector_is_registered_and_is_the_default_chamber() -> None:
    assert VOTE_CONNECTORS == {"house": HouseVotesConnector}


def test_an_unknown_chamber_is_refused_naming_the_available_ones() -> None:
    result = runner.invoke(app, ["sync-votes", "--chamber", "senate"])
    assert result.exit_code == 2
    assert "no connector for 'senate'" in result.output and "house" in result.output


def test_a_congress_outside_the_supported_range_fails_with_the_range() -> None:
    result = runner.invoke(app, ["sync-votes", "--congress", "500"])
    assert result.exit_code == 1
    assert "108-119" in result.output


def test_the_command_is_documented() -> None:
    result = runner.invoke(app, ["sync-votes", "--help"])
    assert result.exit_code == 0 and "--chamber" in result.output and "--download-only" in result.output


class _Stub:
    """A Connector that does nothing and reports what it was given."""

    source_id = "stub.votes"
    seen: dict = {}
    partial = False

    def __init__(self, congresses=None, **kwargs) -> None:
        type(self).seen = {"congresses": congresses, **kwargs}
        self.result = {"partial": type(self).partial, "marker": "stub"}

    def discover(self, ctx):
        return ctx

    select = plan = extract = evidence = stage = normalize = validate = publish = checkpoint = discover


def _stubbed(monkeypatch, partial: bool) -> None:

    stub = type("Stub", (_Stub,), {"partial": partial, "seen": {}})
    monkeypatch.setitem(VOTE_CONNECTORS, "house", stub)
    return stub


def test_a_clean_run_exits_0_prints_the_result_and_forwards_every_option(monkeypatch) -> None:
    import json

    stub = _stubbed(monkeypatch, partial=False)
    result = runner.invoke(
        app,
        ["sync-votes", "--congress", "118", "--congress", "119", "--batch-size", "7", "--pace", "0.5", "--download-only"],
    )
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout[result.stdout.index("{") :]) == {"partial": False, "marker": "stub"}
    seen = stub.seen
    assert seen["congresses"] == [118, 119]
    assert seen["batch_size"] == 7 and seen["download_pace_seconds"] == 0.5 and seen["download_only"] is True
    assert callable(seen["report"])


def test_a_partial_run_exits_2_but_still_prints_the_result(monkeypatch) -> None:
    import json

    stub = _stubbed(monkeypatch, partial=True)
    result = runner.invoke(app, ["sync-votes"])
    assert result.exit_code == 2, result.output
    assert json.loads(result.stdout[result.stdout.index("{") :])["partial"] is True
    assert stub.seen["congresses"] is None and stub.seen["batch_size"] == 50 and stub.seen["download_only"] is False
    assert stub.seen["download_pace_seconds"] == 0.25


def test_a_failing_connector_exits_1_with_a_resume_hint(monkeypatch) -> None:
    class Boom(_Stub):
        def discover(self, ctx):
            raise RuntimeError("origin down")

    monkeypatch.setitem(VOTE_CONNECTORS, "house", Boom)
    result = runner.invoke(app, ["sync-votes"])
    assert result.exit_code == 1
    assert "sync-votes failed: origin down" in result.output and "rerun" in result.output
