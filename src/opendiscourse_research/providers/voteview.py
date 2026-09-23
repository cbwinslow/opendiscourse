"""HTTP-only client for the three Voteview bulk files.

Reads size and ``Last-Modified`` with HEAD, then downloads the bytes.
``Accept-Encoding: identity`` is sent on every request so the size check
matches the bytes that are kept. The individual-vote file is refused: those
votes are already loaded from the Clerk and Senate.gov.
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx

USER_AGENT = "opendiscourse-research/0.1 (Voteview connector; polite, resumable)"
ORIGIN = "https://voteview.com/static/data/out"
MEMBERS = "HSall_members.csv"
ROLLCALLS = "HSall_rollcalls.json"
PARTIES = "HSall_parties.csv"
VOTES = "HSall_votes.csv"
FILES = (MEMBERS, ROLLCALLS, PARTIES)
_FOLDERS = {MEMBERS: "members", ROLLCALLS: "rollcalls", PARTIES: "parties"}


@dataclass(frozen=True)
class RemoteVoteviewFile:
    """One file as HEAD described it, before any byte is kept."""

    name: str
    url: str
    size: int
    last_modified: str


def file_url(name: str, *, origin: str = ORIGIN) -> str:
    """URL of one allowed file. The individual-vote file is refused before any request."""
    if name == VOTES:
        raise ValueError(
            "refusing to download HSall_votes.csv; it copies individual votes "
            "the Clerk and Senate.gov already supply"
        )
    folder = _FOLDERS.get(name)
    if folder is None:
        raise ValueError(f"unknown Voteview file {name}")
    return f"{origin.rstrip('/')}/{folder}/{name}"


class VoteviewClient:
    """HEAD and GET for the three Voteview files. Nothing else is requested."""

    def __init__(self, *, origin: str = ORIGIN, http: httpx.Client | None = None) -> None:
        self._origin = origin
        self._http = http
        self._owns = http is None

    def close(self) -> None:
        """Close the client this object opened. A caller-supplied client stays open."""
        if self._owns and self._http is not None:
            self._http.close()
            self._http = None

    def _client(self) -> httpx.Client:
        if self._http is None:
            self._http = httpx.Client(timeout=300, follow_redirects=True)
        return self._http

    def _request(self, method: str, name: str) -> httpx.Response:
        url = file_url(name, origin=self._origin)
        try:
            return self._client().request(
                method,
                url,
                headers={"User-Agent": USER_AGENT, "Accept-Encoding": "identity"},
            )
        except httpx.HTTPError as exc:
            raise RuntimeError(f"could not download {name}: {exc.__class__.__name__}") from None

    def describe(self, name: str) -> RemoteVoteviewFile:
        """Size and ``Last-Modified``. Either missing refuses the run before a download."""
        url = file_url(name, origin=self._origin)
        response = self._request("HEAD", name)
        if response.status_code != 200:
            raise RuntimeError(f"could not download {name}: HTTP {response.status_code}")
        length = response.headers.get("content-length")
        modified = response.headers.get("last-modified")
        if length is None or not length.isdigit() or int(length) == 0 or not modified:
            raise RuntimeError(
                f"capacity gate: size or Last-Modified unavailable for {name} "
                f"(content-length={length!r}, last-modified={modified!r})"
            )
        return RemoteVoteviewFile(name, url, int(length), modified)

    def download(self, name: str, expected: int) -> bytes:
        """The file body. A length other than the HEAD size is refused."""
        response = self._request("GET", name)
        if response.status_code != 200:
            raise RuntimeError(f"could not download {name}: HTTP {response.status_code}")
        body = response.content
        if len(body) != expected:
            raise RuntimeError(
                f"{name}: downloaded {len(body)} bytes but the origin reports {expected}"
            )
        return body
