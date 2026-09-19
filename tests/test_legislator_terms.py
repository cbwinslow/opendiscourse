"""Story 3.3: legislator terms -> divisions, posts and memberships (rules only, no DB)."""

from __future__ import annotations

from datetime import date

import pytest

from opendiscourse_research.ingestion.legislator_terms import (
    Term,
    parse_terms,
    plan_term,
)
from opendiscourse_research.ingestion.legislators import dedupe_identifiers, parse_legislators

STATE = "ocd-division/country:us"

YAML = """
- id: {bioguide: C000127}
  name: {first: Maria, last: Cantwell}
  terms:
  - {type: rep, start: 1993-01-05, end: 1995-01-03, state: WA, district: 1, party: Democrat}
  - {type: sen, start: '2025-01-03', end: '2031-01-03', state: WA, class: 1, party: Democrat, state_rank: junior}
- id: {bioguide: B000001}
  name: {first: Ann, last: Bee}
"""


def _term(**kw) -> Term:
    base = dict(chamber="rep", start=date(2019, 1, 3), end=date(2021, 1, 3), state="WA", district=7)
    return Term(**{**base, **kw})


def test_terms_are_parsed_with_dates_and_only_the_facts_that_are_present() -> None:
    cantwell, bee = parse_legislators(YAML)

    house, senate = cantwell.terms
    assert (house.chamber, house.state, house.district, house.senate_class) == ("rep", "WA", 1, None)
    assert house.start == date(1993, 1, 5) and house.end == date(1995, 1, 3)
    assert house.metadata == {"state": "WA", "district": 1, "party": "Democrat"}
    assert (senate.chamber, senate.senate_class) == ("sen", 1)
    assert senate.start == date(2025, 1, 3)  # a quoted date string is read the same way
    assert senate.metadata == {"state": "WA", "party": "Democrat", "senate_class": 1, "state_rank": "junior"}
    assert bee.terms == ()  # no terms key: no terms, not an error


def test_deduping_identifiers_keeps_the_terms() -> None:
    people = parse_legislators(YAML)
    kept, _ = dedupe_identifiers(people)
    assert [p.terms for p in kept] == [p.terms for p in people]


def test_a_term_without_a_date_or_chamber_is_refused() -> None:
    with pytest.raises(ValueError, match="start"):
        parse_terms([{"type": "rep", "end": "2021-01-03", "state": "WA", "district": 1}])
    with pytest.raises(ValueError, match="type"):
        parse_terms([{"type": "gov", "start": "2019-01-03", "end": "2021-01-03", "state": "WA"}])


def test_party_affiliations_and_extra_facts_are_kept_json_ready() -> None:
    (term,) = parse_terms(
        [
            {
                "type": "sen", "start": date(2001, 6, 6), "end": date(2007, 1, 3), "state": "VT", "class": 1,
                "how": "appointment", "end-type": "special-election", "caucus": "Democrat",
                "party_affiliations": [{"start": date(2001, 6, 6), "end": date(2007, 1, 3), "party": "Independent"}],
            }
        ]
    )
    assert term.metadata["how"] == "appointment" and term.metadata["end_type"] == "special-election"
    assert term.metadata["caucus"] == "Democrat"
    assert term.metadata["party_affiliations"] == [
        {"start": "2001-06-06", "end": "2007-01-03", "party": "Independent"}
    ]


# -- divisions and posts ------------------------------------------------------
def test_a_house_term_sits_on_its_congressional_district_within_the_state() -> None:
    plan = plan_term(_term())

    assert plan is not None
    assert (plan.state_ocd, plan.state_label, plan.state_class) == (f"{STATE}/state:wa", "Washington", "state")
    assert plan.post_ocd == f"{STATE}/state:wa/cd:7"
    assert plan.post_division_label == "Washington's 7th congressional district"
    assert plan.post_division_class == "cd"
    assert (plan.post_label, plan.post_role, plan.role) == ("Representative, WA-7", "representative", "representative")
    assert plan.chamber == "rep"


@pytest.mark.parametrize(
    ("district", "ordinal"), [(1, "1st"), (2, "2nd"), (3, "3rd"), (4, "4th"), (11, "11th"), (12, "12th"), (13, "13th"), (21, "21st"), (22, "22nd"), (52, "52nd")]
)
def test_district_labels_use_correct_ordinals(district: int, ordinal: str) -> None:
    plan = plan_term(_term(district=district))
    assert plan is not None and plan.post_division_label == f"Washington's {ordinal} congressional district"


def test_at_large_is_district_zero() -> None:
    plan = plan_term(_term(state="AK", district=0))

    assert plan is not None
    assert plan.post_ocd == f"{STATE}/state:ak/cd:at-large"
    assert plan.post_division_label == "Alaska's at-large congressional district"
    assert plan.post_label == "Representative, AK-AL"


def test_a_senate_term_sits_on_the_state_by_class() -> None:
    plan = plan_term(_term(chamber="sen", district=None, senate_class=3))

    assert plan is not None
    assert plan.post_ocd == plan.state_ocd == f"{STATE}/state:wa"
    assert (plan.post_label, plan.post_role, plan.role, plan.chamber) == (
        "Senator, Class 3", "senator", "senator", "sen",
    )


def test_a_senate_term_without_a_class_is_still_placed_on_the_state() -> None:
    plan = plan_term(_term(chamber="sen", district=None, senate_class=None))
    assert plan is not None and plan.post_label == "Senator" and plan.post_ocd == f"{STATE}/state:wa"


@pytest.mark.parametrize(
    ("code", "ocd", "label", "kind"),
    [
        ("DC", f"{STATE}/district:dc", "District of Columbia", "district"),
        ("PR", f"{STATE}/territory:pr", "Puerto Rico", "territory"),
        ("GU", f"{STATE}/territory:gu", "Guam", "territory"),
        ("VI", f"{STATE}/territory:vi", "US Virgin Islands", "territory"),
        ("AS", f"{STATE}/territory:as", "American Samoa", "territory"),
        ("MP", f"{STATE}/territory:mp", "Northern Mariana Islands", "territory"),
        ("DK", f"{STATE}/territory:dt", "Dakota Territory", "territory"),
        ("OL", f"{STATE}/territory:ot", "Orleans Territory", "territory"),
        ("PI", f"{STATE}/territory:pi", "Philippine Islands", "territory"),
    ],
)
def test_delegates_and_territories_sit_on_their_own_division(code: str, ocd: str, label: str, kind: str) -> None:
    plan = plan_term(_term(state=code, district=0 if kind != "territory" or code in {"PR", "GU"} else -1))

    assert plan is not None
    assert (plan.state_ocd, plan.state_label, plan.state_class) == (ocd, label, kind)
    assert plan.post_ocd == ocd and plan.post_division_class == kind
    assert plan.post_label == f"Representative, {code}"


def test_an_unknown_district_gets_no_post_but_keeps_its_state() -> None:
    plan = plan_term(_term(district=-1))

    assert plan is not None
    assert plan.post_ocd is None and plan.post_label is None
    assert plan.state_ocd == f"{STATE}/state:wa"


def test_an_unknown_jurisdiction_code_is_not_guessed() -> None:
    assert plan_term(_term(state="ZZ")) is None


def test_all_fifty_states_have_a_name_and_a_lower_case_id() -> None:
    codes = "AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY".split()
    assert len(codes) == 50
    for code in codes:
        plan = plan_term(_term(state=code, district=1))
        assert plan is not None and plan.state_ocd == f"{STATE}/state:{code.lower()}", code
        assert plan.state_label and plan.state_label != code
