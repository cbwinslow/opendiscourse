"""Legislator terms: parsing and the division/post rules that place a term (Story 3.3).

``unitedstates/congress-legislators`` lists every term of every member since 1789. A term
becomes one ``core.membership``; where it was served becomes a ``core.post`` on a
``core.division`` named by an Open Civic Data id. Only ids the OCD registry defines are
written: states, ``cd:N`` and ``cd:at-large`` (district 0), DC, the territories, and the
historical territories. A division id names a place, not a boundary: district geometry
differs by redistricting vintage and is not loaded here.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from .legislator_profile import contact_from_term

COUNTRY = "ocd-division/country:us"

STATES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California",
    "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware", "FL": "Florida", "GA": "Georgia",
    "HI": "Hawaii", "ID": "Idaho", "IL": "Illinois", "IN": "Indiana", "IA": "Iowa",
    "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
    "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi",
    "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada", "NH": "New Hampshire",
    "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York", "NC": "North Carolina",
    "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma", "OR": "Oregon", "PA": "Pennsylvania",
    "RI": "Rhode Island", "SC": "South Carolina", "SD": "South Dakota", "TN": "Tennessee",
    "TX": "Texas", "UT": "Utah", "VT": "Vermont", "VA": "Virginia", "WA": "Washington",
    "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming",
}

# code -> (ocd suffix after ``country:us/``, label, classification). The upstream file's own
# codes for the historical territories (DK, OL, PI) differ from the OCD ones (dt, ot, pi).
JURISDICTIONS = {
    "DC": ("district:dc", "District of Columbia", "district"),
    "PR": ("territory:pr", "Puerto Rico", "territory"),
    "GU": ("territory:gu", "Guam", "territory"),
    "VI": ("territory:vi", "US Virgin Islands", "territory"),
    "AS": ("territory:as", "American Samoa", "territory"),
    "MP": ("territory:mp", "Northern Mariana Islands", "territory"),
    "DK": ("territory:dt", "Dakota Territory", "territory"),
    "OL": ("territory:ot", "Orleans Territory", "territory"),
    "PI": ("territory:pi", "Philippine Islands", "territory"),
}

CHAMBERS = {"rep": "representative", "sen": "senator"}


def _date(value: Any, field_name: str) -> date:
    """A YAML date or ISO string; anything else is refused (never guessed)."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        raise ValueError(f"term {field_name} is not a date: {value!r}") from None


def _jsonable(value: Any) -> Any:
    """Dates become ISO text so the metadata is storable as jsonb."""
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_jsonable(v) for v in value]
    return value


@dataclass(frozen=True)
class Term:
    """One term of office as asserted by a source file."""

    chamber: str  # "rep" or "sen"
    start: date
    end: date
    state: str
    district: int | None = None
    senate_class: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict, hash=False)
    contact: dict[str, str] = field(default_factory=dict, hash=False)


def parse_terms(records: Iterable[dict[str, Any]] | None) -> tuple[Term, ...]:
    """Parse a legislator's ``terms`` list; malformed terms raise, they are never skipped."""
    terms: list[Term] = []
    for record in records or []:
        chamber = record.get("type")
        if chamber not in CHAMBERS:
            raise ValueError(f"term type must be 'rep' or 'sen', not {chamber!r}")
        if not record.get("start"):
            raise ValueError("term has no start date")
        if not record.get("end"):
            raise ValueError("term has no end date")
        state = str(record.get("state") or "").strip().upper()
        if not state:
            raise ValueError("term has no state")
        district = record.get("district")
        senate_class = record.get("class")
        meta: dict[str, Any] = {"state": state}
        if district is not None:
            meta["district"] = int(district)
        if record.get("party"):
            meta["party"] = record["party"]
        if senate_class is not None:
            meta["senate_class"] = int(senate_class)
        for source_key, key in (
            ("state_rank", "state_rank"),
            ("how", "how"),
            ("end-type", "end_type"),
            ("caucus", "caucus"),
            ("party_affiliations", "party_affiliations"),
        ):
            if record.get(source_key):
                meta[key] = _jsonable(record[source_key])
        terms.append(
            Term(
                chamber,
                _date(record["start"], "start"),
                _date(record["end"], "end"),
                state,
                None if district is None else int(district),
                None if senate_class is None else int(senate_class),
                meta,
                contact_from_term(record),
            )
        )
    return tuple(terms)


def _ordinal(number: int) -> str:
    suffix = "th" if 10 <= number % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(number % 10, "th")
    return f"{number}{suffix}"


@dataclass(frozen=True)
class TermPlan:
    """Where a term sits: its state or territory division and, if known, its post."""

    chamber: str
    role: str
    state_ocd: str
    state_label: str
    state_class: str
    post_ocd: str | None = None
    post_division_label: str | None = None
    post_division_class: str | None = None
    post_label: str | None = None
    post_role: str | None = None


def plan_term(term: Term) -> TermPlan | None:
    """Place a term, or return None for a jurisdiction code we cannot identify.

    A code outside the table is never guessed: the caller counts and reports it.
    """
    role = CHAMBERS[term.chamber]
    if term.state in JURISDICTIONS:
        suffix, label, kind = JURISDICTIONS[term.state]
        ocd = f"{COUNTRY}/{suffix}"
        # A delegate's or commissioner's district number carries no information: the
        # territory (or DC) is the post, whatever number an old record gave it.
        return TermPlan(
            term.chamber, role, ocd, label, kind, ocd, label, kind,
            f"Representative, {term.state}" if term.chamber == "rep" else "Senator", role,
        )
    name = STATES.get(term.state)
    if name is None:
        return None
    state_ocd = f"{COUNTRY}/state:{term.state.lower()}"
    plan = {"chamber": term.chamber, "role": role, "state_ocd": state_ocd, "state_label": name, "state_class": "state"}
    if term.chamber == "sen":
        klass = f", Class {term.senate_class}" if term.senate_class else ""
        return TermPlan(
            **plan, post_ocd=state_ocd, post_division_label=name, post_division_class="state",
            post_label=f"Senator{klass}", post_role=role,
        )
    district = term.district
    if district is None or district < 0:  # unknown district: keep the state, claim no post
        return TermPlan(**plan)
    if district == 0:
        return TermPlan(
            **plan, post_ocd=f"{state_ocd}/cd:at-large",
            post_division_label=f"{name}'s at-large congressional district", post_division_class="cd",
            post_label=f"Representative, {term.state}-AL", post_role=role,
        )
    return TermPlan(
        **plan, post_ocd=f"{state_ocd}/cd:{district}",
        post_division_label=f"{name}'s {_ordinal(district)} congressional district", post_division_class="cd",
        post_label=f"Representative, {term.state}-{district}", post_role=role,
    )
