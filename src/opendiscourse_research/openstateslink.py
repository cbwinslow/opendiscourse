"""Link OpenStates rows to owned rows by stable identifiers.

A match is an equal identifier in an approved namespace. Display name, party,
district, office, and biography are never compared. A state bill label such as
``HB 264`` is not a Congress bill type and number.

Every person identifier, link, name, source, office, and contact column is
kept. Twitter and the other contact schemes are stored. They do not merge
two people. BioGuide is the only person join this module trusts.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass

# OpenStates asserts this scheme. It is the only person bridge this module trusts.
PERSON_LINK_SCHEME = "bioguide"
# These schemes are contact details. They are stored, and they are not join keys.
SOCIAL_SCHEMES = frozenset({"twitter", "facebook", "instagram", "youtube", "mastodon"})
PERSON_CONTACT_TABLES = (
    "opencivicdata_person",
    "opencivicdata_personidentifier",
    "opencivicdata_personlink",
    "opencivicdata_personname",
    "opencivicdata_personsource",
    "openstates_personoffice",
)
US_JURISDICTION_ID = "ocd-jurisdiction/country:us/government"
_FEDERAL_BILL = re.compile(
    r"^(hr|s|hres|sres|hjres|sjres|hconres|sconres) (\d+)$",
    re.IGNORECASE,
)
_VOTE_KEY = re.compile(r"^us-\d{4}-(?:lower|upper)-\d+$")
_PROTECTED_DATABASES = frozenset(
    {"openstates", "opendiscourse", "postgres", "template0", "template1"}
)


@dataclass(frozen=True)
class PersonLink:
    """One OpenStates person and the owned person a BioGuide id selects."""

    ocd_person_id: str
    bioguide: str
    person_id: str | None
    conflict: str | None = None


@dataclass(frozen=True)
class BillLink:
    """One federal OpenStates bill and the owned bill its Congress key selects."""

    ocd_bill_id: str
    congress: str
    bill_type: str
    bill_number: str
    bill_id: str | None


@dataclass(frozen=True)
class VoteLink:
    """OpenStates vote events that share one official roll-call key."""

    external_id: str
    ocd_vote_ids: tuple[str, ...]
    matched: bool


@dataclass(frozen=True)
class RetainedContact:
    """One source value kept for later use.

    ``joins_people`` is true only for a BioGuide identifier. A shared Twitter
    handle is recorded and does not select an owned person by itself.
    ``fields`` holds every non-empty column from the source row.
    """

    ocd_person_id: str
    table: str
    kind: str
    scheme: str
    value: str
    fields: tuple[tuple[str, str], ...]
    person_id: str | None
    joins_people: bool
    shared_with_other_person: bool = False


def link_people(
    rows: list[tuple[str, str, str]],
    owned_bioguide: Mapping[str, str],
) -> list[PersonLink]:
    """Match ``(ocd_person_id, scheme, identifier)`` rows on BioGuide only.

    Any other scheme is ignored. Two BioGuide values for one person, or one
    BioGuide value on two OpenStates people, are conflicts and do not match.
    """
    by_person: dict[str, set[str]] = defaultdict(set)
    by_bioguide: dict[str, set[str]] = defaultdict(set)
    for ocd_person_id, scheme, identifier in rows:
        if scheme != PERSON_LINK_SCHEME:
            continue
        bioguide = identifier.strip()
        if not bioguide:
            continue
        by_person[ocd_person_id].add(bioguide)
        by_bioguide[bioguide].add(ocd_person_id)

    links: list[PersonLink] = []
    seen: set[tuple[str, str]] = set()
    for ocd_person_id, bioguides in sorted(by_person.items()):
        for bioguide in sorted(bioguides):
            key = (ocd_person_id, bioguide)
            if key in seen:
                continue
            seen.add(key)
            conflict = None
            if len(bioguides) > 1:
                conflict = "person_has_multiple_bioguide_ids"
            elif len(by_bioguide[bioguide]) > 1:
                conflict = "bioguide_claimed_by_multiple_people"
            person_id = None if conflict else owned_bioguide.get(bioguide)
            links.append(
                PersonLink(
                    ocd_person_id=ocd_person_id,
                    bioguide=bioguide,
                    person_id=person_id,
                    conflict=conflict,
                )
            )
    return links


def source_fields(row: Mapping[str, object]) -> tuple[tuple[str, str], ...]:
    """Return every non-empty column. Nested JSON is kept as stable text."""
    kept: list[tuple[str, str]] = []
    for key in sorted(row):
        value = row[key]
        if value is None:
            continue
        if isinstance(value, (dict, list)):
            text = json.dumps(value, sort_keys=True, default=str, separators=(",", ":"))
        else:
            text = str(value).strip()
        if text:
            kept.append((str(key), text))
    return tuple(kept)


def _owned_person_ids(links: list[PersonLink]) -> dict[str, str | None]:
    """Map an OpenStates person to an owned id only when BioGuide is unambiguous."""
    grouped: dict[str, list[PersonLink]] = defaultdict(list)
    for link in links:
        grouped[link.ocd_person_id].append(link)
    owned: dict[str, str | None] = {}
    for ocd_person_id, person_links in grouped.items():
        if len(person_links) == 1 and person_links[0].conflict is None and person_links[0].person_id:
            owned[ocd_person_id] = person_links[0].person_id
        else:
            owned[ocd_person_id] = None
    return owned


def retain_person_contact(
    *,
    identifiers: list[tuple[str, str, str]] | None = None,
    people: list[Mapping[str, object]] | None = None,
    links: list[Mapping[str, object]] | None = None,
    names: list[Mapping[str, object]] | None = None,
    sources: list[Mapping[str, object]] | None = None,
    offices: list[Mapping[str, object]] | None = None,
    owned_bioguide: Mapping[str, str] | None = None,
) -> tuple[list[PersonLink], list[RetainedContact]]:
    """Keep every contact field and link people only through BioGuide.

    ``identifiers`` are ``(ocd_person_id, scheme, identifier)`` rows. Mapping
    rows are the publisher tables named in ``PERSON_CONTACT_TABLES``. A blank
    value is the publisher having nothing to say. Every other column is kept.
    """
    identifier_rows = identifiers or []
    person_links = link_people(identifier_rows, owned_bioguide or {})
    owned = _owned_person_ids(person_links)
    retained: list[RetainedContact] = []

    def add(ocd_person_id: str, table: str, kind: str, scheme: str, value: str, fields: tuple[tuple[str, str], ...], *, joins: bool) -> None:
        text = value.strip()
        if not ocd_person_id or not text:
            return
        retained.append(
            RetainedContact(
                ocd_person_id=ocd_person_id,
                table=table,
                kind=kind,
                scheme=scheme,
                value=text,
                fields=fields,
                person_id=owned.get(ocd_person_id),
                joins_people=joins,
            )
        )

    for ocd_person_id, scheme, identifier in identifier_rows:
        scheme_text = (scheme or "").strip()
        identifier_text = (identifier or "").strip()
        if not scheme_text or not identifier_text:
            continue
        kind = "social" if scheme_text in SOCIAL_SCHEMES else "identifier"
        add(
            ocd_person_id,
            "opencivicdata_personidentifier",
            kind,
            scheme_text,
            identifier_text,
            (("identifier", identifier_text), ("person_id", ocd_person_id), ("scheme", scheme_text)),
            joins=scheme_text == PERSON_LINK_SCHEME,
        )

    for row in people or []:
        ocd_person_id = str(row.get("id") or row.get("person_id") or "")
        fields = source_fields(row)
        for column, text in fields:
            if column in {"id", "person_id"}:
                continue
            kind = "email" if column == "email" else "person_field"
            add(ocd_person_id, "opencivicdata_person", kind, column, text, fields, joins=False)
    for row in links or []:
        ocd_person_id = str(row.get("person_id") or "")
        fields = source_fields(row)
        url = str(row.get("url") or "").strip()
        note = str(row.get("note") or "link").strip() or "link"
        add(ocd_person_id, "opencivicdata_personlink", "link", note, url or note, fields, joins=False)
    for row in names or []:
        ocd_person_id = str(row.get("person_id") or "")
        fields = source_fields(row)
        add(
            ocd_person_id,
            "opencivicdata_personname",
            "name",
            str(row.get("note") or "name"),
            str(row.get("name") or ""),
            fields,
            joins=False,
        )
    for row in sources or []:
        ocd_person_id = str(row.get("person_id") or "")
        fields = source_fields(row)
        url = str(row.get("url") or "").strip()
        note = str(row.get("note") or "source").strip() or "source"
        add(ocd_person_id, "opencivicdata_personsource", "source", note, url or note, fields, joins=False)
    for row in offices or []:
        ocd_person_id = str(row.get("person_id") or "")
        fields = source_fields(row)
        classification = str(row.get("classification") or "office").strip() or "office"
        for column in ("address", "voice", "fax", "name"):
            add(
                ocd_person_id,
                "openstates_personoffice",
                "office",
                f"{classification}:{column}",
                str(row.get(column) or ""),
                fields,
                joins=False,
            )

    seen: dict[tuple[str, str], set[str]] = defaultdict(set)
    for item in retained:
        seen[(item.scheme, item.value)].add(item.ocd_person_id)
    marked = [
        RetainedContact(
            ocd_person_id=item.ocd_person_id,
            table=item.table,
            kind=item.kind,
            scheme=item.scheme,
            value=item.value,
            fields=item.fields,
            person_id=item.person_id,
            joins_people=item.joins_people,
            shared_with_other_person=len(seen[(item.scheme, item.value)]) > 1,
        )
        for item in retained
    ]
    return person_links, marked


def federal_bill_key(session: str, identifier: str) -> tuple[str, str, str] | None:
    """Return ``(congress, bill_type, bill_number)`` or None.

    ``HR 1`` in a numeric Congress session is a federal key. ``HB 264`` is not.
    """
    if not session.isdigit():
        return None
    match = _FEDERAL_BILL.fullmatch(identifier.strip())
    if match is None:
        return None
    return session, match.group(1).lower(), str(int(match.group(2)))


def link_federal_bills(
    rows: list[tuple[str, str, str, str]],
    owned: Mapping[tuple[str, str, str], str],
) -> list[BillLink]:
    """Match ``(ocd_bill_id, jurisdiction_id, session, identifier)`` rows.

    Rows outside the United States government jurisdiction, and labels that are
    not a Congress bill type and number, are omitted rather than guessed.
    """
    links: list[BillLink] = []
    for ocd_bill_id, jurisdiction_id, session, identifier in rows:
        if jurisdiction_id != US_JURISDICTION_ID:
            continue
        key = federal_bill_key(session, identifier)
        if key is None:
            continue
        congress, bill_type, bill_number = key
        links.append(
            BillLink(
                ocd_bill_id=ocd_bill_id,
                congress=congress,
                bill_type=bill_type,
                bill_number=bill_number,
                bill_id=owned.get(key),
            )
        )
    return links


def link_votes(
    events: list[tuple[str, str]],
    owned_external_ids: set[str],
) -> list[VoteLink]:
    """Group ``(ocd_vote_id, identifier)`` events onto official roll-call keys.

    Several OpenStates events may share one key. Events whose identifier is not
    ``us-<year>-lower|upper-<roll>`` are left unmatched and omitted.
    """
    grouped: dict[str, list[str]] = defaultdict(list)
    for ocd_vote_id, identifier in events:
        if _VOTE_KEY.fullmatch(identifier or "") is None:
            continue
        grouped[identifier].append(ocd_vote_id)
    return [
        VoteLink(
            external_id=external_id,
            ocd_vote_ids=tuple(sorted(vote_ids)),
            matched=external_id in owned_external_ids,
        )
        for external_id, vote_ids in sorted(grouped.items())
    ]


def candidate_database_name(period: str, checksum: str) -> str:
    """Name a restore target from the month and the dump checksum.

    The result is never ``openstates`` or ``opendiscourse``.
    """
    if not re.fullmatch(r"\d{4}-\d{2}", period):
        raise ValueError("period must use YYYY-MM")
    if not re.fullmatch(r"[0-9a-f]{64}", checksum):
        raise ValueError("checksum must be a lowercase SHA-256")
    name = f"openstates_{period.replace('-', '')}_{checksum[:12]}"
    assert_restore_target(name)
    return name


def assert_restore_target(database: str) -> None:
    """Refuse a restore aimed at the live snapshot or the warehouse."""
    if database in _PROTECTED_DATABASES or not database.startswith("openstates_"):
        raise ValueError(f"refusing to restore into {database}")


def activation_rename_plan(*, candidate: str, previous_label: str) -> list[str]:
    """Return the rename sequence that swaps a validated candidate into service.

    The foreign server keeps ``dbname=openstates``. These statements are not
    executed here. ``previous_label`` is a short checksum or ``unattested``.
    """
    assert_restore_target(candidate)
    if not re.fullmatch(r"[a-z0-9_]{1,40}", previous_label):
        raise ValueError("previous snapshot label is not a safe database suffix")
    previous = f"openstates_previous_{previous_label}"
    assert_restore_target(previous)
    return [
        "REVOKE CONNECT ON DATABASE openstates FROM openstates_fdw",
        "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = 'openstates'",
        f"ALTER DATABASE openstates RENAME TO {previous}",
        f"ALTER DATABASE {candidate} RENAME TO openstates",
        "GRANT CONNECT ON DATABASE openstates TO openstates_fdw",
    ]
