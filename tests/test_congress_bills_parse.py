"""Congress.gov bill JSON parsing. No database and no network."""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from opendiscourse_research.cli import app
from opendiscourse_research.ingestion.congress_bills import (
    PARTS,
    CongressBillConnector,
    assemble_bill,
    parse_list_page,
)
from opendiscourse_research.ingestion.connector import ConnectorContext
from opendiscourse_research.providers.congress_api import CongressServerError


def test_list_page_reads_the_identity_and_the_next_offset() -> None:
    bills, nxt = parse_list_page(
        json.dumps(
            {
                "bills": [{"congress": 107, "type": "HR", "number": "1"}],
                "pagination": {"next": "https://api.congress.gov/v3/bill/107?offset=250&limit=250"},
            }
        ).encode()
    )
    assert bills == [{"congress": "107", "bill_type": "HR", "number": "1"}]
    assert nxt == 250


def test_detail_becomes_a_bill_with_sponsor_actions_and_subjects() -> None:
    parsed = assemble_bill(
        detail=json.dumps(
            {
                "bill": {
                    "congress": 107,
                    "type": "HR",
                    "number": "1",
                    "title": "A tax bill",
                    "introducedDate": "2001-01-03",
                    "latestAction": {"actionDate": "2001-02-01", "text": "Passed House."},
                    "sponsors": [{"bioguideId": "A000360", "fullName": "Smith, Bob"}],
                    "policyArea": {"name": "Taxation"},
                }
            }
        ).encode(),
        actions=json.dumps(
            {"actions": [{"actionDate": "2001-01-03", "text": "Introduced", "type": "IntroReferral"}]}
        ).encode(),
        subjects=json.dumps(
            {"subjects": {"policyArea": {"name": "Taxation"}, "legislativeSubjects": [{"name": "Income tax"}]}}
        ).encode(),
        cosponsors=json.dumps({"cosponsors": [{"bioguideId": "B000001", "fullName": "Lee, Ann"}]}).encode(),
    )
    assert (parsed["bill_type"], parsed["bill_number"], parsed["introduced_date"]) == ("hr", "1", "2001-01-03")
    assert parsed["sponsorships"][0]["role"] == "sponsor"
    assert parsed["sponsorships"][1]["role"] == "cosponsor"
    assert parsed["actions"][0]["description"] == "Introduced"
    assert parsed["subjects"][1]["label"] == "Income tax"
    assert parsed["record"]["bill"]["title"] == "A tax bill"


def test_congress_108_is_refused_so_govinfo_bills_stay_put() -> None:
    with pytest.raises(ValueError, match="108"):
        CongressBillConnector((108,), http=object())


def _identity(number: str) -> dict[str, str]:
    return {"congress": "106", "bill_type": "SRES", "number": number}


def _detail(number: str) -> bytes:
    return json.dumps(
        {"bill": {"congress": 106, "type": "SRES", "number": number, "title": "A resolution"}}
    ).encode()


def test_a_bill_is_skipped_only_when_every_part_is_loaded() -> None:
    connector = CongressBillConnector((106,), http=object())
    complete = {
        f"106/sres/1/{name}": {"status": "loaded", "local_path": f"/{name}", "artifact_id": name}
        for name in ("detail", *PARTS)
    }
    connector._loaded = complete
    assert connector._bill_complete(_identity("1")) is True
    missing = dict(complete)
    del missing["106/sres/1/cosponsors"]
    connector._loaded = {key.replace("/1/", "/218/"): value for key, value in missing.items()}
    assert connector._bill_complete(_identity("218")) is False


def test_a_broken_part_saves_the_bill_and_the_next_one(monkeypatch: pytest.MonkeyPatch) -> None:
    saved: list[str] = []
    noted: list[str] = []

    class _Client:
        def part(self, congress: int, bill_type: str, number: str, name: str) -> bytes:
            del congress, bill_type
            if number == "218" and name == "cosponsors":
                raise CongressServerError("HTTP 500")
            if number == "3" and name == "detail":
                raise CongressServerError("HTTP 500")
            if name == "detail":
                return _detail(number)
            return b"{}"

    class _Conn:
        def __enter__(self):
            return self

        def __exit__(self, *args: object) -> bool:
            return False

        def commit(self) -> None:
            return None

    connector = CongressBillConnector((106,), http=object())
    connector._client = _Client()

    def keep(key: str, url: str, body: bytes) -> str:
        del url, body
        connector._loaded[key] = {"status": "loaded", "local_path": f"/{key}", "artifact_id": key}
        return key

    def note(identity: dict[str, str], name: str, exc: BaseException) -> None:
        noted.append(f"{identity['number']}/{name}")
        connector._failed[f"106/sres/{identity['number']}/{name}"] = str(exc)

    def save(parsed: dict, *args: object, **kwargs: object) -> str:
        del args, kwargs
        saved.append(parsed["bill_number"])
        return "bill"

    monkeypatch.setattr(connector, "_keep", keep)
    monkeypatch.setattr(connector, "_note_failure", note)
    monkeypatch.setattr(
        "opendiscourse_research.ingestion.congress_bills.connect",
        lambda: _Conn(),
    )
    monkeypatch.setattr(
        "opendiscourse_research.ingestion.congress_bills.ensure_us_legislative_session",
        lambda *args, **kwargs: "session",
    )
    monkeypatch.setattr(
        "opendiscourse_research.ingestion.congress_bills.save_billstatus_bill",
        save,
    )
    counts = {"bills": 0, "skipped": 0, "not_saved": 0}
    connector._drain([_identity("218"), _identity("219"), _identity("3")], counts)
    assert set(saved) == {"218", "219"}
    assert counts["bills"] == 2
    assert counts["not_saved"] == 1
    assert set(noted) == {"218/cosponsors", "3/detail"}


def test_a_clean_run_records_succeeded_and_a_gap_records_partial() -> None:
    class _Run:
        def __init__(self) -> None:
            self.target: dict[str, object] | None = None
            self.partial = False

        def record_target(self, *args: object, **kwargs: object) -> None:
            del args
            self.target = kwargs

        def mark_partial(self) -> None:
            self.partial = True

    class _Client:
        def close(self) -> None:
            return None

    connector = CongressBillConnector((106,), http=object())
    connector._client = _Client()
    connector._identities = lambda congress: []  # type: ignore[method-assign]
    run = _Run()
    connector._run = run  # type: ignore[assignment]
    connector.extract(ConnectorContext(source_id=connector.source_id))
    assert run.partial is False
    assert run.target is not None
    assert run.target["status"] == "succeeded"

    connector._failed = {"106/sres/218/cosponsors": "HTTP 500"}
    connector._finished = False
    run = _Run()
    connector._run = run  # type: ignore[assignment]
    connector.extract(ConnectorContext(source_id=connector.source_id))
    assert run.partial is True
    assert run.target is not None
    assert run.target["status"] == "partial"
    assert connector.result["failed_parts"] == [
        {"key": "106/sres/218/cosponsors", "error": "HTTP 500"}
    ]


def test_command_exits_2_when_a_part_was_not_served(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Partial:
        def __init__(self, congresses: object = None, *, limit: object = None, report: object = None) -> None:
            del congresses, limit, report
            self.result = {"partial": True, "failed_parts": [{"key": "106/sres/218/cosponsors"}]}

    monkeypatch.setattr("opendiscourse_research.catalog.sync_inventory", lambda: None)
    monkeypatch.setattr("opendiscourse_research.ingestion.congress_bills.CongressBillConnector", _Partial)
    monkeypatch.setattr("opendiscourse_research.ingestion.connector.run_connector", lambda connector: None)
    result = CliRunner().invoke(app, ["sync-congress-bills", "--limit", "1"])
    assert result.exit_code == 2
    assert "106/sres/218/cosponsors" in result.stdout
