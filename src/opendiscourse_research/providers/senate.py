"""Senate roll-call client: HTTP only (Story 11.2).

Read-only, unauthenticated lookups against ``senate.gov/legislative/LIS``:

- the vote menu of one Congress session (``vote_menu_<congress>_<session>.xml``): every roll call
  with its number, date, issue, question, result, tally and title. It lists what exists, and its
  tally is checked against the downloaded file;
- the size and ``Last-Modified`` of one roll-call XML file, which is how a refreshed file is
  detected without downloading it.

Three quirks of the origin shape this client (found live 2026-09-20). A HEAD asking for the identity
encoding carries no ``Content-Length``, and one that allows gzip reports the length of the gzip
stream, so the size is read from the headers of a GET whose body is not read. The larger files (about
13 of 1,600 in the 118th and 119th Congresses, 60 KB and up) are served chunked with no
``Content-Length`` at all; for those the body is read once and its length is the size. And a file that
is not published redirects (301 or 302) to an HTML "not available" page with status 200 at the end,
so redirects are not followed. A redirect to one of those two known pages means "not published";
a redirect anywhere else (maintenance, a bot challenge) is an error, never "no such file".

The XML itself is downloaded by the Connector through ``ingestion.bulk.download``. Everything is
paced and retried once on transport errors, 429 and 5xx; anything else raises :class:`SenateError`
so a caller never mistakes a failure for "no data".
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from urllib.parse import urlparse
from xml.etree import ElementTree

import httpx

from .official_counts import SENATE_MENU
from .paced import PacedClient, Send
from .remote_roll import RemoteRoll, RollFileError, RollFileNotFound

USER_AGENT = "opendiscourse-research/0.1 (Senate votes connector; polite, resumable)"
PACE_SECONDS = 0.25
VOTE_URL = (
    "https://www.senate.gov/legislative/LIS/roll_call_votes/vote{congress}{session}/"
    "vote_{congress}_{session}_{number:05d}.xml"
)
_REDIRECTS = {301, 302, 303, 307, 308}
# Where the origin sends a request for a roll call or a menu that does not exist (seen 2026-09-20).
_NOT_AVAILABLE_PATHS = {
    "/legislative/roll-call-vote-not-available.htm",
    "/pagelayout/general/one_item_and_teasers/file_not_found.htm",
}


class SenateError(RollFileError):
    """A Senate lookup failed or returned something unusable."""


class SenateNotFound(SenateError, RollFileNotFound):
    """The Senate does not publish that file (a redirect to its "not available" page, or 404)."""


def _error(message: str, status: int | None) -> SenateError:
    return (SenateNotFound if status in _REDIRECTS or status == 404 else SenateError)(message)


def _only_known_redirects(send: Send) -> Send:
    """Let a redirect through only when it goes to the origin's "not available" page.

    Any other redirect becomes a transport-style error, which the paced client retries once and then
    reports as a :class:`SenateError` (a failed file, a partial run), so a maintenance or challenge
    page can never make listed roll calls look vacated.
    """

    def guarded(method: str, url: str) -> httpx.Response:
        response = send(method, url)
        if response.status_code in _REDIRECTS:
            target = urlparse(response.headers.get("location", ""))
            if target.netloc not in ("", "www.senate.gov") or target.path not in _NOT_AVAILABLE_PATHS:
                raise httpx.TransportError(
                    f"unexpected redirect ({response.status_code}) to {response.headers.get('location', '')!r}"
                )
        return response

    return guarded


@dataclass(frozen=True)
class MenuEntry:
    """One line of a session's vote menu."""

    number: int
    date: str  # "21-Dec": day and month only, the year is the menu's
    issue: str
    question: str
    result: str
    yeas: int | None
    nays: int | None
    title: str


@dataclass(frozen=True)
class SenateMenu:
    """A session's vote menu: the calendar year and every roll call it lists."""

    congress: int
    session: int
    year: int
    entries: dict[int, MenuEntry]


@dataclass(frozen=True)
class SenateRemoteRoll(RemoteRoll):
    """A Senate file's origin state, with the session and the menu line that listed it."""

    session: int = 0
    menu: MenuEntry | None = None


def menu_url(congress: int, session: int) -> str:
    """Where the Senate publishes one session's vote menu."""
    return SENATE_MENU.format(congress=congress, session=session)


def vote_url(congress: int, session: int, number: int) -> str:
    """Where the Senate publishes one roll call (five digits: ``vote_109_1_00100.xml``)."""
    return VOTE_URL.format(congress=congress, session=session, number=number)


def _default_send(method: str, url: str) -> httpx.Response:
    """One request with the project's User-Agent, never following a redirect.

    ``HEAD`` is answered with a GET for the identity encoding whose body is not read (the response
    is closed as soon as the headers are in): that is the only request that reports the file's real
    size. A chunked answer has no length in its headers; its body is then read and the measured length
    is put in ``Content-Length``, so the caller sees the same thing for every file. Everything else is
    a plain GET.
    """
    headers = {"User-Agent": USER_AGENT}
    if method == "HEAD":
        headers["Accept-Encoding"] = "identity"
        with httpx.stream("GET", url, headers=headers, timeout=60, follow_redirects=False) as response:
            if response.is_success and "content-length" not in response.headers:
                response.headers["content-length"] = str(len(response.read()))
            return response
    return httpx.request(method, url, headers=headers, timeout=60, follow_redirects=False)


def _int(text: str | None) -> int | None:
    value = (text or "").strip()
    return int(value) if value.isdigit() else None


def _words(node: ElementTree.Element, tag: str) -> str:
    """A child's text with runs of whitespace (the menu breaks long lines) collapsed."""
    return " ".join((node.findtext(tag) or "").split())


def parse_menu(content: bytes, congress: int, session: int) -> SenateMenu:
    """Read one vote menu; a menu that is not the one asked for, or is unreadable, is an error."""
    try:
        root = ElementTree.fromstring(content)
    except ElementTree.ParseError as exc:
        raise SenateError(f"vote menu {congress}/{session}: unreadable ({exc})") from exc
    got = (_int(root.findtext("congress")), _int(root.findtext("session")))
    year = _int(root.findtext("congress_year"))
    if root.tag != "vote_summary" or got != (congress, session) or year is None:
        raise SenateError(f"vote menu {congress}/{session}: this is not that menu (congress/session {got})")
    entries: dict[int, MenuEntry] = {}
    for node in root.findall("./votes/vote"):
        number = _int(node.findtext("vote_number"))
        if number is None:
            raise SenateError(f"vote menu {congress}/{session}: an entry has no vote_number")
        if number in entries:
            raise SenateError(f"vote menu {congress}/{session}: vote {number} is listed twice")
        entries[number] = MenuEntry(
            number,
            _words(node, "vote_date"),
            _words(node, "issue"),
            _words(node, "question"),
            _words(node, "result"),
            _int(node.findtext("vote_tally/yeas")),
            _int(node.findtext("vote_tally/nays")),
            _words(node, "title"),
        )
    return SenateMenu(congress, session, year, entries)


class SenateVotes:
    """Paced, retrying client for the Senate's vote menus and roll-call files."""

    def __init__(
        self,
        send: Send = _default_send,
        pace_seconds: float = PACE_SECONDS,
        sleep: Callable[[float], None] = time.sleep,
        today: Callable[[], date] = lambda: datetime.now(UTC).date(),
    ) -> None:
        self._client = PacedClient(_only_known_redirects(send), pace_seconds, sleep, _error)
        self._today = today
        self._menus: dict[tuple[int, int], SenateMenu] = {}

    def menu(self, congress: int, session: int, year: int) -> SenateMenu:
        """The vote menu of a session (once per client).

        An empty or missing menu fails closed for a past year (a degraded page must not read as
        "no votes"); the current or a future year may simply have no roll calls yet.
        """
        key = (congress, session)
        if key in self._menus:
            return self._menus[key]
        url = menu_url(congress, session)
        try:
            menu = parse_menu(self._client.request("GET", url).content, congress, session)
        except SenateNotFound:
            if year < self._today().year:
                raise
            menu = SenateMenu(congress, session, year, {})
        if menu.year != year:
            raise SenateError(f"{url}: lists calendar year {menu.year}, expected {year}")
        if not menu.entries and year < self._today().year:
            raise SenateError(f"{url}: no roll calls listed for {year}")
        self._menus[key] = menu
        return menu

    def roll_numbers(self, congress: int, session: int, year: int) -> list[int]:
        """Every roll number the session's menu lists, ascending."""
        return sorted(self.menu(congress, session, year).entries)

    def roll_info(self, congress: int, session: int, year: int, number: int) -> SenateRemoteRoll:
        """Size and ``Last-Modified`` of one file. Unknown size fails closed."""
        url = vote_url(congress, session, number)
        headers = self._client.request("HEAD", url).headers
        length, modified = headers.get("content-length", ""), headers.get("last-modified")
        kind = headers.get("content-type", "")
        if not length.isdigit() or int(length) == 0 or not modified:
            raise SenateError(
                f"{url}: the server gave no usable size or Last-Modified "
                f"(content-length={length!r}, last-modified={modified!r})"
            )
        if "xml" not in kind.lower():
            raise SenateError(f"{url}: expected XML, the server sent {kind!r}")
        menu = self._menus.get((congress, session))
        return SenateRemoteRoll(
            year, number, url, int(length), modified, session, menu.entries.get(number) if menu else None
        )
