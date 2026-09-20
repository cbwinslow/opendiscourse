"""Story 11.1: the House Clerk XML parser, on real files from four eras and the odd ones.

Fixtures are unmodified Clerk files (see ``tests/fixtures/house_votes``): a 2003 quorum call, a 2005
recorded vote, a 2007 Speaker election (UTF-8 byte-order mark, candidate tallies), a 2007 roll that
names the chamber in ``<committee>`` and carries an amendment, a 2015 vote and the 2024 roll 28 that
the OpenStates row ``us-2024-lower-28`` matches.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path
from xml.etree import ElementTree

import pytest

from opendiscourse_research.ingestion.billstatus_record import (
    record_paths,
    record_problems,
    xml_paths,
)
from opendiscourse_research.ingestion.house_vote_parse import (
    HOUSE_LIST_TAGS,
    normalize_position,
    normalize_result,
    parse_house_vote,
)

FIXTURES = Path(__file__).parent / "fixtures" / "house_votes"
ALL = sorted(FIXTURES.glob("*.xml"))


def _parse(name: str):
    return parse_house_vote((FIXTURES / name).read_bytes())


def _doc(votes: str = "", metadata: str = "", totals: str = "") -> bytes:
    return f"""<?xml version="1.0"?>
<rollcall-vote><vote-metadata><congress>108</congress><rollcall-num>7</rollcall-num>{metadata}{totals}</vote-metadata>
<vote-data>{votes}</vote-data></rollcall-vote>""".encode()


def test_there_are_fixtures_from_every_era() -> None:
    names = " ".join(p.name for p in ALL)
    for year in ("2003", "2005", "2007", "2015", "2024"):
        assert year in names


@pytest.mark.parametrize("path", ALL, ids=lambda p: p.name)
def test_the_record_holds_every_element_attribute_and_value(path: Path) -> None:
    data = path.read_bytes()
    parsed = parse_house_vote(data)
    root = ElementTree.fromstring(data)
    assert record_problems(root, parsed.record) == []
    assert record_paths(parsed.record, root.tag) == xml_paths(root)
    # the roll-call lists keep their shape whatever the count
    assert isinstance(parsed.record["vote-data"]["recorded-vote"], list)
    assert len(parsed.record["vote-data"]["recorded-vote"]) == len(parsed.votes)


@pytest.mark.parametrize("path", ALL, ids=lambda p: p.name)
def test_every_recorded_vote_is_typed_with_its_bioguide_id_and_printed_details(path: Path) -> None:
    parsed = parse_house_vote(path.read_bytes())
    assert parsed.votes
    for vote in parsed.votes:
        assert vote["bioguide_id"] and vote["party"] and vote["state"] and vote["name"]
        assert vote["position_raw"]
        assert vote["position"] in {"yes", "no", "not voting", "other"}


def test_2005_roll_100_header_totals_and_first_vote() -> None:
    parsed = _parse("2005-roll100.xml")
    roll = parsed.roll
    assert (roll["congress"], roll["roll_number"], roll["congress_session"]) == (109, 100, "1st")
    assert roll["legislative_number"] == "H RES 202"
    assert roll["question"] == "On Ordering the Previous Question"
    assert (roll["vote_type"], roll["vote_result"], roll["majority_party"]) == ("YEA-AND-NAY", "Passed", "R")
    assert roll["result"] == "pass"
    assert roll["chamber_label"] == "U.S. House of Representatives"
    assert roll["vote_description"].startswith("Providing for consideration of the bill (H.R. 8)")
    assert roll["action_date"] == date(2005, 4, 13)
    assert roll["action_time_etz"] == "14:18"
    assert roll["occurred_at"] == datetime(2005, 4, 13, 18, 18, tzinfo=UTC)  # EDT is UTC-4
    assert (roll["yea_total"], roll["nay_total"], roll["present_total"], roll["not_voting_total"]) == (237, 195, 0, 2)
    assert {p["party"]: p["yea_total"] for p in parsed.party_totals} == {
        "Republican": 230,
        "Democratic": 7,
        "Independent": 0,
    }
    first = parsed.votes[0]
    assert first == {
        "bioguide_id": "A000014",
        "name": "Abercrombie",
        "sort_name": "Abercrombie",
        "unaccented_name": "Abercrombie",
        "party": "D",
        "state": "HI",
        "role": "legislator",
        "position_raw": "Nay",
        "position": "no",
    }
    assert parsed.record["vote-metadata"]["action-time"] == {"@time-etz": "14:18", "#text": "2:18 PM"}


def test_2024_roll_28_matches_the_openstates_row_it_enriches() -> None:
    roll = _parse("2024-roll028.xml").roll
    # us-2024-lower-28 in the warehouse: 2024-01-31 21:47 UTC, "On Passage", "pass" (checked live 2026-09-20)
    assert roll["occurred_at"] == datetime(2024, 1, 31, 21, 47, tzinfo=UTC)
    assert (roll["question"], roll["result"], roll["roll_number"]) == ("On Passage", "pass", 28)
    assert (roll["yea_total"], roll["nay_total"], roll["present_total"]) == (422, 2, 1)


def test_2015_fixture_positions_use_yea_nay_and_aye_no_normalization() -> None:
    parsed = _parse("2015-roll705.xml")
    by_word = {v["position_raw"]: v["position"] for v in parsed.votes}
    assert by_word.keys() <= {"Yea", "Nay", "Aye", "No", "Present", "Not Voting"}
    assert {by_word[w] for w in ("Yea", "Aye") if w in by_word} == {"yes"}
    assert {by_word[w] for w in ("Nay", "No") if w in by_word} == {"no"}
    assert parsed.roll["yea_total"] == sum(v["position"] == "yes" for v in parsed.votes)
    assert parsed.roll["nay_total"] == sum(v["position"] == "no" for v in parsed.votes)


def test_quorum_call_has_present_positions_and_no_amendment() -> None:
    parsed = _parse("2003-roll001-quorum.xml")
    assert parsed.roll["legislative_number"] == "QUORUM" and parsed.roll["vote_type"] == "QUORUM"
    assert parsed.roll["vote_description"] is None  # <vote-desc></vote-desc>
    assert parsed.record["vote-metadata"]["vote-desc"] == ""
    assert {v["position_raw"] for v in parsed.votes} <= {"Present", "Not Voting"}
    assert {v["position"] for v in parsed.votes} <= {"other", "not voting"}
    assert parsed.roll["amendment_number"] is None


def test_speaker_election_keeps_candidate_names_and_tallies() -> None:
    parsed = _parse("2007-roll002-speaker-election.xml")  # the file begins with a byte-order mark
    assert parsed.roll["question"] == "Election of the Speaker"
    assert parsed.roll["vote_result"] == "Pelosi" and parsed.roll["result"] is None
    assert parsed.roll["yea_total"] is None  # elections tally candidates, not yeas
    assert parsed.party_totals == []
    candidates = parsed.record["vote-metadata"]["vote-totals"]["totals-by-candidate"]
    assert {c["candidate"]: c["candidate-total"] for c in candidates}["Pelosi"] == "233"
    words = {v["position_raw"] for v in parsed.votes}
    assert {"Pelosi", "Boehner"} <= words
    assert {v["position"] for v in parsed.votes if v["position_raw"] in {"Pelosi", "Boehner"}} == {"other"}
    speakers = [v for v in parsed.votes if v["role"] == "speaker"]
    assert speakers == []  # the Speaker-elect casts no vote in the election itself


def test_committee_element_names_the_chamber_and_amendment_fields_are_typed() -> None:
    roll = _parse("2007-roll455-committee-amendment.xml").roll
    assert roll["chamber_label"] == "U.S. House of Representatives"
    assert roll["amendment_number"] == "4"
    assert roll["amendment_author"] == "Reichert of Washington Amendment"
    assert roll["legislative_number"] == "H R 2638"


def test_the_speaker_is_typed_like_any_member_and_keeps_the_role() -> None:
    parsed = _parse("2015-roll705.xml")
    speaker = next(v for v in parsed.votes if v["role"] == "speaker")
    assert speaker["bioguide_id"] == "R000570" and speaker["party"] == "R" and speaker["state"] == "WI"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Yea", "yes"), ("Aye", "yes"), (" yea ", "yes"), ("Nay", "no"), ("No", "no"),
        ("Not Voting", "not voting"), ("Present", "other"), ("Jeffries", "other"), ("", "other"),
    ],
)
def test_position_normalization(raw: str, expected: str) -> None:
    assert normalize_position(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Passed", "pass"), ("Agreed to", "pass"), ("Failed", "fail"), ("Rejected", "fail"),
        ("Pelosi", None), ("", None), (None, None),
    ],
)
def test_result_normalization(raw: str | None, expected: str | None) -> None:
    assert normalize_result(raw) == expected


def test_a_single_recorded_vote_is_still_a_list() -> None:
    one = _doc(
        '<recorded-vote><legislator name-id="A000001" sort-field="A" unaccented-name="A" party="D" state="HI"'
        ' role="legislator">A</legislator><vote>Yea</vote></recorded-vote>'
    )
    parsed = parse_house_vote(one)
    assert isinstance(parsed.record["vote-data"]["recorded-vote"], list)
    assert HOUSE_LIST_TAGS >= {"recorded-vote", "totals-by-party", "totals-by-candidate"}
    assert len(parsed.votes) == 1


def test_an_entry_without_a_name_id_is_typed_with_no_bioguide_id() -> None:
    parsed = parse_house_vote(
        _doc('<recorded-vote><legislator party="D" state="HI" role="legislator">Anon</legislator><vote>Nay</vote></recorded-vote>')
    )
    assert parsed.votes[0]["bioguide_id"] is None and parsed.votes[0]["name"] == "Anon"


def test_missing_time_leaves_occurred_at_unknown_but_keeps_the_date() -> None:
    parsed = parse_house_vote(_doc(metadata="<action-date>4-Jan-2007</action-date>"))
    assert parsed.roll["action_date"] == date(2007, 1, 4) and parsed.roll["occurred_at"] is None


@pytest.mark.parametrize(
    "data",
    [
        b"<rollcall-vote><vote-data/></rollcall-vote>",  # no metadata
        b"<something-else><vote-metadata/></something-else>",  # wrong root
        _doc(metadata="<action-date>31-Foo-2007</action-date>"),
        _doc(totals="<vote-totals><totals-by-vote><yea-total>many</yea-total></totals-by-vote></vote-totals>"),
        b"<rollcall-vote><vote-metadata><congress>108</congress></vote-metadata></rollcall-vote>",  # no roll number
    ],
)
def test_unusable_files_raise_instead_of_loading_short(data: bytes) -> None:
    with pytest.raises(ValueError):
        parse_house_vote(data)


def test_a_file_that_is_not_xml_raises_a_parse_error() -> None:
    with pytest.raises(ElementTree.ParseError):
        parse_house_vote(b"<html><body>Request Rejected")


def test_text_after_a_child_element_cannot_be_recorded_and_raises() -> None:
    with pytest.raises(ValueError, match="tail"):
        parse_house_vote(_doc(metadata="<majority>R</majority>stray text"))


CONTAINERS = {"rollcall-vote", "vote-metadata", "vote-totals", "vote-data", "recorded-vote", "totals-by-party-header"}


def test_the_field_checklist_names_every_element_and_attribute_of_every_fixture() -> None:
    import yaml

    checklist = yaml.safe_load((FIXTURES.parents[2] / "inventory" / "fields" / "congress.house_votes.yaml").read_text())
    text = " ".join(f"{f['name']} {f.get('where') or ''}" for f in checklist["fields"])
    unnamed = set()
    for path in ALL:
        for xml_path in xml_paths(ElementTree.fromstring(path.read_bytes())):
            leaf = xml_path.rsplit("/", 1)[-1].lstrip("@")
            if leaf not in CONTAINERS and leaf not in text:
                unnamed.add(xml_path)
    assert not unnamed, f"add these to inventory/fields/congress.house_votes.yaml: {sorted(unnamed)}"


def test_a_clean_file_has_no_notes_and_a_malformed_time_or_odd_result_is_noted_but_loads() -> None:
    assert _parse("2005-roll100.xml").notes == ()
    bad_time = parse_house_vote(
        _doc(metadata='<action-date>4-Jan-2007</action-date><action-time time-etz="noon">x</action-time>')
    )
    assert bad_time.roll["occurred_at"] is None and bad_time.roll["action_date"] == date(2007, 1, 4)
    assert bad_time.notes == ("time_unusable",)
    odd = parse_house_vote(_doc(metadata="<vote-result>Tabled indefinitely</vote-result>"))
    assert odd.roll["vote_result"] == "Tabled indefinitely" and odd.roll["result"] is None
    assert odd.notes == ("result_not_normalized",)
    both = parse_house_vote(
        _doc(
            metadata='<action-date>4-Jan-2007</action-date><action-time time-etz="25:99">x</action-time>'
            "<vote-result>Pelosi</vote-result>"
        )
    )
    assert both.notes == ("time_unusable", "result_not_normalized")
    assert _parse("2007-roll002-speaker-election.xml").notes == ("result_not_normalized",)
