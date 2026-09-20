"""Story 11.2: the Senate roll-call XML parser, on real files from four eras and the odd ones.

Fixtures are unmodified senate.gov files (see ``tests/fixtures/senate_votes``): a 2003 nomination whose
``modify_date`` was set in 2010, a 2005 vote in the older shape (no ``modify_date``, no
``document_congress``, two amendment levels), a 2010 treaty amendment (empty document block), two
January-February 2021 rolls (an objection to the electoral count with no ``<document>``, and a
budget resolution decided by the Vice President), the impeachment trial (Guilty and Not Guilty) and
2025 roll 100 (``document_congress``, ``modify_date`` and the third amendment level).
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
from opendiscourse_research.ingestion.senate_vote_parse import (
    normalize_position,
    normalize_result,
    parse_senate_vote,
)

FIXTURES = Path(__file__).parent / "fixtures" / "senate_votes"
ALL = sorted(FIXTURES.glob("*.xml"))


def _parse(name: str):
    return parse_senate_vote((FIXTURES / name).read_bytes())


def _doc(members: str = "", extra: str = "", date_text: str = "April 19, 2005,  02:51 PM") -> bytes:
    return f"""<?xml version="1.0" encoding="UTF-8"?><roll_call_vote>
<congress>109</congress><session>1</session><congress_year>2005</congress_year><vote_number>7</vote_number>
<vote_date>{date_text}</vote_date>{extra}<count><yeas>1</yeas><nays/><present/><absent/></count>
<members>{members}</members></roll_call_vote>""".encode()


def _member(lis: str | None = "S001", cast: str = "Yea", name: str = "Smith (D-XX)") -> str:
    tag = f"<lis_member_id>{lis}</lis_member_id>" if lis is not None else "<lis_member_id/>"
    return (
        f"<member><member_full>{name}</member_full><last_name>Smith</last_name><first_name>Ann</first_name>"
        f"<party>D</party><state>XX</state><vote_cast>{cast}</vote_cast>{tag}</member>"
    )


def test_there_are_fixtures_from_every_era() -> None:
    names = " ".join(p.name for p in ALL)
    for year in ("2003", "2005", "2010", "2021", "2025"):
        assert year in names


@pytest.mark.parametrize("path", ALL, ids=lambda p: p.name)
def test_the_record_holds_every_element_attribute_and_value(path: Path) -> None:
    data = path.read_bytes()
    parsed = parse_senate_vote(data)
    root = ElementTree.fromstring(data)
    assert record_problems(root, parsed.record) == []
    assert record_paths(parsed.record, root.tag) == xml_paths(root)
    assert isinstance(parsed.record["members"]["member"], list)  # a list whatever the count
    assert len(parsed.record["members"]["member"]) == len(parsed.votes)


@pytest.mark.parametrize("path", ALL, ids=lambda p: p.name)
def test_every_senator_is_typed_with_the_lis_id_and_printed_details(path: Path) -> None:
    parsed = parse_senate_vote(path.read_bytes())
    roll = parsed.roll
    # the file lists every senator serving that day (99 on 6 January 2021), and its counts add up to them
    assert len(parsed.votes) == sum(roll[k] for k in ("yea_total", "nay_total", "present_total", "not_voting_total"))
    for vote in parsed.votes:
        assert vote["lis_member_id"] and vote["party"] and vote["state"] and vote["name"]
        assert vote["last_name"] and vote["first_name"] and vote["position_raw"]
        assert vote["position"] in {"yes", "no", "not voting", "other"}
    counts = roll
    assert counts["yea_total"] == sum(v["position_raw"] in {"Yea", "Guilty"} for v in parsed.votes)
    assert counts["nay_total"] == sum(v["position_raw"] in {"Nay", "Not Guilty"} for v in parsed.votes)
    assert parsed.party_totals == []  # the Senate file has none


def test_2005_roll_100_is_the_older_shape() -> None:
    parsed = _parse("2005-roll100.xml")
    roll = parsed.roll
    assert (roll["congress"], roll["roll_number"], roll["roll_year"], roll["congress_session"]) == (109, 100, 2005, "1st")
    assert roll["question"] == "On the Motion"
    assert roll["vote_question_text"] == "On the Motion (Motion to Recess, As Modified)"
    assert roll["vote_title"] == "Motion to Recess, As Modified"
    assert roll["vote_result"] == "Motion Agreed to" and roll["result"] == "pass"
    assert roll["vote_result_text"] == "Motion Agreed to (56-42)"
    assert roll["majority_requirement"] == "1/2"
    assert roll["action_date"] == date(2005, 4, 19) and roll["action_time_etz"] == "14:51"
    assert roll["occurred_at"] == datetime(2005, 4, 19, 18, 51, tzinfo=UTC)  # EDT is UTC-4
    assert roll["modified_at"] is None  # not in the older files
    assert (roll["document_type"], roll["document_number"], roll["document_name"]) == ("H.R.", "1268", "H.R. 1268")
    assert roll["document_congress"] is None  # not stated: kept NULL, not guessed
    assert roll["document_short_title"].startswith("Emergency Supplemental Appropriations Act")
    assert roll["amendment_number"] is None and roll["amendment_purpose"] == "No Statement of Purpose on File."
    assert roll["amendment_to_amendment_to_amendment_number"] is None
    assert (roll["yea_total"], roll["nay_total"], roll["present_total"], roll["not_voting_total"]) == (56, 42, 0, 2)
    assert (roll["tie_breaker_by"], roll["tie_breaker_vote"]) == (None, None)
    # the bill is the roll call's own Congress's when the older file does not say
    assert (roll["link_congress"], roll["link_bill_type"], roll["link_bill_number"]) == (109, "hr", "1268")
    assert parsed.votes[0] == {
        "lis_member_id": "S213",
        "name": "Akaka (D-HI)",
        "last_name": "Akaka",
        "first_name": "Daniel",
        "party": "D",
        "state": "HI",
        "position_raw": "Nay",
        "position": "no",
    }
    assert parsed.notes == ()


def test_2025_roll_100_has_the_newer_fields() -> None:
    roll = _parse("2025-roll100.xml").roll
    assert roll["document_congress"] == 119 and roll["document_type"] == "S." and roll["document_number"] == "9"
    assert roll["modified_at"] == datetime(2025, 3, 6, 20, 13, tzinfo=UTC)  # 03:13 PM EST
    assert roll["occurred_at"] == datetime(2025, 3, 3, 23, 27, tzinfo=UTC)  # 06:27 PM EST
    assert roll["majority_requirement"] == "3/5" and roll["result"] == "fail"
    assert roll["vote_result"] == "Cloture on the Motion to Proceed Rejected"
    assert (roll["yea_total"], roll["nay_total"], roll["not_voting_total"]) == (51, 45, 4)
    assert (roll["link_congress"], roll["link_bill_type"], roll["link_bill_number"]) == (119, "s", "9")
    assert roll["amendment_to_amendment_to_amendment_number"] is None  # present in the file, empty


def test_a_nomination_keeps_its_document_and_links_to_no_bill() -> None:
    roll = _parse("2003-roll038-nomination.xml").roll
    assert (roll["document_type"], roll["document_number"], roll["document_name"]) == ("PN", "35", "PN35")
    assert roll["document_congress"] == 108 and roll["document_title"].startswith("Marian Blank Horn")
    assert roll["question"] == "On the Nomination" and roll["vote_result"] == "Nomination Confirmed"
    assert roll["result"] == "pass"
    assert roll["modified_at"] == datetime(2010, 1, 7, 20, 25, tzinfo=UTC)
    assert (roll["link_congress"], roll["link_bill_type"], roll["link_bill_number"]) == (None, None, None)


def test_a_treaty_amendment_keeps_the_amendment_block_as_the_file_gives_it() -> None:
    roll = _parse("2010-roll295-treaty-amendment.xml").roll
    assert roll["document_type"] is None and roll["document_number"] is None  # the block is empty
    assert roll["document_congress"] == 111
    assert roll["amendment_number"] == "S.Amdt. 4895"
    assert roll["amendment_to_document_number"] == "Treaty Doc. 111-5"
    assert roll["amendment_purpose"].startswith("To provide an understanding")
    assert roll["vote_result"] == "Amendment Rejected" and roll["result"] == "fail"
    assert (roll["link_bill_type"], roll["link_bill_number"]) == (None, None)


def test_the_vice_president_tie_break_is_typed_on_the_roll_call_and_is_not_a_member() -> None:
    parsed = _parse("2021-roll054-tie-breaker.xml")
    roll = parsed.roll
    assert (roll["tie_breaker_by"], roll["tie_breaker_vote"]) == ("Vice President of the United States", "Yea")
    assert (roll["yea_total"], roll["nay_total"]) == (50, 50)
    assert len(parsed.votes) == 100 and all(v["lis_member_id"] for v in parsed.votes)
    assert not any("Vice President" in (v["name"] or "") for v in parsed.votes)
    assert parsed.record["tie_breaker"] == {"by_whom": "Vice President of the United States", "tie_breaker_vote": "Yea"}
    assert roll["document_type"] == "S.Con.Res." and roll["link_bill_type"] == "sconres"


def test_impeachment_words_stay_as_stated_and_normalize_to_other() -> None:
    parsed = _parse("2021-roll059-impeachment.xml")
    words = {v["position_raw"]: v["position"] for v in parsed.votes}
    assert words == {"Guilty": "other", "Not Guilty": "other"}
    roll = parsed.roll
    assert roll["vote_result"] == "Not Guilty" and roll["result"] is None
    assert "result_not_normalized" in parsed.notes
    assert roll["majority_requirement"] == "2/3" and (roll["yea_total"], roll["nay_total"]) == (57, 43)
    assert roll["document_type"] == "H.Res." and roll["link_bill_type"] == "hres"


def test_a_roll_call_with_no_document_block_loads_with_empty_document_columns() -> None:
    parsed = _parse("2021-roll001-objection-no-document.xml")
    roll = parsed.roll
    assert roll["document_type"] is None and roll["document_congress"] is None and roll["amendment_number"] is None
    assert roll["vote_question_text"].startswith("On the Objection (Shall the Objection Submitted")
    assert roll["question"] == "On the Objection" and roll["vote_result"] == "Objection Not Sustained"
    assert roll["result"] is None  # "Not Sustained" is not a plain pass or fail
    assert "document" not in parsed.record  # the record does not invent it


def test_a_member_with_no_lis_id_is_typed_with_none_never_a_guess() -> None:
    parsed = parse_senate_vote(_doc(_member(None) + _member("S002", "Nay")))
    assert [v["lis_member_id"] for v in parsed.votes] == [None, "S002"]
    assert parsed.votes[0]["name"] == "Smith (D-XX)"


def test_empty_counts_are_zero_and_an_absent_count_block_is_none() -> None:
    parsed = parse_senate_vote(_doc(_member()))
    roll = parsed.roll
    assert (roll["yea_total"], roll["nay_total"], roll["present_total"], roll["not_voting_total"]) == (1, 0, 0, 0)
    bare = parse_senate_vote(_doc(_member()).replace(b"<count><yeas>1</yeas><nays/><present/><absent/></count>", b""))
    assert bare.roll["yea_total"] is None and bare.roll["not_voting_total"] is None


def test_a_single_member_is_still_a_list_in_the_record() -> None:
    parsed = parse_senate_vote(_doc(_member()))
    assert isinstance(parsed.record["members"]["member"], list) and len(parsed.record["members"]["member"]) == 1


def test_an_unusable_modify_date_is_noted_and_an_unusable_vote_date_is_an_error() -> None:
    parsed = parse_senate_vote(_doc(_member(), "<modify_date>sometime</modify_date>"))
    assert parsed.roll["modified_at"] is None and "modified_unusable" in parsed.notes
    with pytest.raises(ValueError, match="vote_date"):
        parse_senate_vote(_doc(_member(), date_text="the other day"))


def test_a_file_that_is_not_a_roll_call_is_refused() -> None:
    with pytest.raises(ValueError, match="roll_call_vote"):
        parse_senate_vote(b"<vote_summary><congress>1</congress></vote_summary>")
    with pytest.raises(ValueError, match="required"):
        parse_senate_vote(b"<roll_call_vote><congress>1</congress></roll_call_vote>")
    with pytest.raises(ElementTree.ParseError):
        parse_senate_vote(b"<roll_call_vote>")


def test_text_after_a_child_cannot_be_recorded_so_the_file_is_refused() -> None:
    bad = _doc(_member()).replace(b"<count>", b"stray text<count>")
    with pytest.raises(ValueError, match="tail"):
        parse_senate_vote(bad)


@pytest.mark.parametrize(
    ("word", "expected"),
    [("Yea", "yes"), ("YEA", "yes"), ("Nay", "no"), ("Not Voting", "not voting"), ("Present", "other"),
     ("Guilty", "other"), ("Not Guilty", "other"), ("", "other")],
)
def test_position_normalization(word: str, expected: str) -> None:
    assert normalize_position(word) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Motion Agreed to", "pass"),
        ("Nomination Confirmed", "pass"),
        ("Bill Passed", "pass"),
        ("Cloture on the Motion to Proceed Rejected", "fail"),
        ("Motion Rejected", "fail"),
        ("Amendment Not Agreed to", "fail"),
        ("Motion Not Agreed to", "fail"),
        ("Nomination Not Confirmed", "fail"),
        ("Amendment Not Adopted", "fail"),
        ("Amendment Adopted", "pass"),
        ("Bill Not Passed", "fail"),
        ("Joint Resolution Passed", "pass"),
        ("Motion  to Table\nAgreed to", "pass"),
        ("Amendment Rejected", "fail"),
        ("Cloture Motion Failed", "fail"),
        ("Point of Order Well Taken", None),
        ("Point of Order Not Well Taken", None),
        ("Decision of Chair Not Sustained", None),
        ("Guilty", None),
        ("Objection Not Sustained", None),
        ("Veto Sustained", None),
        ("Not Guilty", None),
        ("", None),
        (None, None),
    ],
)
def test_result_normalization_keeps_only_plain_outcomes(text: str | None, expected: str | None) -> None:
    assert normalize_result(text) == expected
