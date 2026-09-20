"""Read one House Clerk roll-call XML file into its lossless record and its typed fields (Story 11.1).

The Clerk publishes each roll call at ``clerk.house.gov/evs/<year>/roll<NNN>.xml``. Two things come
out of a file, both from the same parse:

- ``record``: every element and attribute, as JSON (the encoding of ``billstatus_record``), so a
  field nobody has modelled yet is still stored and queryable;
- typed fields for the columns people query: the roll-call header, totals by party, and one entry
  per recorded vote with the member's party, state and printed name as recorded at the vote.

Nothing here touches the database or the network. A member is identified by the BioGuide
``name-id`` the file states; the printed name is kept as recorded and is never used to find a
person. ``position`` is the normalized position (``yes``/``no``/``not voting``/``other``, the
vocabulary of the OpenStates rows already in ``fact.member_vote``); ``position_raw`` is the file's
own word (``Yea``, ``Aye``, ``Present``, or a Speaker candidate's name).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from typing import Any
from xml.etree import ElementTree
from zoneinfo import ZoneInfo

from .billstatus_record import record_problems, record_sha256, xml_to_record

# Repeat within their parent or not depending on the roll call; always arrays so shapes do not vary.
HOUSE_LIST_TAGS = frozenset({"recorded-vote", "totals-by-party", "totals-by-candidate"})
EASTERN = ZoneInfo("America/New_York")
_YES = {"yea", "aye", "yes"}
_NO = {"nay", "no"}
_PASS = {"passed", "agreed to", "adopted"}
_FAIL = {"failed", "rejected", "not agreed to"}
_MONTHS = {
    name: number
    for number, name in enumerate(
        ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"), 1
    )
}


@dataclass(frozen=True)
class HouseVote:
    """One parsed roll-call file."""

    record: dict[str, Any]
    record_sha256: str
    roll: dict[str, Any]
    party_totals: list[dict[str, Any]]
    votes: list[dict[str, Any]]
    # Fields that loaded as NULL although the file had something: ``time_unusable`` (a time-etz that
    # is not a clock time) and ``result_not_normalized`` (a vote-result that is not a plain outcome,
    # as in a Speaker election). The Connector counts them so the gap is visible, not silent.
    notes: tuple[str, ...] = ()


def normalize_position(raw: str) -> str:
    """The warehouse's position vocabulary for a word the Clerk printed."""
    word = raw.strip().lower()
    if word in _YES:
        return "yes"
    if word in _NO:
        return "no"
    if word == "not voting":
        return "not voting"
    return "other"  # Present, a Speaker candidate's name, anything else


def normalize_result(raw: str | None) -> str | None:
    """``pass``/``fail`` for the results OpenStates rows already use; None for any other outcome."""
    word = (raw or "").strip().lower()
    if word in _PASS:
        return "pass"
    if word in _FAIL:
        return "fail"
    return None


def _text(parent: ElementTree.Element, tag: str) -> str | None:
    """A child's text, stripped; None when the child is absent or empty."""
    child = parent.find(tag)
    value = (child.text or "").strip() if child is not None else ""
    return value or None


def _int(value: str | None, what: str) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        raise ValueError(f"{what} {value!r} is not a number") from None


def _action_date(value: str | None) -> date | None:
    """``4-Jan-2007`` (the Clerk's form, day without padding); anything else is an error."""
    if value is None:
        return None
    try:
        day, month, year = value.split("-")
        return date(int(year), _MONTHS[month.lower()], int(day))
    except (ValueError, KeyError):
        raise ValueError(f"action-date {value!r} is not d-Mon-yyyy") from None


def _occurred_at(day: date | None, etz: str | None) -> datetime | None:
    """Date plus the Eastern clock time the file states, as UTC; None when either is unknown."""
    if day is None or not etz:
        return None
    try:
        hour, minute = (int(part) for part in etz.split(":")[:2])
        return datetime.combine(day, time(hour, minute), tzinfo=EASTERN).astimezone(UTC)
    except ValueError:
        return None


def _party_totals(metadata: ElementTree.Element) -> list[dict[str, Any]]:
    rows = []
    for node in metadata.findall("vote-totals/totals-by-party"):
        party = _text(node, "party")
        if party is None:
            continue
        rows.append(
            {
                "party": party,
                "yea_total": _int(_text(node, "yea-total"), "yea-total"),
                "nay_total": _int(_text(node, "nay-total"), "nay-total"),
                "present_total": _int(_text(node, "present-total"), "present-total"),
                "not_voting_total": _int(_text(node, "not-voting-total"), "not-voting-total"),
            }
        )
    return rows


def _votes(root: ElementTree.Element) -> list[dict[str, Any]]:
    votes = []
    for entry in root.findall("vote-data/recorded-vote"):
        legislator = entry.find("legislator")
        raw = (entry.findtext("vote") or "").strip()
        attrs = legislator.attrib if legislator is not None else {}
        votes.append(
            {
                "bioguide_id": (attrs.get("name-id") or "").strip() or None,
                "name": ((legislator.text or "").strip() if legislator is not None else "") or None,
                "sort_name": attrs.get("sort-field"),
                "unaccented_name": attrs.get("unaccented-name"),
                "party": attrs.get("party"),
                "state": attrs.get("state"),
                "role": attrs.get("role"),
                "position_raw": raw,
                "position": normalize_position(raw),
            }
        )
    return votes


def parse_house_vote(data: bytes) -> HouseVote:
    """Parse one roll-call file. Raises ``ElementTree.ParseError`` or ``ValueError`` if unusable.

    Also proves the record lossless (every element, attribute and value of the XML), so a file the
    encoding cannot hold is reported instead of stored short.
    """
    root = ElementTree.fromstring(data)
    if root.tag != "rollcall-vote":
        raise ValueError(f"root element is <{root.tag}>, expected <rollcall-vote>")
    metadata = root.find("vote-metadata")
    if metadata is None:
        raise ValueError("no <vote-metadata>")
    record = xml_to_record(root, HOUSE_LIST_TAGS)
    if problems := record_problems(root, record):
        raise ValueError(f"record is not lossless: {problems[0]}")
    congress = _int(_text(metadata, "congress"), "congress")
    number = _int(_text(metadata, "rollcall-num"), "rollcall-num")
    if congress is None or number is None:
        raise ValueError("congress and rollcall-num are required")
    day = _action_date(_text(metadata, "action-date"))
    time_node = metadata.find("action-time")
    etz = (time_node.get("time-etz") or "").strip() if time_node is not None else ""
    totals = metadata.find("vote-totals/totals-by-vote")
    total = (lambda tag: _int(_text(totals, tag), tag)) if totals is not None else (lambda tag: None)
    roll = {
        "congress": congress,
        "roll_number": number,
        "congress_session": _text(metadata, "session"),
        # Some early-2007 files name the chamber in <committee> instead of <chamber>.
        "chamber_label": _text(metadata, "chamber") or _text(metadata, "committee"),
        "legislative_number": _text(metadata, "legis-num"),
        "question": _text(metadata, "vote-question"),
        "vote_type": _text(metadata, "vote-type"),
        "vote_result": _text(metadata, "vote-result"),
        "majority_party": _text(metadata, "majority"),
        "vote_description": _text(metadata, "vote-desc"),
        "amendment_number": _text(metadata, "amendment-num"),
        "amendment_author": _text(metadata, "amendment-author"),
        "action_date": day,
        "action_time_etz": etz or None,
        "occurred_at": _occurred_at(day, etz),
        "yea_total": total("yea-total"),
        "nay_total": total("nay-total"),
        "present_total": total("present-total"),
        "not_voting_total": total("not-voting-total"),
    }
    roll["result"] = normalize_result(roll["vote_result"])
    notes = []
    if etz and roll["occurred_at"] is None:
        notes.append("time_unusable")
    if roll["vote_result"] and roll["result"] is None:
        notes.append("result_not_normalized")
    return HouseVote(record, record_sha256(record), roll, _party_totals(metadata), _votes(root), tuple(notes))
