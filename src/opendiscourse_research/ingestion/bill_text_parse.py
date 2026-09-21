"""Read one GovInfo BILLS XML member into its lossless record and typed version identity.

GovInfo publishes each bill version as XML in the BILLS bulk collection (one zip per
Congress × session × bill type). Two things come out of a file, both from the same parse:

- ``record``: every element and attribute, as JSON (the encoding of ``billstatus_record``);
- typed version identity: congress, type, number and version code from the *filename*,
  plus a title and date when the file states them.

The parser never fetches ``bill.dtd`` / ``billres.xsl``. Sponsor ``name-id`` values stay
in the record; they are not used to find a person. Version code is the filename suffix
(``ih``, ``eh``, ``rh``, ``pcs``, …), not a guessed mapping from ``bill-stage``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from xml.etree import ElementTree

from ..providers.govinfo import bills_member_identity
from .billstatus_record import record_problems, record_sha256, xml_to_record

# Tags that may appear once or many times; always arrays so shapes do not vary with count.
BILLS_LIST_TAGS = frozenset(
    {
        "sponsor",
        "cosponsor",
        "committee-name",
        "section",
        "subsection",
        "paragraph",
        "subparagraph",
        "clause",
        "subclause",
        "item",
        "quoted-block",
        "toc-entry",
        "whereas",
    }
)
_DOCTYPE = re.compile(rb"<!DOCTYPE\b[^>]*>", re.IGNORECASE | re.DOTALL)
_XML_DECL = re.compile(rb"^\s*<\?xml\b[^?]*\?>", re.IGNORECASE | re.DOTALL)
# Named entities from bill.dtd / res.dtd. We do not fetch those files; after the
# DOCTYPE is stripped, expat would otherwise ParseError on &nbsp; and friends.
_LOCAL_ENTITIES = (
    b"<!DOCTYPE bills [\n"
    b'<!ENTITY nbsp "&#160;">\n'
    b'<!ENTITY ndash "&#8211;">\n'
    b'<!ENTITY mdash "&#8212;">\n'
    b'<!ENTITY lsquo "&#8216;">\n'
    b'<!ENTITY rsquo "&#8217;">\n'
    b'<!ENTITY ldquo "&#8220;">\n'
    b'<!ENTITY rdquo "&#8221;">\n'
    b'<!ENTITY hellip "&#8230;">\n'
    b'<!ENTITY bull "&#8226;">\n'
    b"]>\n"
)
_DC_IDENTITY = re.compile(
    r"^(?P<congress>\d+)\s+(?P<type>HCONRES|HJRES|HR|HRES|SCONRES|SJRES|SRES|S)"
    r"\s+(?P<number>\d+)\s+(?P<version>[A-Z][A-Z0-9]*)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class BillText:
    """One parsed BILLS XML member."""

    record: dict[str, Any]
    record_sha256: str
    congress: int
    bill_type: str
    bill_number: str
    version_code: str
    title: str | None
    published_at: datetime | None
    bill_stage: str | None
    root_tag: str
    source_member: str


def parse_xml_without_dtd(content: bytes) -> ElementTree.Element:
    """Parse GovInfo BILLS XML without resolving the DTD (we do not fetch bill.dtd)."""
    stripped = _DOCTYPE.sub(b"", content)
    match = _XML_DECL.match(stripped)
    if match:
        body = stripped[: match.end()] + _LOCAL_ENTITIES + stripped[match.end() :]
    else:
        body = _LOCAL_ENTITIES + stripped
    return ElementTree.fromstring(body)


def _body_identity(root: ElementTree.Element) -> tuple[int, str, int, str] | None:
    """Congress, type, number and version as the XML body states them, if it does.

    Taken from Dublin Core title (``119 HR 23 IH: …``). Unparseable titles are ignored
    rather than guessed; a filename that disagrees with a parseable title is refused.
    """
    raw = _dc(root, "title")
    if not raw:
        return None
    match = _DC_IDENTITY.match(raw)
    if not match:
        return None
    return (
        int(match.group("congress")),
        match.group("type").lower(),
        int(match.group("number")),
        match.group("version").lower(),
    )


def _text(element: ElementTree.Element | None) -> str | None:
    if element is None:
        return None
    value = "".join(element.itertext()).strip()
    return value or None


def _dc(root: ElementTree.Element, local: str) -> str | None:
    tag = f"{{http://purl.org/dc/elements/1.1/}}{local}"
    for element in root.iter():
        if element.tag == tag:
            return _text(element)
    return None


def _published_at(root: ElementTree.Element) -> datetime | None:
    raw = _dc(root, "date")
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw)
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    except ValueError:
        return None


def parse_bills_xml(content: bytes, member_name: str) -> BillText:
    """Lossless record plus typed version identity for one BILLS XML member."""
    identity = bills_member_identity(member_name)
    if identity is None:
        raise ValueError(f"{member_name}: not a BILLS version file name")
    congress, bill_type, number, version_code = identity
    root = parse_xml_without_dtd(content)
    body = _body_identity(root)
    if body is not None and body != identity:
        raise ValueError(
            f"{member_name} describes {body}, not the version its name promises"
        )
    record = xml_to_record(root, list_tags=BILLS_LIST_TAGS, capture_tails=True)
    problems = record_problems(root, record)
    if problems:
        raise ValueError(f"{member_name}: record is not lossless ({problems[0]})")
    title = _text(root.find("./form/official-title")) or _dc(root, "title")
    stage = root.get("bill-stage") or root.get("resolution-stage")
    return BillText(
        record=record,
        record_sha256=record_sha256(record),
        congress=congress,
        bill_type=bill_type,
        bill_number=str(number),
        version_code=version_code,
        title=title,
        published_at=_published_at(root),
        bill_stage=stage,
        root_tag=root.tag.split("}", 1)[-1],
        source_member=member_name,
    )
