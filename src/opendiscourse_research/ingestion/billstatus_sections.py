"""Typed rows for the BILLSTATUS sections promoted out of the full record (Story 9.5b).

Each function reads one section of a ``<bill>`` element and returns dictionaries ready for the
matching ``core.bill_*`` table. The full record (``billstatus_record``) keeps everything; these
are the parts modelled so far: CRS summaries, enacted laws, related bills and amendments.
Dates and timestamps stay as the source's ISO text; the upsert SQL casts them.
"""

from __future__ import annotations

from typing import Any
from xml.etree import ElementTree


def _clean(value: str | None) -> str | None:
    """Stripped text, or None when blank."""
    return value.strip() if value and value.strip() else None


def _first(element: ElementTree.Element, *paths: str) -> str | None:
    """The first non-blank text among ``paths`` (an XML element repeats scalars in a few files)."""
    for path in paths:
        if text := _clean(element.findtext(path)):
            return text
    return None


def summaries(bill: ElementTree.Element, member: str | None) -> list[dict[str, Any]]:
    """CRS summaries: ``summaries/summary``, or ``summaries/billSummaries/item`` in 13 old-style files."""
    items = bill.findall("./summaries/summary") or bill.findall("./summaries/billSummaries/item")
    return [
        {
            "version_code": _first(item, "versionCode"),
            "action_date": _first(item, "actionDate"),
            "action_description": _first(item, "actionDesc", "name"),
            "update_date": _first(item, "updateDate"),
            "text": _first(item, "text", "cdata/text"),
            "source_ordinal": ordinal,
            "source_member": member,
        }
        for ordinal, item in enumerate(items, start=1)
    ]


def laws(bill: ElementTree.Element, member: str | None) -> list[dict[str, Any]]:
    """Public and private laws the bill became (``laws/item``: type and number)."""
    return [
        {
            "law_type": _first(item, "type"),
            "law_number": _first(item, "number"),
            "source_ordinal": ordinal,
            "source_member": member,
        }
        for ordinal, item in enumerate(bill.findall("./laws/item"), start=1)
        if _first(item, "number")
    ]


def related_bills(bill: ElementTree.Element, member: str | None) -> list[dict[str, Any]]:
    """Bills CRS relates to this one, with each relationship (identical, related, procedural...)."""
    rows = []
    for ordinal, item in enumerate(bill.findall("./relatedBills/item"), start=1):
        number = _first(item, "number")
        congress = _first(item, "congress")
        bill_type = _first(item, "type")
        if not (number and congress and bill_type):
            continue
        rows.append(
            {
                "related_congress": int(congress),
                # lower case, like core.bill.bill_type, so the two join
                "related_bill_type": bill_type.lower(),
                "related_bill_number": number,
                "title": _first(item, "title", "latestTitle"),
                "latest_action_date": _first(item, "latestAction/actionDate"),
                "latest_action_text": _first(item, "latestAction/text"),
                "relationships": [
                    {"type": _first(rel, "type"), "identified_by": _first(rel, "identifiedBy")}
                    for rel in item.findall("./relationshipDetails/item")
                ],
                "source_ordinal": ordinal,
                "source_member": member,
            }
        )
    return rows


def amendments(bill: ElementTree.Element, member: str | None) -> list[dict[str, Any]]:
    """Amendments to the bill, keyed by their own congress, type (HAMDT/SAMDT) and number.

    The sponsor is kept by BioGuide id only (people join on BioGuide, never on the name).
    """
    rows = []
    for ordinal, item in enumerate(bill.findall("./amendments/amendment"), start=1):
        number = _first(item, "number")
        congress = _first(item, "congress")
        amendment_type = _first(item, "type")
        if not (number and congress and amendment_type):
            continue
        amended = item.find("./amendedAmendment")
        rows.append(
            {
                "amendment_congress": int(congress),
                "amendment_type": amendment_type,
                "amendment_number": number,
                "chamber": _first(item, "chamber"),
                "purpose": _first(item, "purpose"),
                "description": _first(item, "description"),
                "submitted_at": _first(item, "submittedDate"),
                "proposed_at": _first(item, "proposedDate"),
                "update_date": _first(item, "updateDate"),
                "latest_action_date": _first(item, "latestAction/actionDate"),
                "latest_action_text": _first(item, "latestAction/text"),
                "sponsor_bioguide_id": _first(
                    item, "./sponsors/item/bioguideId", "./sponsors/item/identifiers/bioguideId"
                ),
                "metadata": (
                    {
                        "amended_amendment": {
                            "congress": _first(amended, "congress"),
                            "type": _first(amended, "type"),
                            "number": _first(amended, "number"),
                        }
                    }
                    if amended is not None and _first(amended, "number")
                    else {}
                ),
                "source_ordinal": ordinal,
                "source_member": member,
            }
        )
    return rows


def cbo_cost_estimates(bill: ElementTree.Element, member: str | None) -> list[dict[str, Any]]:
    """CBO estimates published with a bill (``cboCostEstimates/item``)."""
    return [
        {
            "published_at": _first(item, "pubDate"),
            "title": _first(item, "title"),
            "source_url": _first(item, "url"),
            "description": _first(item, "description"),
            "source_ordinal": ordinal,
            "source_member": member,
        }
        for ordinal, item in enumerate(bill.findall("./cboCostEstimates/item"), start=1)
    ]
