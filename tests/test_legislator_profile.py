"""Member profile parsing: biography, names, social accounts, and district offices."""

from opendiscourse_research.ingestion.legislator_profile import (
    contact_from_term,
    district_offices,
    odd_genders,
    person_facts,
    social_accounts,
)
from opendiscourse_research.ingestion.legislator_terms import parse_terms


def test_washington_contact_is_kept_off_the_term_metadata() -> None:
    term = parse_terms(
        [
            {
                "type": "sen",
                "start": "2021-01-03",
                "end": "2027-01-03",
                "state": "WA",
                "class": 1,
                "phone": "202-224-3441",
                "office": "311 Hart",
            }
        ]
    )[0]
    assert term.contact == {"phone": "202-224-3441", "office": "311 Hart"}
    assert "phone" not in term.metadata
    assert contact_from_term({"phone": "  "}) == {}


def test_nickname_is_a_name_fact_and_not_the_only_official_name() -> None:
    facts = person_facts(
        {
            "name": {"first": "Bernard", "last": "Sanders", "official_full": "Bernard Sanders", "nickname": "Bernie"},
            "other_names": [{"last": "Levy", "end": "1846-01-12"}],
            "bio": {"birthday": "1941-09-08", "gender": "M"},
        },
        "2026-09-03",
    )
    kinds = {fact["name_kind"]: fact for fact in facts["names"]}
    assert kinds["nickname"]["full_name"] == "Bernie"
    assert kinds["nickname"]["source_vintage"] == "2026-09-03"
    assert kinds["official"]["full_name"] == "Bernard Sanders"
    assert kinds["former"]["source_vintage"] == "1846-01-12"
    assert facts["birthday"].isoformat() == "1941-09-08"


def test_social_handle_and_id_stay_on_one_row() -> None:
    rows = social_accounts(
        {"id": {"bioguide": "R000600"}, "social": {"twitter": "RepAmata", "twitter_id": 3026622545}}
    )
    assert rows == [{"network": "twitter", "handle": "RepAmata", "external_id": "3026622545"}]


def test_a_new_social_field_is_refused() -> None:
    try:
        social_accounts({"id": {"bioguide": "R000600"}, "social": {"bluesky": "someone"}})
    except ValueError as exc:
        assert "bluesky" in str(exc)
    else:
        raise AssertionError("expected the new field to be refused")


def test_an_office_needs_both_coordinates() -> None:
    try:
        district_offices(
            {"id": {"bioguide": "A000055"}, "offices": [{"id": "A000055-cullman", "latitude": 34.1}]}
        )
    except ValueError as exc:
        assert "coordinate" in str(exc)
    else:
        raise AssertionError("expected a half coordinate pair to be refused")


def test_unexpected_gender_is_listed() -> None:
    assert odd_genders(["M", "F", "X", None, "M"]) == ["X"]
