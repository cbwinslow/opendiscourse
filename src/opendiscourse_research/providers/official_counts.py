"""Official expected-count lookups for the Congress coverage comparator.

Three public sources, all read-only and unauthenticated: GovInfo BILLSTATUS
directory manifests (bills per Congress and type), Senate.gov roll-call vote
menus (votes per Congress and session), and the House Clerk roll-call index
(highest roll number per calendar year). Every lookup raises
:class:`OfficialCountError` on any failure so callers can report ``unknown``
instead of a misleading zero.
"""

from __future__ import annotations

import re
import time
from collections.abc import Callable
from xml.etree import ElementTree

import httpx

from .paced import PacedClient

USER_AGENT = "opendiscourse-research/0.1 (coverage comparator; read-only)"
PACE_SECONDS = 1.0
GOVINFO_ROOT = "https://www.govinfo.gov/bulkdata/json/BILLSTATUS"
GOVINFO_MANIFEST = "https://www.govinfo.gov/bulkdata/json/BILLSTATUS/{congress}/{bill_type}"
SENATE_MENU = "https://www.senate.gov/legislative/LIS/roll_call_lists/vote_menu_{congress}_{session}.xml"
HOUSE_INDEX = "https://clerk.house.gov/evs/{year}/index.asp"
_ROLL_NUMBER = re.compile(r"rollnumber=(\d+)", re.IGNORECASE)


class OfficialCountError(RuntimeError):
    """An official count could not be fetched or parsed."""


Get = Callable[[str], httpx.Response]


def _default_get(url: str) -> httpx.Response:
    """Fetch one URL with the project's User-Agent; GovInfo needs an Accept for JSON."""
    headers = {"User-Agent": USER_AGENT}
    if "govinfo.gov/bulkdata/json" in url:
        headers["Accept"] = "application/json"
    return httpx.get(url, headers=headers, timeout=60, follow_redirects=True)


class OfficialCounts:
    """Paced, retrying client for the official count sources."""

    def __init__(
        self,
        get: Get = _default_get,
        pace_seconds: float = PACE_SECONDS,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._client = PacedClient(
            lambda _method, url: get(url),
            pace_seconds,
            sleep,
            lambda message, _status: OfficialCountError(message),
        )

    def _fetch(self, url: str) -> httpx.Response:
        """GET with pacing; retry once on transport errors, 429 and 5xx only."""
        return self._client.request("GET", url)

    def first_billstatus_congress(self) -> int:
        """Return the earliest Congress folder in GovInfo's BILLSTATUS root manifest."""
        url = GOVINFO_ROOT
        try:
            names = [
                int(item["name"])
                for item in self._fetch(url).json()["files"]
                if item.get("folder") and str(item.get("name", "")).isdigit()
            ]
        except (ValueError, KeyError, TypeError, AttributeError) as exc:
            raise OfficialCountError(f"{url}: unreadable manifest ({exc})") from exc
        if not names:
            raise OfficialCountError(f"{url}: no Congress folders listed")
        return min(names)

    def billstatus(self, congress: int, bill_type: str) -> int:
        """Return the number of BILLSTATUS XML files GovInfo lists for one type."""
        url = GOVINFO_MANIFEST.format(congress=congress, bill_type=bill_type)
        try:
            files = self._fetch(url).json()["files"]
            count = sum(1 for item in files if item.get("name", "").endswith(".xml"))
        except (ValueError, KeyError, TypeError, AttributeError) as exc:
            raise OfficialCountError(f"{url}: unreadable manifest ({exc})") from exc
        if count == 0:  # a degraded 200 must never become an authoritative zero
            raise OfficialCountError(f"{url}: manifest lists no XML files")
        return count

    def senate_votes(self, congress: int, session: int) -> int:
        """Return the number of roll-call votes in one Senate session's vote menu."""
        url = SENATE_MENU.format(congress=congress, session=session)
        try:
            root = ElementTree.fromstring(self._fetch(url).content)
        except ElementTree.ParseError as exc:
            raise OfficialCountError(f"{url}: unreadable vote menu ({exc})") from exc
        count = len(root.findall("./votes/vote"))
        if count == 0:
            raise OfficialCountError(f"{url}: vote menu lists no votes")
        return count

    def house_rolls(self, year: int) -> int:
        """Return the highest House roll-call number listed for a calendar year."""
        url = HOUSE_INDEX.format(year=year)
        numbers = [int(n) for n in _ROLL_NUMBER.findall(self._fetch(url).text)]
        if not numbers:
            raise OfficialCountError(f"{url}: no roll numbers found")
        return max(numbers)
