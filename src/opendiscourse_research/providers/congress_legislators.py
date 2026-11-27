"""HTTP-only client for ``unitedstates/congress-legislators``.

A run first pins the commit the publisher's branch points at, then reads every
file from that commit's permalink, so the recorded URL always describes the
bytes that are kept. ``Accept-Encoding: identity`` is sent so the size check
matches those bytes (GitHub reports the compressed length otherwise).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime

import httpx

USER_AGENT = "opendiscourse-research/0.1"
RAW = "https://raw.githubusercontent.com/unitedstates/congress-legislators"
API = "https://api.github.com/repos/unitedstates/congress-legislators/commits"
_SHA = re.compile(r"^[0-9a-f]{40}$")


@dataclass(frozen=True)
class Commit:
    """One upstream commit and the UTC calendar day it was committed."""

    sha: str
    day: str


class CongressLegislatorsClient:
    """Resolve a commit, then HEAD and GET files at that commit."""

    def __init__(self, *, raw: str = RAW, api: str = API, http: httpx.Client | None = None) -> None:
        self._raw = raw.rstrip("/")
        self._api = api.rstrip("/")
        self._http = http
        self._owns = http is None

    def close(self) -> None:
        """Close the client this object opened. A caller-supplied client stays open."""
        if self._owns and self._http is not None:
            self._http.close()
            self._http = None

    def _client(self) -> httpx.Client:
        if self._http is None:
            self._http = httpx.Client(timeout=45, follow_redirects=True)
        return self._http

    def _request(self, method: str, url: str, what: str) -> httpx.Response:
        try:
            response = self._client().request(
                method, url, headers={"User-Agent": USER_AGENT, "Accept-Encoding": "identity"}
            )
        except httpx.HTTPError as exc:
            raise RuntimeError(f"{what}: {exc.__class__.__name__}") from None
        if response.status_code != 200:
            raise RuntimeError(f"{what}: HTTP {response.status_code}")
        return response

    def resolve_commit(self, ref: str = "main") -> Commit:
        """The commit ``ref`` points at now. An answer that cannot be pinned is refused."""
        what = "could not read the latest commit of congress-legislators"
        response = self._request("GET", f"{self._api}/{ref}", what)
        try:
            body = response.json()
            sha = body["sha"]
            committed = datetime.fromisoformat(body["commit"]["committer"]["date"])
        except (ValueError, KeyError, TypeError):
            raise RuntimeError(f"{what}: unexpected answer") from None
        if not isinstance(sha, str) or not _SHA.match(sha) or committed.tzinfo is None:
            raise RuntimeError(f"{what}: unexpected answer")
        return Commit(sha, committed.astimezone(UTC).date().isoformat())

    def file_url(self, sha: str, name: str) -> str:
        """Permalink of one file at one commit."""
        return f"{self._raw}/{sha}/{name}"

    def size(self, url: str, name: str) -> int:
        """Published size in bytes. An unknown size refuses the run before a download."""
        length = self._request("HEAD", url, f"could not download {name}").headers.get(
            "content-length"
        )
        if length is None or not length.isdigit() or int(length) == 0:
            raise RuntimeError(f"capacity gate: size unavailable for {name}")
        return int(length)

    def download(self, url: str, name: str, expected: int) -> bytes:
        """The file body. A length other than the published size is refused."""
        body = self._request("GET", url, f"could not download {name}").content
        if len(body) != expected:
            raise RuntimeError(
                f"{name}: downloaded {len(body)} bytes but the origin reports {expected}"
            )
        return body
