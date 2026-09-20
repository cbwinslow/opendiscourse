"""Read one Senate roll-call XML file into its lossless record and its typed fields (Story 11.2).

The Senate publishes each roll call at ``senate.gov/legislative/LIS/roll_call_votes/vote<C><S>/
vote_<C>_<S>_<NNNNN>.xml``. Two things come out of a file, both from the same parse:

- ``record``: every element and attribute, as JSON (the encoding of ``billstatus_record``), so a
  field nobody has modelled yet is still stored and queryable;
- typed fields for the columns people query: the roll-call header, the document and amendment
  blocks, the counts, the tie-breaker, and one entry per senator with the party, state and name as
  printed at the vote.

Nothing here touches the database or the network. A senator is identified by the LIS member id the
file states (``lis_member_id``); the printed name is kept as recorded and is never used to find a
person. The Vice President breaks a tie outside the member list: that is the ``tie_breaker`` block,
typed on the roll call, never a member vote. ``position`` is the normalized position
(``yes``/``no``/``not voting``/``other``, the vocabulary already in ``fact.member_vote``);
``position_raw`` is the file's own word (``Yea``, ``Present``, ``Guilty``).

Older files differ from newer ones (no ``modify_date`` or ``document_congress`` before about 2011,
one nesting level fewer in the amendment block, no ``<document>`` at all on a few 2021 rolls): every
optional block and field may be absent and is then NULL, never a guess.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from typing import Any
from xml.etree import ElementTree
from zoneinfo import ZoneInfo

from .billstatus_record import record_problems, record_sha256, xml_to_record

SENATE_LIST_TAGS = frozenset({"member"})  # one senator or a hundred: always an array
EASTERN = ZoneInfo("America/New_York")
_YES = {"yea", "aye", "yes"}
_NO = {"nay", "no"}
# "<thing decided> [Not] <positive ending>": the ending decides, a "not" directly before it turns it around.
_POSITIVE = re.compile(r"(?:^|\s)(not\s+)?(agreed to|confirmed|passed|adopted)$")
_NEGATIVE = ("rejected", "failed", "defeated")  # outcome words that are already negative
_MONTHS = {
    name: number
    for number, name in enumerate(
        (
            "january", "february", "march", "april", "may", "june",
            "july", "august", "september", "october", "november", "december",
        ),
        1,
    )
}
_STAMP = re.compile(r"^([A-Za-z]+) (\d{1,2}), (\d{4}),? (\d{1,2}):(\d{2}) ?([AP]M)$", re.IGNORECASE)
_ORDINALS = {"1": "1st", "2": "2nd", "3": "3rd"}
# The bill types core.bill holds, by the way the Senate prints a document's type.
BILL_TYPES = {
    "H.R.": "hr",
    "S.": "s",
    "H.Res.": "hres",
    "S.Res.": "sres",
    "H.Con.Res.": "hconres",
    "S.Con.Res.": "sconres",
    "H.J.Res.": "hjres",
    "S.J.Res.": "sjres",
}


@dataclass(frozen=True)
class SenateVote:
    """One parsed roll-call file."""

    record: dict[str, Any]
    record_sha256: str
    roll: dict[str, Any]
    party_totals: list[dict[str, Any]]  # always empty: the Senate file has no totals by party
    votes: list[dict[str, Any]]
    # Fields that loaded as NULL although the file had something: ``modified_unusable`` (a
    # modify_date that is not a date) and ``result_not_normalized`` (a vote_result that is not a plain
    # outcome, such as "Guilty" or "Veto Sustained"). The Connector counts them so the gap is visible.
    notes: tuple[str, ...] = ()


def normalize_position(raw: str) -> str:
    """The warehouse's position vocabulary for a word the Senate printed."""
    word = raw.strip().lower()
    if word in _YES:
        return "yes"
    if word in _NO:
        return "no"
    if word == "not voting":
        return "not voting"
    return "other"  # Present, Guilty, Not Guilty, anything else keeps its own word in position_raw


def normalize_result(raw: str | None) -> str | None:
    """``pass``/``fail`` for the results OpenStates rows already use; None for any other outcome.

    The Senate words a result as the thing decided plus the outcome ("Motion Agreed to", "Nomination
    Confirmed", "Cloture on the Motion to Proceed Rejected"). A positive ending (agreed to, confirmed,
    passed, adopted) is ``pass`` unless the word "not" stands directly before it ("Amendment Not
    Adopted", "Motion Not Agreed to"), which is ``fail``; rejected, failed and defeated are ``fail``.
    Anything else ("Not Guilty", "Veto Sustained", "Point of Order Well Taken") is None.
    """
    word = " ".join((raw or "").lower().split())
    if word.endswith(_NEGATIVE):
        return "fail"
    if match := _POSITIVE.search(word):
        return "fail" if match[1] else "pass"
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


def _stamp(value: str | None) -> tuple[date, str, datetime] | None:
    """``April 19, 2005,  02:51 PM`` -> (date, ``14:51``, UTC instant); Eastern clock time as the Senate posts it."""
    if value is None:
        return None
    match = _STAMP.match(" ".join(value.split()))
    if match is None or match[1].lower() not in _MONTHS:
        return None
    month, day, year, hour, minute, meridian = match[1].lower(), *match.groups()[1:]
    try:
        clock = time(int(hour) % 12 + (12 if meridian.upper() == "PM" else 0), int(minute))
        local = datetime.combine(date(int(year), _MONTHS[month], int(day)), clock, tzinfo=EASTERN)
    except ValueError:
        return None
    return local.date(), clock.strftime("%H:%M"), local.astimezone(UTC)


def _count(counts: ElementTree.Element | None, tag: str) -> int | None:
    """A count; the Senate prints an empty element for none (``<present/>``), which is zero."""
    if counts is None or counts.find(tag) is None:
        return None
    return _int(_text(counts, tag), tag) or 0


def _votes(root: ElementTree.Element) -> list[dict[str, Any]]:
    votes = []
    for member in root.findall("members/member"):
        raw = (member.findtext("vote_cast") or "").strip()
        votes.append(
            {
                "lis_member_id": _text(member, "lis_member_id"),
                "name": _text(member, "member_full"),
                "last_name": _text(member, "last_name"),
                "first_name": _text(member, "first_name"),
                "party": _text(member, "party"),
                "state": _text(member, "state"),
                "position_raw": raw,
                "position": normalize_position(raw),
            }
        )
    return votes


def _bill_link(congress: int, document: ElementTree.Element | None) -> dict[str, Any]:
    """The bill a roll call's document names, when it names one.

    A bill lives and dies within its Congress, so an older file with no ``document_congress`` refers
    to the roll call's own Congress. Anything that is not a bill (a nomination, a treaty, an
    amendment, an empty block) links to nothing: it stays in the document columns as printed.
    """
    empty = {"link_congress": None, "link_bill_type": None, "link_bill_number": None}
    if document is None:
        return empty
    bill_type = BILL_TYPES.get(_text(document, "document_type") or "")
    number = _text(document, "document_number")
    if bill_type is None or number is None or not number.isdigit():
        return empty
    stated = _int(_text(document, "document_congress"), "document_congress")
    return {"link_congress": stated or congress, "link_bill_type": bill_type, "link_bill_number": number}


def parse_senate_vote(data: bytes) -> SenateVote:
    """Parse one roll-call file. Raises ``ElementTree.ParseError`` or ``ValueError`` if unusable.

    Also proves the record lossless (every element, attribute and value of the XML), so a file the
    encoding cannot hold is reported instead of stored short.
    """
    root = ElementTree.fromstring(data)
    if root.tag != "roll_call_vote":
        raise ValueError(f"root element is <{root.tag}>, expected <roll_call_vote>")
    record = xml_to_record(root, SENATE_LIST_TAGS)
    if problems := record_problems(root, record):
        raise ValueError(f"record is not lossless: {problems[0]}")
    congress = _int(_text(root, "congress"), "congress")
    number = _int(_text(root, "vote_number"), "vote_number")
    year = _int(_text(root, "congress_year"), "congress_year")
    if congress is None or number is None or year is None:
        raise ValueError("congress, vote_number and congress_year are required")
    session = _text(root, "session")
    voted = _stamp(_text(root, "vote_date"))
    if voted is None:
        raise ValueError(f"vote_date {_text(root, 'vote_date')!r} is not 'Month D, YYYY, HH:MM AM'")
    modified = _stamp(_text(root, "modify_date"))
    document, amendment = root.find("document"), root.find("amendment")
    counts, tie = root.find("count"), root.find("tie_breaker")

    def block(parent: ElementTree.Element | None, tag: str) -> str | None:
        return _text(parent, tag) if parent is not None else None

    roll = {
        "congress": congress,
        "roll_number": number,
        "roll_year": year,
        "session_number": _int(session, "session"),
        "congress_session": _ORDINALS.get(session or "", session),
        "question": _text(root, "question"),
        "vote_question_text": _text(root, "vote_question_text"),
        "vote_document_text": _text(root, "vote_document_text"),
        "vote_result_text": _text(root, "vote_result_text"),
        "vote_title": _text(root, "vote_title"),
        "vote_result": _text(root, "vote_result"),
        "majority_requirement": _text(root, "majority_requirement"),
        "action_date": voted[0],
        "action_time_etz": voted[1],
        "occurred_at": voted[2],
        "modified_at": modified[2] if modified else None,
        "document_congress": _int(block(document, "document_congress"), "document_congress"),
        "document_type": block(document, "document_type"),
        "document_number": block(document, "document_number"),
        "document_name": block(document, "document_name"),
        "document_title": block(document, "document_title"),
        "document_short_title": block(document, "document_short_title"),
        "amendment_number": block(amendment, "amendment_number"),
        "amendment_to_amendment_number": block(amendment, "amendment_to_amendment_number"),
        "amendment_to_amendment_to_amendment_number": block(
            amendment, "amendment_to_amendment_to_amendment_number"
        ),
        "amendment_to_document_number": block(amendment, "amendment_to_document_number"),
        "amendment_to_document_short_title": block(amendment, "amendment_to_document_short_title"),
        "amendment_purpose": block(amendment, "amendment_purpose"),
        "yea_total": _count(counts, "yeas"),
        "nay_total": _count(counts, "nays"),
        "present_total": _count(counts, "present"),
        "not_voting_total": _count(counts, "absent"),
        "tie_breaker_by": block(tie, "by_whom"),
        "tie_breaker_vote": block(tie, "tie_breaker_vote"),
        **_bill_link(congress, document),
    }
    roll["result"] = normalize_result(roll["vote_result"])
    notes = []
    if _text(root, "modify_date") and modified is None:
        notes.append("modified_unusable")
    if roll["vote_result"] and roll["result"] is None:
        notes.append("result_not_normalized")
    return SenateVote(record, record_sha256(record), roll, [], _votes(root), tuple(notes))
