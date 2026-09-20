"""Story 11.1: the House Clerk client. No network; responses are faked."""

from __future__ import annotations

from datetime import date

import httpx
import pytest

from opendiscourse_research.providers.clerk import (
    ClerkError,
    ClerkHouseVotes,
    ClerkNotFound,
    roll_url,
)

MODIFIED = "Tue, 01 Sep 2020 12:06:52 GMT"


def _response(method: str, url: str, status: int = 200, **kwargs) -> httpx.Response:
    return httpx.Response(status, request=httpx.Request(method, url), **kwargs)


class _Script:
    """Replays queued responses per URL and records every call."""

    def __init__(self, replies: dict[str, list]) -> None:
        self.replies = {url: list(items) for url, items in replies.items()}
        self.calls: list[tuple[str, str]] = []

    def __call__(self, method: str, url: str) -> httpx.Response:
        self.calls.append((method, url))
        item = self.replies[url].pop(0)
        if isinstance(item, Exception):
            raise item
        return _response(method, url, **item)


def _client(script: _Script) -> ClerkHouseVotes:
    return ClerkHouseVotes(send=script, pace_seconds=0, sleep=lambda _s: None, today=lambda: date(2026, 9, 20))


def _page(year: int, numbers: list[int], links: str = "") -> dict:
    rows = "".join(
        f'<TR><TD><A HREF="http://clerk.house.gov/cgi-bin/vote.asp?year={year}&rollnumber={n}">{n}</A></TD></TR>'
        for n in numbers
    )
    return {"text": f"<HTML><TABLE>{rows}</TABLE>{links}</HTML>"}


def test_roll_urls_pad_to_three_digits_and_grow_past_a_thousand() -> None:
    assert roll_url(2024, 28) == "https://clerk.house.gov/evs/2024/roll028.xml"
    assert roll_url(2007, 1186) == "https://clerk.house.gov/evs/2007/roll1186.xml"


def test_roll_numbers_are_the_union_of_the_index_and_its_listing_pages() -> None:
    base = "https://clerk.house.gov/evs/2005"
    links = '<A HREF="ROLL_100.asp">100</A><A HREF="ROLL_000.asp">0</A><A HREF="ROLL_100.asp">again</A>'
    script = _Script(
        {
            f"{base}/index.asp": [_page(2005, [101, 102], links)],
            f"{base}/ROLL_100.asp": [_page(2005, [100, 101, 102])],
            f"{base}/ROLL_000.asp": [_page(2005, [1, 2, 99])],
        }
    )
    assert _client(script).roll_numbers(2005) == [1, 2, 99, 100, 101, 102]
    assert len(script.calls) == 3  # the repeated link is fetched once


def test_links_to_another_year_are_ignored() -> None:
    mixed = _page(2005, [5])["text"] + _page(2004, [9])["text"]
    script = _Script({"https://clerk.house.gov/evs/2005/index.asp": [{"text": mixed}]})
    assert _client(script).roll_numbers(2005) == [5]


def test_an_empty_listing_fails_closed() -> None:
    script = _Script({"https://clerk.house.gov/evs/2005/index.asp": [{"text": "<HTML>maintenance</HTML>"}]})
    with pytest.raises(ClerkError, match="no roll numbers"):
        _client(script).roll_numbers(2005)


def test_the_current_year_with_no_rolls_yet_is_not_an_error_but_a_past_year_is() -> None:
    empty = {"text": "<HTML>no votes yet</HTML>"}
    current = _Script({"https://clerk.house.gov/evs/2026/index.asp": [empty]})
    assert _client(current).roll_numbers(2026) == []
    future_404 = _Script({"https://clerk.house.gov/evs/2027/index.asp": [{"status": 404}]})
    assert _client(future_404).roll_numbers(2027) == []
    with pytest.raises(ClerkError, match="no roll numbers"):
        _client(_Script({"https://clerk.house.gov/evs/2025/index.asp": [empty]})).roll_numbers(2025)
    with pytest.raises(ClerkNotFound):  # a past year's missing index is a failure
        _client(_Script({"https://clerk.house.gov/evs/2025/index.asp": [{"status": 404}]})).roll_numbers(2025)


def test_roll_info_reads_size_and_last_modified_from_head() -> None:
    url = roll_url(2005, 100)
    script = _Script(
        {url: [{"headers": {"content-length": "83234", "last-modified": MODIFIED, "content-type": "text/xml"}}]}
    )
    remote = _client(script).roll_info(2005, 100)
    assert (remote.size, remote.last_modified, remote.url) == (83234, MODIFIED, url)
    assert script.calls == [("HEAD", url)]


@pytest.mark.parametrize(
    "headers",
    [
        {"content-type": "text/xml"},  # no length: unknown size fails closed
        {"content-length": "0", "last-modified": MODIFIED, "content-type": "text/xml"},
        {"content-length": "10", "content-type": "text/xml"},  # no Last-Modified: a refresh could not be detected
        {"content-length": "10", "last-modified": MODIFIED, "content-type": "text/html"},  # a soft error page
    ],
)
def test_unusable_head_answers_fail_closed(headers: dict[str, str]) -> None:
    url = roll_url(2005, 100)
    with pytest.raises(ClerkError):
        _client(_Script({url: [{"headers": headers}]})).roll_info(2005, 100)


def test_a_404_means_the_clerk_does_not_publish_it() -> None:
    url = roll_url(2005, 700)
    with pytest.raises(ClerkNotFound):
        _client(_Script({url: [{"status": 404}]})).roll_info(2005, 700)


def test_a_server_error_is_retried_once_then_reported() -> None:
    url = roll_url(2005, 100)
    ok = {"headers": {"content-length": "5", "last-modified": MODIFIED, "content-type": "text/xml"}}
    script = _Script({url: [{"status": 503}, ok]})
    assert _client(script).roll_info(2005, 100).size == 5
    assert len(script.calls) == 2
    with pytest.raises(ClerkError):
        _client(_Script({url: [{"status": 503}, {"status": 503}]})).roll_info(2005, 100)


def test_a_head_asks_for_the_identity_encoding_because_gzip_makes_the_clerk_report_20_bytes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from opendiscourse_research.providers import clerk

    seen: list[tuple[str, dict[str, str]]] = []

    def fake(method: str, url: str, *, headers: dict[str, str], **kwargs) -> httpx.Response:
        seen.append((method, headers))
        return _response(method, url, headers={"content-length": "82538", "last-modified": MODIFIED, "content-type": "text/xml"})

    monkeypatch.setattr(clerk.httpx, "request", fake)
    ClerkHouseVotes(pace_seconds=0, sleep=lambda _s: None).roll_info(2024, 28)
    assert seen[0][0] == "HEAD" and seen[0][1]["Accept-Encoding"] == "identity"
    clerk._default_send("GET", "https://clerk.house.gov/evs/2024/index.asp")
    assert "Accept-Encoding" not in seen[1][1]
