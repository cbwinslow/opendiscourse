"""House Clerk roll-call client: HTTP only (Story 11.1).

Read-only, unauthenticated lookups against ``clerk.house.gov/evs``:

- the roll numbers the Clerk lists for a calendar year (``index.asp`` shows the latest few and links
  to ``ROLL_000.asp``, ``ROLL_100.asp`` ... which list the rest);
- one HEAD per roll-call XML file (its size and ``Last-Modified``, which is how a refreshed file is
  detected without downloading it).

The XML itself is downloaded by the Connector through ``ingestion.bulk.download``, so it lands in
``DATA_ROOT`` as a retained artifact. Everything is paced and retried once on transport errors, 429
and 5xx; anything else raises :class:`ClerkError` so a caller never mistakes a failure for "no data".
A 404 raises :class:`ClerkNotFound`: the Clerk does not publish that file.
"""

from __future__ import annotations

import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime

import httpx

from .official_counts import HOUSE_INDEX
from .paced import PacedClient, Send

USER_AGENT = "opendiscourse-research/0.1 (House votes connector; polite, resumable)"
PACE_SECONDS = 0.25
EVS_ROOT = "https://clerk.house.gov/evs"
LIST_URL = EVS_ROOT + "/{year}/{page}"
ROLL_URL = EVS_ROOT + "/{year}/roll{number:03d}.xml"
_LIST_PAGE = re.compile(r'href="(ROLL_\d+\.asp)"', re.IGNORECASE)
_ROLL_LINK = re.compile(r"year=(\d{4})&(?:amp;)?rollnumber=(\d+)", re.IGNORECASE)


class ClerkError(RuntimeError):
    """A Clerk lookup failed or returned something unusable."""


class ClerkNotFound(ClerkError):
    """The Clerk answered 404: that file is not published."""


def _error(message: str, status: int | None) -> ClerkError:
    return (ClerkNotFound if status == 404 else ClerkError)(message)


@dataclass(frozen=True)
class RemoteRoll:
    """What the Clerk says about one roll-call file, without downloading it."""

    year: int
    number: int
    url: str
    size: int
    last_modified: str


def roll_url(year: int, number: int) -> str:
    """Where the Clerk publishes one roll call (three digits at least: ``roll028.xml``)."""
    return ROLL_URL.format(year=year, number=number)


def _default_send(method: str, url: str) -> httpx.Response:
    """One request with the project's User-Agent.

    A HEAD must say ``Accept-Encoding: identity``: with gzip accepted, the Clerk answers HEAD with the
    length of an empty gzip stream (20 bytes) and no way to learn the file's size (found live 2026-09-20).
    """
    headers = {"User-Agent": USER_AGENT}
    if method == "HEAD":
        headers["Accept-Encoding"] = "identity"
    return httpx.request(method, url, headers=headers, timeout=60, follow_redirects=True)


class ClerkHouseVotes:
    """Paced, retrying client for the House Clerk's roll-call listing and files."""

    def __init__(
        self,
        send: Send = _default_send,
        pace_seconds: float = PACE_SECONDS,
        sleep: Callable[[float], None] = time.sleep,
        today: Callable[[], date] = lambda: datetime.now(UTC).date(),
    ) -> None:
        self._client = PacedClient(send, pace_seconds, sleep, _error)
        self._today = today

    def roll_numbers(self, year: int) -> list[int]:
        """Every roll number the Clerk lists for ``year``, ascending.

        An empty listing fails closed for a past year (a degraded page must not read as "no votes");
        the current or a future year may simply have no roll calls yet, and returns ``[]``.
        """
        index_url = HOUSE_INDEX.format(year=year)
        try:
            page_text = self._client.request("GET", index_url).text
        except ClerkNotFound:
            if year < self._today().year:
                raise
            return []  # a year that has not begun has no index yet
        found = self._numbers(page_text, year)
        for page in dict.fromkeys(_LIST_PAGE.findall(page_text)):
            found |= self._numbers(self._client.request("GET", LIST_URL.format(year=year, page=page)).text, year)
        if not found and year < self._today().year:
            raise ClerkError(f"{index_url}: no roll numbers listed for {year}")
        return sorted(found)

    @staticmethod
    def _numbers(text: str, year: int) -> set[int]:
        return {int(n) for y, n in _ROLL_LINK.findall(text) if int(y) == year}

    def roll_info(self, year: int, number: int) -> RemoteRoll:
        """Size and ``Last-Modified`` of one file. Unknown size fails closed."""
        url = roll_url(year, number)
        headers = self._client.request("HEAD", url).headers
        length, modified = headers.get("content-length", ""), headers.get("last-modified")
        kind = headers.get("content-type", "")
        if not length.isdigit() or int(length) == 0 or not modified:
            raise ClerkError(
                f"{url}: the server gave no usable size or Last-Modified "
                f"(content-length={length!r}, last-modified={modified!r})"
            )
        if "xml" not in kind.lower():
            raise ClerkError(f"{url}: expected XML, the server sent {kind!r}")
        return RemoteRoll(year, number, url, int(length), modified)
