"""Connector for House roll-call votes from the Clerk's official XML: download -> inventory -> ingest (Story 11.1).

The stages, the ledger and the resume rule live in :class:`roll_call_votes.RollCallVotesConnector`;
this module says what is House: the Clerk's yearly index lists the roll numbers, one HEAD per file
gives its origin state, a member joins on the BioGuide ``name-id``, and a roll call OpenStates already
created under ``us-<year>-lower-<number>`` is enriched in place.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Sequence
from typing import Any

from ..coverage import FIRST_CONGRESS, LAST_CONGRESS
from ..providers.clerk import PACE_SECONDS, ClerkHouseVotes
from ..providers.remote_roll import RemoteRoll
from ..repositories.votes import (
    HOUSE_OCD_ORGANIZATION,
    bioguide_people,
    house_organization_id,
    save_house_roll_call,
)
from .bulk import download
from .house_vote_parse import HouseVote, parse_house_vote
from .roll_call_votes import (
    BATCH_SIZE,
    Downloader,
    RollCallVotesConnector,
    RollFile,
    congress_years,
)

SOURCE_ID = "congress.house_votes"
LOCK_KEY = f"{SOURCE_ID}:sync"

__all__ = [
    "FIRST_CONGRESS",
    "LAST_CONGRESS",
    "LOCK_KEY",
    "SOURCE_ID",
    "HouseVotesConnector",
    "artifact_key",
    "congress_years",
]


def artifact_key(year: int, number: int) -> str:
    """Registry key of one House roll-call file."""
    return f"house-roll-{year}-{number:03d}.xml"


class HouseVotesConnector(RollCallVotesConnector):
    """Ten-stage Connector for the House. Roll calls load in batched transactions and resume by record row."""

    source_id = SOURCE_ID
    chamber = "house"
    chamber_name = "House"
    origin = "clerk.house.gov"
    key_prefix = "house-roll"
    unresolved_result_key = "unresolved_bioguide_ids"
    without_id_result_key = "entries_without_bioguide_id"

    def __init__(
        self,
        congresses: Sequence[int] | None = None,
        *,
        clerk: ClerkHouseVotes | None = None,
        downloader: Downloader = download,
        batch_size: int = BATCH_SIZE,
        download_only: bool = False,
        report: Callable[[str], None] | None = None,
        sleep: Callable[[float], None] = time.sleep,
        download_pace_seconds: float = PACE_SECONDS,
    ) -> None:
        super().__init__(
            congresses,
            remote=clerk or ClerkHouseVotes(pace_seconds=download_pace_seconds),
            downloader=downloader,
            batch_size=batch_size,
            download_only=download_only,
            report=report,
            sleep=sleep,
            download_pace_seconds=download_pace_seconds,
        )

    def _bounds(self) -> tuple[int, int]:
        return FIRST_CONGRESS, LAST_CONGRESS

    def _list_numbers(self, congress: int, year: int) -> list[int]:
        return self._remote.roll_numbers(year)  # type: ignore[no-any-return]

    def _head(self, congress: int, year: int, number: int) -> RemoteRoll:
        return self._remote.roll_info(year, number)  # type: ignore[no-any-return]

    def _artifact_key(self, year: int, number: int) -> str:
        return artifact_key(year, number)

    def _filename(self, congress: int, year: int, number: int) -> str:
        return f"{year}/roll{number:03d}.xml"

    def _parse(self, data: bytes) -> HouseVote:
        return parse_house_vote(data)

    def _identity(self, parsed: HouseVote) -> tuple[Any, ...]:
        return parsed.roll["congress"], parsed.roll["roll_number"]

    def _expected(self, roll: RollFile) -> tuple[Any, ...]:
        return roll.congress, roll.remote.number

    def _describe(self, identity: tuple[Any, ...]) -> str:
        return f"Congress {identity[0]} roll {identity[1]}"

    def _people(self, conn: Any) -> dict[str, str]:
        return bioguide_people(conn)

    def _organization(self, conn: Any) -> str | None:
        return house_organization_id(conn)

    def _organization_missing(self) -> str:
        return (
            f"the House organization (ocd identifier {HOUSE_OCD_ORGANIZATION}) is not in the "
            "warehouse; new roll calls are loaded without an organization"
        )

    def _save(self, conn: Any, parsed: HouseVote, **kwargs: Any) -> dict[str, Any]:
        # Looked up by name at call time: a test replaces this module's ``save_house_roll_call``.
        return save_house_roll_call(conn, parsed, **kwargs)
