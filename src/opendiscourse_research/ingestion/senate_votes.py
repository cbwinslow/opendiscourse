"""Connector for Senate roll-call votes from senate.gov's official XML: download -> inventory -> ingest (Story 11.2).

The stages, the ledger and the resume rule live in :class:`roll_call_votes.RollCallVotesConnector`;
this module says what is Senate. Each Congress session's vote menu lists its roll numbers (and is
kept as a cross-check: a file whose number, tally or date disagrees with the menu is reported and
the run is ``partial``); one request per file gives its origin state; a senator joins on the LIS
member id the file states (never on a printed name); and a roll call OpenStates already created
under ``us-<year>-upper-<number>`` is enriched in place. After the load, roll calls whose document
names a bill that ``core.bill`` holds are linked to it by Congress, type and number.
"""

from __future__ import annotations

import re
import time
from collections.abc import Callable, Sequence
from datetime import date
from typing import Any

from ..coverage import FIRST_CONGRESS, LAST_CONGRESS
from ..providers.remote_roll import RemoteRoll
from ..providers.senate import PACE_SECONDS, SenateRemoteRoll, SenateVotes
from ..repositories.votes import (
    SENATE_OCD_ORGANIZATION,
    link_senate_bills,
    lis_people,
    save_senate_roll_call,
    senate_organization_id,
)
from .bulk import download
from .roll_call_votes import (
    BATCH_SIZE,
    Downloader,
    RollCallVotesConnector,
    RollFile,
    congress_years,
)
from .senate_vote_parse import SenateVote, parse_senate_vote

SOURCE_ID = "congress.senate_votes"

__all__ = [
    "FIRST_CONGRESS",
    "LAST_CONGRESS",
    "SOURCE_ID",
    "SenateVotesConnector",
    "artifact_key",
    "congress_years",
    "session_of",
]

_MENU_DATE = re.compile(r"^(\d{1,2})-([A-Za-z]{3})$")
_MONTHS = ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec")


def artifact_key(year: int, number: int) -> str:
    """Registry key of one Senate roll-call file."""
    return f"senate-roll-{year}-{number:03d}.xml"


def session_of(congress: int, year: int) -> int:
    """The session (1 or 2) a calendar year is in within a Congress."""
    return congress_years(congress).index(year) + 1


def _menu_date(text: str) -> tuple[int, int] | None:
    """The menu's ``21-Dec`` as (month, day); None when it is not that form."""
    match = _MENU_DATE.match(text.strip())
    if match is None or match[2].lower() not in _MONTHS:
        return None
    return _MONTHS.index(match[2].lower()) + 1, int(match[1])


class SenateVotesConnector(RollCallVotesConnector):
    """Ten-stage Connector for the Senate. Roll calls load in batched transactions and resume by record row."""

    source_id = SOURCE_ID
    chamber = "senate"
    chamber_name = "Senate"
    origin = "senate.gov"
    key_prefix = "senate-roll"
    unresolved_result_key = "unresolved_lis_member_ids"
    without_id_result_key = "entries_without_lis_member_id"

    def __init__(
        self,
        congresses: Sequence[int] | None = None,
        *,
        senate: SenateVotes | None = None,
        downloader: Downloader = download,
        batch_size: int = BATCH_SIZE,
        download_only: bool = False,
        report: Callable[[str], None] | None = None,
        sleep: Callable[[float], None] = time.sleep,
        download_pace_seconds: float = PACE_SECONDS,
    ) -> None:
        super().__init__(
            congresses,
            remote=senate or SenateVotes(pace_seconds=download_pace_seconds),
            downloader=downloader,
            batch_size=batch_size,
            download_only=download_only,
            report=report,
            sleep=sleep,
            download_pace_seconds=download_pace_seconds,
        )
        self._bills_linked = 0

    def _bounds(self) -> tuple[int, int]:
        return FIRST_CONGRESS, LAST_CONGRESS

    def _list_numbers(self, congress: int, year: int) -> list[int]:
        return self._remote.roll_numbers(congress, session_of(congress, year), year)  # type: ignore[no-any-return]

    def _head(self, congress: int, year: int, number: int) -> RemoteRoll:
        return self._remote.roll_info(congress, session_of(congress, year), year, number)  # type: ignore[no-any-return]

    def _artifact_key(self, year: int, number: int) -> str:
        return artifact_key(year, number)

    def _filename(self, congress: int, year: int, number: int) -> str:
        return f"{year}/vote_{congress}_{session_of(congress, year)}_{number:05d}.xml"

    def _parse(self, data: bytes) -> SenateVote:
        return parse_senate_vote(data)

    def _identity(self, parsed: SenateVote) -> tuple[Any, ...]:
        roll = parsed.roll
        return roll["congress"], roll["session_number"], roll["roll_number"], roll["roll_year"]

    def _expected(self, roll: RollFile) -> tuple[Any, ...]:
        return roll.congress, session_of(roll.congress, roll.remote.year), roll.remote.number, roll.remote.year

    def _describe(self, identity: tuple[Any, ...]) -> str:
        return f"Congress {identity[0]} session {identity[1]} roll {identity[2]} of {identity[3]}"

    def _people(self, conn: Any) -> dict[str, str]:
        return lis_people(conn)

    def _organization(self, conn: Any) -> str | None:
        return senate_organization_id(conn)

    def _organization_missing(self) -> str:
        return (
            f"the Senate organization (ocd identifier {SENATE_OCD_ORGANIZATION}) is not in the "
            "warehouse; new roll calls are loaded without an organization"
        )

    def _save(self, conn: Any, parsed: SenateVote, **kwargs: Any) -> dict[str, Any]:
        return save_senate_roll_call(conn, parsed, **kwargs)

    def _cross_check(self, roll: RollFile, parsed: SenateVote) -> list[str]:
        """Compare the file with the menu line that listed it: number, tally and calendar day.

        A file with no menu line is reported too, never skipped.
        """
        menu = roll.remote.menu if isinstance(roll.remote, SenateRemoteRoll) else None
        if menu is None:
            # Listed roll numbers come from the menu, so a missing line is itself a disagreement.
            return ["the file is listed but the session menu has no line for it, so it cannot be cross-checked"]
        found: list[str] = []
        got = parsed.roll
        if menu.number != got["roll_number"]:
            found.append(f"the menu lists vote {menu.number}, the file says {got['roll_number']}")
        for word, listed, stated in (
            ("yeas", menu.yeas, got["yea_total"]),
            ("nays", menu.nays, got["nay_total"]),
        ):
            if listed is not None and listed != stated:
                found.append(f"the menu lists {listed} {word}, the file says {stated}")
        listed_day = _menu_date(menu.date)
        stated_day: date = got["action_date"]
        if listed_day is not None and listed_day != (stated_day.month, stated_day.day):
            found.append(f"the menu dates it {menu.date}, the file {stated_day.isoformat()}")
        return found

    def _finish(self, conn: Any, congresses: Sequence[int]) -> None:
        self._bills_linked = link_senate_bills(conn, list(congresses))

    def _extra_result(self) -> dict[str, Any]:
        return {
            "linked_to_bills_at_end": self._bills_linked,
            "disagreements_with_menu": self._listing_disagreements,
        }
