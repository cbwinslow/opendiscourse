"""Story 9.5: the GovInfo BILLSTATUS client. No network; responses are faked."""

from __future__ import annotations

import httpx
import pytest

from opendiscourse_research.providers.govinfo import (
    BILL_TYPES,
    ZIP_URL,
    GovInfoBillStatus,
    GovInfoError,
    GovInfoNotFound,
    member_identity,
)
from opendiscourse_research.providers.paced import PacedClient, retry_after_seconds


def _response(method: str, url: str, status: int = 200, **kwargs) -> httpx.Response:
    return httpx.Response(status, request=httpx.Request(method, url), **kwargs)


class _Script:
    """A fake transport that replays queued responses per URL and counts calls."""

    def __init__(self, replies: dict[str, list]) -> None:
        self.replies = {url: list(items) for url, items in replies.items()}
        self.calls: list[tuple[str, str]] = []

    def __call__(self, method: str, url: str) -> httpx.Response:
        self.calls.append((method, url))
        item = self.replies[url].pop(0)
        if isinstance(item, Exception):
            raise item
        return _response(method, url, **item)


def _client(script: _Script) -> GovInfoBillStatus:
    return GovInfoBillStatus(send=script, pace_seconds=0, sleep=lambda _s: None)


def test_zip_info_reads_size_and_last_modified_from_head() -> None:
    url = ZIP_URL.format(congress=108, bill_type="hr")
    script = _Script(
        {url: [{"headers": {"content-length": "1783250", "last-modified": "Sat, 20 Jan 2024 00:55:38 GMT"}}]}
    )
    remote = _client(script).zip_info(108, "hr")
    assert (remote.size, remote.last_modified, remote.url) == (
        1783250,
        "Sat, 20 Jan 2024 00:55:38 GMT",
        url,
    )
    assert script.calls == [("HEAD", url)]


@pytest.mark.parametrize(
    "headers",
    [
        {},  # no length at all: unknown size must fail closed
        {"content-length": "0", "last-modified": "Sat, 20 Jan 2024 00:55:38 GMT"},
        {"content-length": "10"},  # no Last-Modified: a refresh could not be detected
    ],
)
def test_zip_info_fails_closed_without_a_usable_size_or_date(headers: dict) -> None:
    url = ZIP_URL.format(congress=108, bill_type="hr")
    with pytest.raises(GovInfoError, match="no usable size"):
        _client(_Script({url: [{"headers": headers}]})).zip_info(108, "hr")


def test_a_permanent_client_error_is_not_retried() -> None:
    url = ZIP_URL.format(congress=108, bill_type="hr")
    script = _Script({url: [{"status": 404}, {"status": 200}]})
    with pytest.raises(GovInfoNotFound, match="404"):
        _client(script).zip_info(108, "hr")
    assert len(script.calls) == 1


def test_a_transient_server_error_is_retried_once() -> None:
    url = ZIP_URL.format(congress=108, bill_type="hr")
    ok = {"headers": {"content-length": "5", "last-modified": "Sat, 20 Jan 2024 00:55:38 GMT"}}
    script = _Script({url: [{"status": 503}, ok]})
    assert _client(script).zip_info(108, "hr").size == 5
    assert len(script.calls) == 2


def test_persistent_server_errors_give_up_after_one_retry() -> None:
    url = ZIP_URL.format(congress=108, bill_type="hr")
    script = _Script({url: [{"status": 500}, {"status": 500}, {"status": 200}]})
    with pytest.raises(GovInfoError):
        _client(script).zip_info(108, "hr")
    assert len(script.calls) == 2


def test_transport_errors_are_retried_then_reported() -> None:
    url = ZIP_URL.format(congress=108, bill_type="hr")
    script = _Script({url: [httpx.ConnectTimeout("slow"), httpx.ConnectTimeout("slow")]})
    with pytest.raises(GovInfoError, match="slow"):
        _client(script).zip_info(108, "hr")
    assert len(script.calls) == 2


def test_requests_are_paced() -> None:
    url = ZIP_URL.format(congress=108, bill_type="hr")
    ok = {"headers": {"content-length": "5", "last-modified": "x"}}
    sleeps: list[float] = []
    client = GovInfoBillStatus(
        send=_Script({url: [ok, ok]}), pace_seconds=1.0, sleep=sleeps.append
    )
    client.zip_info(108, "hr")
    client.zip_info(108, "hr")
    assert sleeps and all(0 < s <= 1.0 for s in sleeps)


def test_congresses_lists_only_numeric_folders_sorted() -> None:
    root = "https://www.govinfo.gov/bulkdata/json/BILLSTATUS"
    files = [
        {"name": "119", "folder": True},
        {"name": "108", "folder": True},
        {"name": "readme.txt", "folder": False},
        {"name": "notes", "folder": True},
    ]
    assert _client(_Script({root: [{"json": {"files": files}}]})).congresses() == [108, 119]


def test_congresses_refuses_an_empty_listing() -> None:
    root = "https://www.govinfo.gov/bulkdata/json/BILLSTATUS"
    with pytest.raises(GovInfoError, match="no Congress folders"):
        _client(_Script({root: [{"json": {"files": []}}]})).congresses()


def test_manifest_lists_xml_names_only() -> None:
    url = "https://www.govinfo.gov/bulkdata/json/BILLSTATUS/108/hr"
    files = [
        {"name": "BILLSTATUS-108hr1.xml"},
        {"name": "BILLSTATUS-108-hr.zip"},
        {"name": "BILLSTATUS-108hr2.xml"},
    ]
    names = _client(_Script({url: [{"json": {"files": files}}]})).manifest_xml(108, "hr")
    assert names == {"BILLSTATUS-108hr1.xml", "BILLSTATUS-108hr2.xml"}


def test_an_empty_manifest_is_an_error_never_a_zero() -> None:
    url = "https://www.govinfo.gov/bulkdata/json/BILLSTATUS/108/hr"
    with pytest.raises(GovInfoError, match="no XML"):
        _client(_Script({url: [{"json": {"files": [{"name": "x.zip"}]}}]})).manifest_xml(108, "hr")


def test_an_unreadable_manifest_is_an_error() -> None:
    url = "https://www.govinfo.gov/bulkdata/json/BILLSTATUS/108/hr"
    with pytest.raises(GovInfoError, match="unreadable"):
        _client(_Script({url: [{"json": {"unexpected": []}}]})).manifest_xml(108, "hr")


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("BILLSTATUS-118hr184.xml", (118, "hr", 184)),
        ("BILLSTATUS-118hres5.xml", (118, "hres", 5)),
        ("BILLSTATUS-108s1.xml", (108, "s", 1)),
        ("BILLSTATUS-108sres27.xml", (108, "sres", 27)),
        ("BILLSTATUS-119hconres10.xml", (119, "hconres", 10)),
        ("BILLSTATUS-119sjres3.xml", (119, "sjres", 3)),
        ("BILLSTATUS-118-hr.zip", None),
        ("BILLSTATUS-118xyz9.xml", None),
        ("../BILLSTATUS-118hr1.xml", None),
        ("BILLSTATUS-118hr.xml", None),
    ],
)
def test_member_identity_parses_only_real_bill_file_names(name: str, expected) -> None:
    assert member_identity(name) == expected


def test_every_bill_type_round_trips_through_member_identity() -> None:
    for bill_type in BILL_TYPES:
        assert member_identity(f"BILLSTATUS-110{bill_type}42.xml") == (110, bill_type, 42)


def test_a_403_is_an_error_but_not_a_not_found() -> None:
    url = ZIP_URL.format(congress=108, bill_type="hr")
    with pytest.raises(GovInfoError) as raised:
        _client(_Script({url: [{"status": 403}]})).zip_info(108, "hr")
    assert not isinstance(raised.value, GovInfoNotFound)


# -- the shared transport ------------------------------------------------------
def test_retry_after_accepts_seconds_and_http_dates_and_caps_both() -> None:
    from datetime import UTC, datetime

    now = datetime(2026, 9, 19, 12, 0, 0, tzinfo=UTC)
    assert retry_after_seconds("7") == 7
    assert retry_after_seconds("9999") == 30
    assert retry_after_seconds("Sat, 19 Sep 2026 12:00:10 GMT", now) == 10
    assert retry_after_seconds("Sat, 19 Sep 2026 11:00:00 GMT", now) == 0  # already past
    assert retry_after_seconds("Sat, 19 Sep 2026 13:00:00 GMT", now) == 30
    assert retry_after_seconds("soon") is None and retry_after_seconds("") is None


def test_a_last_failed_attempt_does_not_sleep_for_retry_after() -> None:
    sleeps: list[float] = []
    calls: list[str] = []

    def always_throttled(method: str, url: str) -> httpx.Response:
        calls.append(url)
        return _response(method, url, 429, headers={"Retry-After": "20"})

    client = PacedClient(always_throttled, 0, sleeps.append)
    with pytest.raises(RuntimeError):
        client.request("GET", "https://example/x")
    assert len(calls) == 2
    assert sleeps == [20.0]  # once, between the attempts; not again before giving up


def test_the_error_factory_sees_the_status() -> None:
    seen: list[int | None] = []

    def factory(message: str, status: int | None) -> Exception:
        seen.append(status)
        return ValueError(message)

    def gone(method: str, url: str) -> httpx.Response:
        return _response(method, url, 410)

    with pytest.raises(ValueError):
        PacedClient(gone, 0, lambda _s: None, factory).request("GET", "https://example/x")
    assert seen == [410]
