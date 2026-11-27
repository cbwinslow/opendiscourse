"""HTTP client for congress-legislators: pin one commit, check sizes, download (no network)."""

from __future__ import annotations

import httpx
import pytest

from opendiscourse_research.providers.congress_legislators import CongressLegislatorsClient

SHA = "a" * 40
NAME = "legislators-current.yaml"


def _client(handler) -> CongressLegislatorsClient:
    return CongressLegislatorsClient(
        raw="https://raw.test/repo",
        api="https://api.test/commits",
        http=httpx.Client(transport=httpx.MockTransport(handler)),
    )


def _commit(sha: object = SHA, date: object = "2026-09-03T23:30:00Z"):
    return lambda request: httpx.Response(
        200, json={"sha": sha, "commit": {"committer": {"date": date}}}
    )


def test_resolve_commit_returns_the_sha_and_the_utc_commit_day() -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return _commit()(request)

    pin = _client(handler).resolve_commit()

    assert (pin.sha, pin.day) == (SHA, "2026-09-03")
    assert seen == ["https://api.test/commits/main"]


@pytest.mark.parametrize(
    "handler",
    [
        _commit(sha="main"),
        _commit(date="yesterday"),
        lambda request: httpx.Response(200, json=[]),
        lambda request: httpx.Response(200, content=b"<html>"),
    ],
)
def test_resolve_commit_refuses_an_answer_it_cannot_pin(handler) -> None:
    with pytest.raises(RuntimeError, match="latest commit"):
        _client(handler).resolve_commit()


def test_resolve_commit_names_the_http_status() -> None:
    with pytest.raises(RuntimeError, match="HTTP 403"):
        _client(lambda request: httpx.Response(403)).resolve_commit()


def test_file_url_is_a_permalink_at_the_commit() -> None:
    client = _client(_commit())
    assert client.file_url(SHA, NAME) == f"https://raw.test/repo/{SHA}/{NAME}"


def test_size_and_download_ask_for_uncompressed_bytes() -> None:
    encodings: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        encodings.append(request.headers["accept-encoding"])
        if request.method == "HEAD":
            return httpx.Response(200, headers={"content-length": "3"})
        return httpx.Response(200, content=b"abc")

    client = _client(handler)
    url = client.file_url(SHA, NAME)
    assert client.size(url, NAME) == 3
    assert client.download(url, NAME, 3) == b"abc"
    assert encodings == ["identity", "identity"]


@pytest.mark.parametrize("headers", [{}, {"content-length": "0"}, {"content-length": "x"}])
def test_unknown_size_fails_closed(headers) -> None:
    client = _client(lambda request: httpx.Response(200, headers=headers))
    with pytest.raises(RuntimeError, match="capacity gate"):
        client.size(client.file_url(SHA, NAME), NAME)


def test_a_short_download_is_refused() -> None:
    client = _client(lambda request: httpx.Response(200, content=b"ab"))
    with pytest.raises(RuntimeError, match="downloaded 2 bytes"):
        client.download(client.file_url(SHA, NAME), NAME, 3)


@pytest.mark.parametrize("call", ["size", "download"])
def test_a_missing_file_or_dropped_connection_names_the_file(call: str) -> None:
    def refused(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    for handler in (lambda request: httpx.Response(404), refused):
        client = _client(handler)
        url = client.file_url(SHA, NAME)
        with pytest.raises(RuntimeError, match=f"could not download {NAME}"):
            client.size(url, NAME) if call == "size" else client.download(url, NAME, 3)
