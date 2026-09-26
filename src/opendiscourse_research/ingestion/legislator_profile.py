"""Biography, leadership, contact, social accounts, and district offices.

The two member files already hold biography, leadership, and the Washington
office printed on a term. Social accounts and district offices are separate
files in the same checkout. People are linked on BioGuide only.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from datetime import date
from typing import Any

import yaml

CONTACT_KEYS = ("office", "address", "phone", "fax", "contact_form", "url", "rss_url")
SOCIAL_PAIRS = (
    ("twitter", "twitter", "twitter_id"),
    ("facebook", "facebook", None),
    ("instagram", "instagram", "instagram_id"),
    ("youtube", "youtube", "youtube_id"),
    ("mastodon", "mastodon", None),
)
SOCIAL_KEYS = {key for _, handle, external in SOCIAL_PAIRS for key in (handle, external) if key}
_Loader = getattr(yaml, "CSafeLoader", yaml.SafeLoader)


def load_yaml(content: bytes | str) -> list[dict[str, Any]]:
    """Parse one profile YAML file. An empty file is an empty list, not a guess."""
    records = yaml.load(content, Loader=_Loader)
    if records is None:
        return []
    if not isinstance(records, list):
        raise ValueError("profile file must be a YAML list")
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            raise ValueError(f"profile record #{index} is not a mapping")
    return records


def contact_from_term(record: Mapping[str, Any]) -> dict[str, str]:
    """Washington office fields printed on one term. Absent fields stay absent."""
    contact: dict[str, str] = {}
    for key in CONTACT_KEYS:
        value = record.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            contact[key] = text
    return contact


def _date(value: Any, label: str) -> date:
    if isinstance(value, date):
        return value
    text = str(value or "").strip()
    try:
        return date.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"{label} is not a date: {value!r}") from exc


def entry_bioguide(record: Mapping[str, Any], label: str) -> str:
    bioguide = str((record.get("id") or {}).get("bioguide") or "").strip()
    if len(bioguide) != 7 or not bioguide[0].isalpha() or not bioguide[1:].isdigit():
        raise ValueError(f"{label} has no BioGuide id")
    return bioguide.upper() if bioguide[0].islower() else bioguide


def person_facts(record: Mapping[str, Any], vintage: str) -> dict[str, Any]:
    """Biography, leadership, and name facts from one member-file entry."""
    bio = record.get("bio") or {}
    if bio and not isinstance(bio, dict):
        raise ValueError("bio is not a mapping")
    birthday = _date(bio["birthday"], "birthday") if bio.get("birthday") else None
    gender = None
    if bio.get("gender") is not None:
        gender = str(bio["gender"]).strip()
        if not gender:
            raise ValueError("bio.gender is blank")
    roles = []
    for index, role in enumerate(record.get("leadership_roles") or []):
        if not isinstance(role, dict):
            raise ValueError(f"leadership role #{index} is not a mapping")
        chamber = str(role.get("chamber") or "").strip()
        title = str(role.get("title") or "").strip()
        if chamber not in {"house", "senate"}:
            raise ValueError(f"leadership chamber must be house or senate, not {chamber!r}")
        if not title:
            raise ValueError("leadership role has no title")
        end = _date(role["end"], "leadership end") if role.get("end") else None
        roles.append(
            {
                "chamber": chamber,
                "title": title,
                "start": _date(role.get("start"), "leadership start"),
                "end": end,
            }
        )
    return {
        "birthday": birthday,
        "gender": gender,
        "leadership": roles,
        "names": _name_facts(record, vintage),
    }


def _name_facts(record: Mapping[str, Any], vintage: str) -> list[dict[str, Any]]:
    name = record.get("name") or {}
    if name and not isinstance(name, dict):
        raise ValueError("name is not a mapping")
    facts: list[dict[str, Any]] = []
    official = str(name.get("official_full") or "").strip()
    if official:
        facts.append(
            {
                "name_kind": "official",
                "full_name": official,
                "given_name": name.get("first"),
                "family_name": name.get("last"),
                "source_vintage": vintage,
            }
        )
    for kind, key in (("middle", "middle"), ("suffix", "suffix"), ("nickname", "nickname")):
        value = str(name.get(key) or "").strip()
        if value:
            facts.append(
                {
                    "name_kind": kind,
                    "full_name": value,
                    "given_name": None,
                    "family_name": None,
                    "source_vintage": vintage,
                }
            )
    seen: set[tuple[str, str]] = set()
    for index, other in enumerate(record.get("other_names") or []):
        if not isinstance(other, dict):
            raise ValueError(f"other name #{index} is not a mapping")
        last = str(other.get("last") or "").strip()
        if not last:
            raise ValueError("other name has no last name")
        middle = str(other.get("middle") or "").strip() or None
        end = _date(other["end"], "other name end").isoformat() if other.get("end") else vintage
        key = ("former", end)
        if key in seen:
            raise ValueError(f"two earlier names share the end date {end}")
        seen.add(key)
        facts.append(
            {
                "name_kind": "former",
                "full_name": " ".join(part for part in (middle, last) if part),
                "given_name": middle,
                "family_name": last,
                "source_vintage": end,
            }
        )
    return facts


def social_accounts(record: Mapping[str, Any]) -> list[dict[str, Any]]:
    """One row per network. The handle and the numeric id stay together."""
    entry_bioguide(record, "social record")
    social = record.get("social") or {}
    if not isinstance(social, dict):
        raise ValueError("social is not a mapping")
    unknown = sorted(set(social) - SOCIAL_KEYS)
    if unknown:
        raise ValueError(f"unknown social field: {', '.join(unknown)}")
    rows = []
    for network, handle_key, id_key in SOCIAL_PAIRS:
        handle = str(social.get(handle_key) or "").strip() or None
        external = str(social.get(id_key) or "").strip() or None if id_key else None
        if handle is None and external is None:
            continue
        rows.append({"network": network, "handle": handle, "external_id": external})
    return rows


def district_offices(record: Mapping[str, Any]) -> list[dict[str, Any]]:
    """One row per office. Coordinates are kept only as a pair."""
    entry_bioguide(record, "district office record")
    offices = record.get("offices") or []
    if not isinstance(offices, list):
        raise ValueError("offices is not a list")
    rows = []
    for index, office in enumerate(offices):
        if not isinstance(office, dict):
            raise ValueError(f"office #{index} is not a mapping")
        office_key = str(office.get("id") or "").strip()
        if not office_key:
            raise ValueError(f"office #{index} has no id")
        latitude = office.get("latitude")
        longitude = office.get("longitude")
        if (latitude is None) != (longitude is None):
            raise ValueError(f"office {office_key} has only one coordinate")
        rows.append(
            {
                "office_key": office_key,
                "address": _text(office.get("address")),
                "building": _text(office.get("building")),
                "suite": _text(office.get("suite")),
                "city": _text(office.get("city")),
                "state": _text(office.get("state")),
                "zip": _text(office.get("zip")),
                "phone": _text(office.get("phone")),
                "fax": _text(office.get("fax")),
                "hours": _text(office.get("hours")),
                "latitude": None if latitude is None else float(latitude),
                "longitude": None if longitude is None else float(longitude),
                "record": office,
            }
        )
    return rows


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def dump(record: Mapping[str, Any] | list[Any]) -> str:
    """Stable JSON for a safety copy."""
    return json.dumps(record, sort_keys=True, default=str)


def odd_genders(genders: Iterable[str | None]) -> list[str]:
    """Letters other than M and F. They are stored, and the run says so."""
    return sorted({gender for gender in genders if gender and gender not in {"M", "F"}})
