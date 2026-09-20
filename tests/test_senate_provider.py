"""Story 11.2: the Senate client. No network; responses are faked."""

from __future__ import annotations

import contextlib
from datetime import date

import httpx
import pytest

from opendiscourse_research.providers.remote_roll import RollFileError, RollFileNotFound
from opendiscourse_research.providers.senate import (
    SenateError,
    SenateNotFound,
    SenateVotes,
    _default_send,
    menu_url,
    parse_menu,
    vote_url,
)

MODIFIED = "Tue, 25 Aug 2026 17:12:12 GMT"
FILE_GONE = "https://www.senate.gov/legislative/roll-call-vote-not-available.htm"
MENU_GONE = "https://www.senate.gov/pagelayout/general/one_item_and_teasers/file_not_found.htm"


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


def _client(script: _Script) -> SenateVotes:
    return SenateVotes(send=script, pace_seconds=0, sleep=lambda _s: None, today=lambda: date(2026, 9, 20))


def _menu_xml(congress: int = 109, session: int = 1, year: int = 2005, numbers: tuple[int, ...] = (2, 1)) -> bytes:
    votes = "".join(
        f"<vote><vote_number>{n:05d}</vote_number><vote_date>21-Dec</vote_date><issue>H.R. 2863</issue>"
        f"<question>On the\n  Conference Report</question><result>Agreed to</result>"
        f"<vote_tally><yeas>93</yeas><nays>0</nays></vote_tally><title>Title {n}</title></vote>"
        for n in numbers
    )
    return (
        f"<vote_summary><congress>{congress}</congress><session>{session}</session>"
        f"<congress_year>{year}</congress_year><votes>{votes}</votes></vote_summary>"
    ).encode()


def _headers(size: str | None = "23648", modified: str | None = MODIFIED, kind: str = "text/xml") -> dict:
    headers = {"content-type": kind}
    if size is not None:
        headers["content-length"] = size
    if modified is not None:
        headers["last-modified"] = modified
    return {"headers": headers}


def test_urls_are_the_ones_the_senate_publishes() -> None:
    assert menu_url(109, 1) == "https://www.senate.gov/legislative/LIS/roll_call_lists/vote_menu_109_1.xml"
    assert vote_url(109, 1, 100) == "https://www.senate.gov/legislative/LIS/roll_call_votes/vote1091/vote_109_1_00100.xml"
    assert vote_url(119, 2, 12345).endswith("vote1192/vote_119_2_12345.xml")


def test_the_menu_lists_roll_numbers_ascending_and_keeps_each_line() -> None:
    script = _Script({menu_url(109, 1): [{"content": _menu_xml()}]})
    client = _client(script)

    assert client.roll_numbers(109, 1, 2005) == [1, 2]
    entry = client.menu(109, 1, 2005).entries[2]
    assert (entry.number, entry.date, entry.issue, entry.result, entry.yeas, entry.nays, entry.title) == (
        2, "21-Dec", "H.R. 2863", "Agreed to", 93, 0, "Title 2",
    )
    assert entry.question == "On the Conference Report"  # the menu's line breaks are collapsed
    assert script.calls == [("GET", menu_url(109, 1))]  # one fetch per session, however often asked
    client.menu(109, 1, 2005)
    assert len(script.calls) == 1


def test_a_menu_that_is_not_the_one_asked_for_is_an_error() -> None:
    script = _Script({menu_url(109, 1): [{"content": _menu_xml(congress=110)}]})
    with pytest.raises(SenateError, match="not that menu"):
        _client(script).menu(109, 1, 2005)
    with pytest.raises(SenateError, match="unreadable"):
        parse_menu(b"<vote_summary", 109, 1)
    with pytest.raises(SenateError, match="listed twice"):
        parse_menu(_menu_xml(numbers=(1, 1)), 109, 1)
    with pytest.raises(SenateError, match="calendar year"):
        _client(_Script({menu_url(109, 1): [{"content": _menu_xml(year=2006)}]})).menu(109, 1, 2005)


def test_an_empty_menu_fails_closed_for_a_past_year_and_is_empty_for_the_current_one() -> None:
    empty = _menu_xml(numbers=())
    with pytest.raises(SenateError, match="no roll calls listed"):
        _client(_Script({menu_url(109, 1): [{"content": empty}]})).roll_numbers(109, 1, 2005)
    assert _client(_Script({menu_url(119, 2): [{"content": _menu_xml(119, 2, 2026, ())}]})).roll_numbers(119, 2, 2026) == []


def test_a_menu_that_redirects_is_not_published_a_past_year_fails_and_a_new_year_is_empty() -> None:
    old = _client(_Script({menu_url(109, 1): [{"status": 302, "headers": {"location": MENU_GONE}}]}))
    with pytest.raises(SenateNotFound):
        old.roll_numbers(109, 1, 2005)
    new = _client(_Script({menu_url(120, 1): [{"status": 302, "headers": {"location": MENU_GONE}}]}))
    assert new.roll_numbers(120, 1, 2027) == []


def test_roll_info_reads_size_last_modified_and_the_menu_line() -> None:
    script = _Script(
        {menu_url(109, 1): [{"content": _menu_xml()}], vote_url(109, 1, 2): [{**_headers()}]}
    )
    client = _client(script)
    client.menu(109, 1, 2005)

    remote = client.roll_info(109, 1, 2005, 2)

    assert (remote.year, remote.number, remote.url, remote.size, remote.last_modified) == (
        2005, 2, vote_url(109, 1, 2), 23648, MODIFIED,
    )
    assert remote.session == 1 and remote.menu is not None and remote.menu.number == 2
    assert script.calls[-1][0] == "HEAD"


@pytest.mark.parametrize(
    "reply",
    [_headers(size=None), _headers(size="0"), _headers(size="abc"), _headers(modified=None), _headers(kind="text/html")],
    ids=["no-size", "zero-size", "bad-size", "no-last-modified", "not-xml"],
)
def test_roll_info_fails_closed_without_a_usable_size_or_last_modified_or_xml(reply: dict) -> None:
    client = _client(_Script({vote_url(109, 1, 2): [reply]}))
    with pytest.raises(SenateError, match="usable size|expected XML"):
        client.roll_info(109, 1, 2005, 2)


def test_a_redirect_or_404_means_not_published_and_other_failures_are_errors() -> None:
    for status, location in ((301, FILE_GONE), (302, "/legislative/roll-call-vote-not-available.htm"), (404, "")):
        client = _client(_Script({vote_url(109, 1, 2): [{"status": status, "headers": {"location": location}}]}))
        with pytest.raises(RollFileNotFound):
            client.roll_info(109, 1, 2005, 2)
    client = _client(_Script({vote_url(109, 1, 2): [{"status": 403}]}))
    with pytest.raises(SenateError) as caught:
        client.roll_info(109, 1, 2005, 2)
    assert not isinstance(caught.value, RollFileNotFound) and isinstance(caught.value, RollFileError)


def test_a_transient_failure_is_retried_once_then_reported() -> None:
    ok = _headers()
    client = _client(_Script({vote_url(109, 1, 2): [{"status": 503}, ok]}))
    assert client.roll_info(109, 1, 2005, 2).size == 23648
    client = _client(_Script({vote_url(109, 1, 2): [httpx.ConnectError("reset"), httpx.ConnectError("reset")]}))
    with pytest.raises(SenateError):
        client.roll_info(109, 1, 2005, 2)


def test_the_real_head_reads_headers_of_an_identity_get_and_never_follows_a_redirect(monkeypatch) -> None:
    """The origin gives no size on HEAD: the client asks with a GET, identity encoding, and reads no body."""
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.url.path.endswith("gone.xml"):
            return httpx.Response(301, headers={"location": "https://x/na.htm"})
        if request.url.path.endswith("chunked.xml"):
            return httpx.Response(
                200, content=iter([b"<a>", b"12", b"</a>"]), headers={"content-type": "text/xml", "last-modified": MODIFIED}
            )
        return httpx.Response(200, content=b"<a/>" * 100, headers={"content-type": "text/xml", "last-modified": MODIFIED})

    transport = httpx.MockTransport(handler)
    real_stream = httpx.stream

    @contextlib.contextmanager
    def stream(method, url, **kwargs):
        with httpx.Client(transport=transport) as client, client.stream(method, url, **kwargs) as response:
            yield response

    monkeypatch.setattr(httpx, "stream", stream)
    response = _default_send("HEAD", "https://www.senate.gov/x/vote_1_1_00001.xml")
    assert response.headers["last-modified"] == MODIFIED
    assert seen[0].method == "GET" and seen[0].headers["accept-encoding"] == "identity"
    assert "opendiscourse" in seen[0].headers["user-agent"]

    chunked = _default_send("HEAD", "https://www.senate.gov/x/chunked.xml")  # no Content-Length: the body is measured
    assert chunked.headers["content-length"] == "9" and "transfer-encoding" in chunked.headers

    gone = _default_send("HEAD", "https://www.senate.gov/x/gone.xml")
    assert gone.status_code == 301  # not followed; PacedClient turns it into "not published"
    monkeypatch.setattr(httpx, "stream", real_stream)


@pytest.mark.parametrize(
    "location",
    ["https://www.senate.gov/maintenance.htm", "https://challenge.example.com/verify", "/legislative/other.htm", ""],
    ids=["maintenance", "other-host", "other-path", "no-location"],
)
def test_a_redirect_anywhere_else_is_an_error_not_a_vacated_roll(location: str) -> None:
    """A maintenance or bot-challenge redirect must never make listed rolls look unpublished."""
    reply = {"status": 302, "headers": {"location": location}}
    script = _Script({vote_url(109, 1, 2): [reply, reply], menu_url(109, 1): [reply, reply]})
    client = _client(script)
    with pytest.raises(SenateError) as caught:
        client.roll_info(109, 1, 2005, 2)
    assert not isinstance(caught.value, RollFileNotFound) and "unexpected redirect" in str(caught.value)
    with pytest.raises(SenateError) as menu:
        client.menu(109, 1, 2005)
    assert not isinstance(menu.value, RollFileNotFound)
