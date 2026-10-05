"""Identifier-only links from OpenStates rows to owned rows."""

from __future__ import annotations

import pytest

from opendiscourse_research.openstateslink import (
    activation_rename_plan,
    assert_restore_target,
    candidate_database_name,
    federal_bill_key,
    link_federal_bills,
    link_people,
    link_votes,
)


def test_people_match_on_bioguide_and_ignore_names_and_other_schemes() -> None:
    links = link_people(
        [
            ("ocd-person/a", "bioguide", "A000001"),
            ("ocd-person/a", "twitter", "someone"),
            ("ocd-person/b", "full_name", "A000001"),
        ],
        {"A000001": "person-1"},
    )
    assert len(links) == 1
    assert links[0].person_id == "person-1"
    assert links[0].bioguide == "A000001"
    assert links[0].conflict is None


def test_people_do_not_match_a_missing_bioguide() -> None:
    links = link_people([("ocd-person/a", "bioguide", "Z000009")], {})
    assert links[0].person_id is None
    assert links[0].conflict is None


def test_one_bioguide_claimed_by_two_people_is_a_conflict() -> None:
    links = link_people(
        [
            ("ocd-person/a", "bioguide", "A000001"),
            ("ocd-person/b", "bioguide", "A000001"),
        ],
        {"A000001": "person-1"},
    )
    assert {link.person_id for link in links} == {None}
    assert {link.conflict for link in links} == {"bioguide_claimed_by_multiple_people"}


def test_two_bioguides_on_one_person_is_a_conflict() -> None:
    links = link_people(
        [
            ("ocd-person/a", "bioguide", "A000001"),
            ("ocd-person/a", "bioguide", "B000002"),
        ],
        {"A000001": "person-1", "B000002": "person-2"},
    )
    assert all(link.person_id is None for link in links)
    assert {link.conflict for link in links} == {"person_has_multiple_bioguide_ids"}


def test_state_bill_label_is_not_a_federal_key() -> None:
    assert federal_bill_key("2026", "HB 264") is None
    assert federal_bill_key("2026 Regular Session", "HR 1") is None


def test_federal_bill_key_normalizes_type_and_number() -> None:
    assert federal_bill_key("118", "HR 03164") == ("118", "hr", "3164")


def test_federal_bills_match_only_the_united_states_jurisdiction() -> None:
    owned = {("118", "hr", "1"): "bill-1"}
    links = link_federal_bills(
        [
            ("ocd-bill/us", "ocd-jurisdiction/country:us/government", "118", "HR 1"),
            ("ocd-bill/va", "ocd-jurisdiction/country:us/state:va/government", "2026", "HB 1"),
        ],
        owned,
    )
    assert len(links) == 1
    assert links[0].bill_id == "bill-1"


def test_unmatched_federal_bill_stays_unlinked() -> None:
    links = link_federal_bills(
        [("ocd-bill/us", "ocd-jurisdiction/country:us/government", "118", "S 9")],
        {},
    )
    assert links[0].bill_id is None


def test_several_openstates_vote_events_share_one_roll_call() -> None:
    links = link_votes(
        [
            ("ocd-vote/1", "us-2024-lower-123"),
            ("ocd-vote/2", "us-2024-lower-123"),
            ("ocd-vote/3", "not-a-roll"),
        ],
        {"us-2024-lower-123"},
    )
    assert len(links) == 1
    assert links[0].ocd_vote_ids == ("ocd-vote/1", "ocd-vote/2")
    assert links[0].matched is True


def test_vote_without_an_owned_roll_is_unmatched() -> None:
    links = link_votes([("ocd-vote/9", "us-2024-upper-4")], set())
    assert links[0].matched is False


def test_candidate_database_name_uses_the_checksum() -> None:
    name = candidate_database_name("2026-10", "a" * 64)
    assert name == "openstates_202610_" + ("a" * 12)


@pytest.mark.parametrize("database", ["openstates", "opendiscourse", "postgres", "warehouse"])
def test_restore_refuses_protected_database_names(database: str) -> None:
    with pytest.raises(ValueError, match="refusing"):
        assert_restore_target(database)


def test_activation_renames_the_candidate_only_after_the_previous_copy() -> None:
    steps = activation_rename_plan(candidate="openstates_202610_" + "ab" * 6, previous_label="unattested")
    assert steps[2].startswith("ALTER DATABASE openstates RENAME TO openstates_previous_unattested")
    assert steps[3] == "ALTER DATABASE openstates_202610_" + "ab" * 6 + " RENAME TO openstates"
    assert "dbname" not in " ".join(steps)
