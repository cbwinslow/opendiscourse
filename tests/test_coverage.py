"""Story 9.3: the coverage comparator reports expected/loaded/missing without network or writes."""

from __future__ import annotations

import json
import zipfile
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest

from opendiscourse_research import coverage
from opendiscourse_research.coverage import (
    BILL_TYPES,
    OfficialCache,
    build_report,
    cell,
    expected_members,
    format_table,
    scan_lake,
)
from opendiscourse_research.providers.official_counts import (
    OfficialCountError,
    OfficialCounts,
)

TODAY = date(2026, 9, 19)


class FakeOfficial:
    """Stands in for OfficialCounts; counts calls and can fail selected lookups."""

    def __init__(self, bills=5, senate=10, house=20, first=108, fail=()):
        self.bills, self.senate, self.house, self.first = bills, senate, house, first
        self.fail = set(fail)
        self.calls = 0

    def _go(self, name: str, value: int, arg: object = None) -> int:
        self.calls += 1
        if name in self.fail or f"{name}:{arg}" in self.fail:
            raise OfficialCountError(f"{name}: down")
        return value

    def first_billstatus_congress(self) -> int:
        return self._go("first", self.first)

    def billstatus(self, congress: int, bill_type: str) -> int:
        return self._go("billstatus", self.bills, bill_type)

    def senate_votes(self, congress: int, session: int) -> int:
        return self._go("senate", self.senate, session)

    def house_rolls(self, year: int) -> int:
        return self._go("house", self.house, year)


def _loaded(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "bills": {},
        "actions": {},
        "roll_calls": {},
        "memberships": {},
        "bioguide_ids": set(),
        "runs_unattributed": 3,
        "runs_total": 4,
        "fec_stage_rows_estimate": 10,
    }
    base.update(overrides)
    return base


def _report(tmp_path: Path, official=None, loaded=None, lake=None, members=None, **kw):
    cache = OfficialCache(tmp_path / "official.json", **kw)
    result = build_report(
        [118],
        official=official or FakeOfficial(),
        cache=cache,
        loaded=loaded or _loaded(),
        lake=lake or (lambda c: None),
        members=members or {118: set()},
        today=TODAY,
    )
    return result, cache


def test_start_confirmed_from_root_manifest(tmp_path):
    result, _ = _report(tmp_path)
    assert result["start_confirmed"] == {"confirmed": True, "first_official_congress": 108}


def test_start_unknown_when_root_manifest_unreachable(tmp_path):
    result, _ = _report(tmp_path, official=FakeOfficial(fail={"first"}))
    assert result["start_confirmed"]["confirmed"] == "unknown"
    assert any(error.startswith("billstatus:first_congress") for error in result["errors"])


def test_earlier_official_congress_is_not_confirmed(tmp_path):
    result, _ = _report(tmp_path, official=FakeOfficial(first=107))
    assert result["start_confirmed"]["confirmed"] is False


def test_unloaded_congress_is_all_missing(tmp_path):
    result, _ = _report(tmp_path, official=FakeOfficial(bills=5))
    bills = result["congresses"][0]["bills"]
    assert (bills["expected"], bills["loaded"], bills["missing"]) == (40, 0, 40)
    assert bills["by_type"]["hr"]["missing"] == 5 and bills["status"] == "incomplete"


def test_lake_drift_shows_missing_on_disk(tmp_path):
    lake = {t: {"bills": 5, "actions": 7} for t in BILL_TYPES}
    lake["hr"] = {"bills": 4, "actions": 7}
    result, _ = _report(tmp_path, lake=lambda c: lake)
    row = result["congresses"][0]["bills"]["by_type"]["hr"]
    assert (row["on_disk"], row["missing_on_disk"]) == (4, 1)
    # a drifting lake is not a verified action basis
    assert result["congresses"][0]["actions"]["basis"] == "lake_archive_unverified"


def test_matching_lake_gives_verified_action_basis(tmp_path):
    lake = {t: {"bills": 5, "actions": 7} for t in BILL_TYPES}
    result, _ = _report(tmp_path, lake=lambda c: lake)
    actions = result["congresses"][0]["actions"]
    assert actions["expected"] == 56 and actions["basis"] == "lake_archive"


def test_roll_calls_without_member_votes_are_flagged(tmp_path):
    loaded = _loaded(
        roll_calls={118: {"senate": {"roll_calls": 3, "without_votes": 3}}}
    )
    result, _ = _report(tmp_path, loaded=loaded)
    votes = result["congresses"][0]["votes"]
    assert votes["roll_calls_without_votes"] == {"house": 0, "senate": 3}
    assert votes["senate"]["expected"] == 20 and votes["senate"]["loaded"] == 3


def test_overloaded_reports_surplus_not_negative_missing():
    assert cell(5, 8, "x") == {
        "expected": 5, "loaded": 8, "missing": 0, "surplus": 3,
        "status": "complete", "basis": "x",
    }


def test_failed_fetch_is_unknown_never_zero(tmp_path):
    result, _ = _report(tmp_path, official=FakeOfficial(fail={"senate"}))
    senate = result["congresses"][0]["votes"]["senate"]
    assert senate["expected"] is None and senate["missing"] is None
    assert senate["status"] == "unknown"
    assert "unknown" not in json.dumps(result["congresses"][0]["votes"]["house"])
    assert "?" in format_table(result)


def test_warm_cache_makes_no_requests_and_refresh_refetches(tmp_path):
    _, cache = _report(tmp_path)
    cache.save()
    assert cache.requests > 0
    official = FakeOfficial()
    _, warm = _report(tmp_path, official=official)
    assert official.calls == 0 and warm.requests == 0
    official = FakeOfficial()
    _, refreshed = _report(tmp_path, official=official, refresh=True)
    assert official.calls == refreshed.requests > 0


def test_failures_are_not_cached(tmp_path):
    _, cache = _report(tmp_path, official=FakeOfficial(fail={"senate"}))
    cache.save()
    assert not any(key.startswith("senate:") for key in json.loads((tmp_path / "official.json").read_text())["entries"])


def test_volatile_entries_expire_after_a_day(tmp_path):
    clock = {"now": datetime(2026, 9, 19, tzinfo=UTC)}
    cache = OfficialCache(tmp_path / "o.json", now=lambda: clock["now"])
    assert cache.get("k", lambda: 1, volatile=True) == 1
    clock["now"] += timedelta(hours=2)
    assert cache.get("k", lambda: 2, volatile=True) == 1
    clock["now"] += timedelta(days=2)
    assert cache.get("k", lambda: 2, volatile=True) == 2
    assert cache.get("stable", lambda: 9) == 9
    clock["now"] += timedelta(days=30)
    assert cache.get("stable", lambda: 10) == 9


def test_members_use_term_overlap_and_bioguide_only(tmp_path):
    path = tmp_path / "leg.yaml"
    path.write_text(
        "- id: {bioguide: A000001}\n  name: {last: Same}\n"
        "  terms: [{start: '2003-01-07', end: '2005-01-03'}]\n"
        "- id: {bioguide: B000002}\n  name: {last: Same}\n"
        "  terms: [{start: '2005-01-04', end: '2007-01-03'}]\n"
        "- id: {}\n  terms: [{start: '2003-01-07', end: '2005-01-03'}]\n"
    )
    found = expected_members([path], [108, 109])
    assert found[108] == {"A000001"}
    assert found[109] == {"B000002"}


def test_members_loaded_intersects_expected(tmp_path):
    loaded = _loaded(bioguide_ids={"A1", "Z9"}, memberships={118: {"A1", "Z9"}})
    result, _ = _report(tmp_path, loaded=loaded, members={118: {"A1", "B2"}})
    members = result["congresses"][0]["members"]
    assert members["people"]["loaded"] == 1 and members["memberships"]["missing"] == 1
    assert members["memberships"]["basis"] == "legislators_yaml"


def test_scan_lake_counts_and_caches(tmp_path, monkeypatch):
    root = tmp_path / "billstatus"
    archive = root / "108" / "hr" / "BILLSTATUS-108-hr.zip"
    archive.parent.mkdir(parents=True)
    xml = (
        "<billStatus><bill><number>{n}</number><type>HR</type><congress>108</congress>"
        "<actions><item/><item/></actions></bill></billStatus>"
    )
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr("BILLSTATUS-108hr1.xml", xml.format(n=1))
        bundle.writestr("BILLSTATUS-108hr2.xml", xml.format(n=2))
        bundle.writestr("BILLSTATUS-108hr3.xml", "<broken")
    monkeypatch.setattr(coverage, "BILLSTATUS_ROOT", root)
    cache = tmp_path / "lake.json"
    assert scan_lake(108, cache) == {"hr": {"bills": 2, "actions": 4, "malformed": 1}}
    monkeypatch.setattr(coverage, "_bill_details", lambda content: pytest.fail("rescanned"))
    assert scan_lake(108, cache)["hr"]["bills"] == 2
    assert scan_lake(109, cache) is None


def _response(url: str, status: int = 200, **kwargs: Any) -> httpx.Response:
    return httpx.Response(status, request=httpx.Request("GET", url), **kwargs)


def test_provider_parses_each_source_and_paces():
    sleeps: list[float] = []

    def get(url: str) -> httpx.Response:
        if "BILLSTATUS/108/hr" in url:
            return _response(url, json={"files": [{"name": "a.xml"}, {"name": "b.xml"}, {"name": "x.json"}]})
        if url.endswith("BILLSTATUS"):
            return _response(url, json={"files": [{"name": "119", "folder": True}, {"name": "108", "folder": True}, {"name": "resources", "folder": True}]})
        if "vote_menu" in url:
            return _response(url, content=b"<vote_summary><votes><vote/><vote/><vote/></votes></vote_summary>")
        return _response(url, text='rollnumber=5 rollnumber=677 rollnumber=12')

    client = OfficialCounts(get=get, pace_seconds=5, sleep=sleeps.append)
    assert client.billstatus(108, "hr") == 2
    assert client.first_billstatus_congress() == 108
    assert client.senate_votes(108, 1) == 3
    assert client.house_rolls(2003) == 677
    assert sleeps and all(0 < wait <= 5 for wait in sleeps)  # later requests were paced


def test_provider_retries_once_then_raises():
    calls = []

    def get(url: str) -> httpx.Response:
        calls.append(url)
        return _response(url, status=503)

    client = OfficialCounts(get=get, pace_seconds=0, sleep=lambda s: None)
    with pytest.raises(OfficialCountError):
        client.house_rolls(2003)
    assert len(calls) == 2


def test_provider_rejects_unreadable_manifest():
    client = OfficialCounts(get=lambda u: _response(u, content=b"<html>"), pace_seconds=0, sleep=lambda s: None)
    with pytest.raises(OfficialCountError):
        client.billstatus(108, "hr")


def test_cli_prints_table_and_pure_json_and_rejects_bad_congress(tmp_path, monkeypatch):
    from typer.testing import CliRunner

    from opendiscourse_research import cli

    result, _ = _report(tmp_path)
    seen: dict[str, Any] = {}

    def fake_report(congresses, refresh, advance=None):
        seen.update(congresses=congresses, refresh=refresh)
        if advance:
            advance("x")
        return result

    monkeypatch.setattr(cli, "coverage_report", fake_report)
    runner = CliRunner()
    table = runner.invoke(
        cli.app, ["coverage", "--congress", "118", "--congress", "118", "--refresh-official"]
    )
    assert table.exit_code == 0 and "118" in table.output
    assert seen == {"congresses": [118], "refresh": True}  # de-duplicated
    as_json = runner.invoke(cli.app, ["coverage", "--json"])
    assert json.loads(as_json.output)["kind"] == "coverage"  # stdout is pure JSON
    bad = runner.invoke(cli.app, ["coverage", "--congress", "120"])
    assert bad.exit_code == 2 and "Traceback" not in bad.output


def test_partial_failures_make_totals_unknown_not_partial_sums(tmp_path):
    result, _ = _report(tmp_path, official=FakeOfficial(fail={"billstatus:sres"}))
    row = result["congresses"][0]
    assert row["bills"]["expected"] is None and row["bills"]["by_type"]["hr"]["expected"] == 5
    assert row["bills"]["by_type"]["sres"]["status"] == "unknown"
    assert row["votes"]["house"]["expected"] == 40
    result, _ = _report(tmp_path / "b", official=FakeOfficial(fail={"house:2023"}))
    assert result["congresses"][0]["votes"]["house"]["expected"] is None


def test_loaded_counts_flow_into_the_row_and_surplus_cannot_hide_a_gap(tmp_path):
    loaded = _loaded(
        bills={118: {"hr": 9, "s": 2, "HR": 4}}, actions={118: 11},
    )
    result, _ = _report(tmp_path, loaded=loaded)
    bills = result["congresses"][0]["bills"]
    assert bills["by_type"]["hr"]["surplus"] == 4 and bills["by_type"]["s"]["missing"] == 3
    assert bills["status"] == "incomplete"  # s is short even though hr overshoots
    assert bills["loaded"] == 11 and bills["loaded_other_types"] == {"HR": 4}
    assert result["congresses"][0]["actions"]["loaded"] == 11


def test_missing_legislators_is_unknown_not_complete(tmp_path):
    result, _ = _report(tmp_path, members={})
    for name in ("people", "memberships"):
        cell_ = result["congresses"][0]["members"][name]
        assert cell_["expected"] is None and cell_["status"] == "unknown"


def test_unknown_fec_estimate_is_none(tmp_path):
    for value in (None, -1):
        result, _ = _report(tmp_path, loaded=_loaded(fec_stage_rows_estimate=value))
        assert result["unattributed"]["fec_stage_rows_estimate"] is None
        assert "FEC stage rows (estimate): ?" in format_table(result)


def test_table_labels_lower_trust_columns():
    header = format_table(
        {
            "start_confirmed": {"first_official_congress": 108, "confirmed": True},
            "congresses": [],
            "unattributed": {
                "runs_without_code_version": 0, "runs_total": 0, "fec_stage_rows_estimate": 0,
            },
            "errors": [],
        }
    )
    assert "actions(lake)" in header and "memberships(yaml)" in header


def test_in_progress_congress_and_current_year_are_refetched_after_a_day(tmp_path):
    clock = {"now": datetime(2026, 9, 19, tzinfo=UTC)}

    def run(official):
        cache = OfficialCache(tmp_path / "o.json", now=lambda: clock["now"])
        result = build_report(
            [119], official=official, cache=cache, loaded=_loaded(),
            lake=lambda c: None, members={119: set()}, today=TODAY,
        )
        cache.save()
        return result, cache

    first, _ = run(FakeOfficial())
    assert first["congresses"][0]["in_progress"] is True
    clock["now"] += timedelta(days=2)
    official = FakeOfficial()
    run(official)
    # 8 bill types + 2 senate sessions + house 2026 refetch; closed year 2025 does not
    assert official.calls == 8 + 2 + 1


def test_entry_cached_while_volatile_is_refetched_once_it_is_closed(tmp_path):
    clock = {"now": datetime(2026, 9, 19, tzinfo=UTC)}
    cache = OfficialCache(tmp_path / "o.json", now=lambda: clock["now"])
    assert cache.get("k", lambda: 1, volatile=True) == 1
    assert cache.get("k", lambda: 5, volatile=False) == 5  # source stopped changing
    assert cache.get("k", lambda: 9, volatile=False) == 5  # now settled


def test_failed_refetch_falls_back_to_the_stale_value(tmp_path):
    clock = {"now": datetime(2026, 9, 19, tzinfo=UTC)}
    cache = OfficialCache(tmp_path / "o.json", now=lambda: clock["now"])
    cache.get("k", lambda: 7, volatile=True)
    clock["now"] += timedelta(days=3)

    def boom() -> int:
        raise OfficialCountError("down")

    assert cache.get("k", boom, volatile=True) == 7 and cache.errors


@pytest.mark.parametrize(
    "content", ["[]", '{"entries": []}', '{"entries": {"k": {"value": 1}}}',
                '{"entries": {"k": {"value": "x", "fetched_at": "nope"}}}', "not json"],
)
def test_malformed_cache_is_treated_as_empty(tmp_path, content):
    path = tmp_path / "o.json"
    path.write_text(content)
    cache = OfficialCache(path)
    assert cache.get("k", lambda: 3) == 3 and cache.requests == 1


def test_scan_lake_survives_a_corrupt_archive_and_reports_it(tmp_path, monkeypatch):
    root = tmp_path / "billstatus"
    archive = root / "108" / "hr" / "BILLSTATUS-108-hr.zip"
    archive.parent.mkdir(parents=True)
    archive.write_bytes(b"not a zip")
    monkeypatch.setattr(coverage, "BILLSTATUS_ROOT", root)
    found = scan_lake(108, tmp_path / "lake.json")
    assert "unreadable" in found["hr"]
    lake = {t: found.get(t, {"bills": 0, "actions": 0}) for t in BILL_TYPES}
    result, _ = _report(tmp_path, official=FakeOfficial(bills=0, fail={"x"}), lake=lambda c: lake)
    assert result["congresses"][0]["actions"]["basis"] == "lake_archive_unverified"


def test_expected_members_skips_malformed_records(tmp_path):
    path = tmp_path / "leg.yaml"
    path.write_text(
        "- just a string\n- id: [1, 2]\n"
        "- id: {bioguide: A1}\n  terms: [5, {start: '2003-01-07', end: '2005-01-03'}]\n"
    )
    assert expected_members([path], [108]) == {108: {"A1"}}


def test_coverage_report_wires_cache_range_and_output_paths(tmp_path, monkeypatch):
    seen: dict[str, Any] = {}

    class Recording(FakeOfficial):
        pass

    monkeypatch.setattr(coverage, "_meta_dir", lambda: tmp_path / "meta")
    monkeypatch.setattr(coverage, "OfficialCounts", Recording)
    monkeypatch.setattr(coverage, "loaded_counts", lambda: _loaded())
    monkeypatch.setattr(coverage, "scan_lake", lambda c, path: seen.setdefault("lake", path))
    leg = tmp_path / "leg.yaml"
    leg.write_text("- id: {bioguide: A1}\n  terms: [{start: '2023-01-03', end: '2025-01-03'}]\n")
    monkeypatch.setattr(coverage, "legislators_paths", lambda: [leg])
    monkeypatch.setattr(coverage, "scan_lake", lambda c, path: None)

    result = coverage.coverage_report([119, 118, 118], refresh_official=True)
    assert [row["congress"] for row in result["congresses"]] == [118, 119]
    assert (tmp_path / "meta" / "official.json").is_file()
    assert json.loads((tmp_path / "meta" / "latest.json").read_text())["kind"] == "coverage"
    assert result["congresses"][0]["members"]["people"]["expected"] == 1
    assert result["official_requests"] > 0  # refresh really refetched
    with pytest.raises(ValueError, match="108-119"):
        coverage.coverage_report([120])


def test_coverage_report_keeps_fetched_counts_when_a_later_step_fails(tmp_path, monkeypatch):
    monkeypatch.setattr(coverage, "_meta_dir", lambda: tmp_path / "meta")
    monkeypatch.setattr(coverage, "OfficialCounts", FakeOfficial)
    monkeypatch.setattr(coverage, "legislators_paths", list)
    monkeypatch.setattr(coverage, "scan_lake", lambda c, path: None)

    def broken():
        raise RuntimeError("db down")

    monkeypatch.setattr(coverage, "loaded_counts", broken)
    with pytest.raises(RuntimeError):
        coverage.coverage_report([118])
    assert not (tmp_path / "meta" / "latest.json").exists()


def test_provider_never_turns_an_empty_200_into_zero():
    empty_manifest = lambda u: _response(u, json={"files": []})
    empty_menu = lambda u: _response(u, content=b"<vote_summary><votes/></vote_summary>")
    with pytest.raises(OfficialCountError):
        OfficialCounts(get=empty_manifest, pace_seconds=0).billstatus(108, "hr")
    with pytest.raises(OfficialCountError):
        OfficialCounts(get=empty_menu, pace_seconds=0).senate_votes(108, 1)


def test_provider_fails_fast_on_404_and_retries_429_after_retry_after():
    calls, sleeps = [], []

    def not_found(url):
        calls.append(url)
        return _response(url, status=404)

    with pytest.raises(OfficialCountError):
        OfficialCounts(get=not_found, pace_seconds=0, sleep=sleeps.append).house_rolls(2003)
    assert len(calls) == 1

    def throttled(url):
        calls.append(url)
        if len(calls) == 1:
            return _response(url, status=429, headers={"Retry-After": "7"})
        return _response(url, text="rollnumber=9")

    calls.clear()
    assert OfficialCounts(get=throttled, pace_seconds=0, sleep=sleeps.append).house_rolls(2003) == 9
    assert 7 in sleeps


def test_default_get_sends_user_agent_and_json_accept_only_for_govinfo(monkeypatch):
    from opendiscourse_research.providers import official_counts

    sent: list[dict[str, str]] = []

    def fake_get(url, headers, **kwargs):
        sent.append(headers)
        return _response(url)

    monkeypatch.setattr(official_counts.httpx, "get", fake_get)
    official_counts._default_get("https://www.govinfo.gov/bulkdata/json/BILLSTATUS/118/hr")
    official_counts._default_get("https://clerk.house.gov/evs/2023/index.asp")
    assert sent[0]["Accept"] == "application/json" and "Accept" not in sent[1]
    assert all(h["User-Agent"].startswith("opendiscourse-research") for h in sent)
