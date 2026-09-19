"""Story 9.5b: a BILLSTATUS record keeps every element path and value of its XML.

Real GovInfo files (``tests/fixtures/billstatus``, chosen by greedy set-cover over the 418
element paths in all 172,703 files) plus small synthetic cases for the shapes that
matter: singleton lists, namespaces, attributes, mixed text.
"""

from __future__ import annotations

import json
from pathlib import Path
from xml.etree import ElementTree

import pytest

from opendiscourse_research.ingestion.billstatus_record import (
    record_leaves,
    record_paths,
    record_problems,
    xml_leaves,
    xml_paths,
    xml_to_record,
)
from opendiscourse_research.repositories.legislation import parse_billstatus_xml

FIXTURES = Path(__file__).parent / "fixtures" / "billstatus"
FIXTURE_FILES = sorted(FIXTURES.glob("BILLSTATUS-*.xml"))


def _root(name: str) -> ElementTree.Element:
    return ElementTree.fromstring((FIXTURES / name).read_bytes())


def test_fixtures_are_present() -> None:
    assert len(FIXTURE_FILES) >= 14


@pytest.mark.parametrize("path", FIXTURE_FILES, ids=lambda p: p.name)
def test_record_captures_every_xml_path_and_value(path: Path) -> None:
    root = ElementTree.fromstring(path.read_bytes())
    record = xml_to_record(root)

    assert record_paths(record, root.tag) == xml_paths(root)
    assert record_leaves(record, root.tag) == xml_leaves(root)
    assert record_problems(root, record) == []


@pytest.mark.parametrize("path", FIXTURE_FILES, ids=lambda p: p.name)
def test_parse_exposes_the_record_of_the_whole_file(path: Path) -> None:
    data = parse_billstatus_xml(path.read_bytes(), member_name=path.name)
    root = ElementTree.fromstring(path.read_bytes())

    assert data["record"] == xml_to_record(root)
    json.dumps(data["record"])  # it must be storable as jsonb


def test_the_fixtures_reach_paths_the_old_parser_dropped() -> None:
    seen: set[str] = set()
    for path in FIXTURE_FILES:
        seen |= xml_paths(ElementTree.fromstring(path.read_bytes()))
    for needed in (
        "/billStatus/bill/summaries/summary/text",
        "/billStatus/bill/relatedBills/item/relationshipDetails/item/type",
        "/billStatus/bill/amendments/amendment/sponsors/item/bioguideId",
        "/billStatus/bill/laws/item/number",
        "/billStatus/bill/cboCostEstimates/item/url",
        "/billStatus/bill/committeeReports/committeeReport/citation",
        "/billStatus/bill/actions/item/recordedVotes/recordedVote/rollNumber",
        "/billStatus/bill/textVersions/item/formats/item/type",
    ):
        assert needed in seen, needed


# -- the encoding ---------------------------------------------------------------
def test_scalars_are_stripped_strings_and_singleton_lists_stay_lists() -> None:
    root = ElementTree.fromstring(
        "<billStatus><bill><title>\n   A title \n</title>"
        "<actions><item><text>one</text></item></actions>"
        "<summaries><summary><text>s</text></summary></summaries>"
        "<empty/></bill></billStatus>"
    )
    record = xml_to_record(root)

    assert record["bill"]["title"] == "A title"
    assert record["bill"]["actions"] == {"item": [{"text": "one"}]}
    assert record["bill"]["summaries"] == {"summary": [{"text": "s"}]}
    assert record["bill"]["empty"] == ""


def test_any_other_repeated_tag_becomes_a_list_and_keeps_every_value() -> None:
    root = ElementTree.fromstring(
        "<billStatus><bill><amendments><amendment><number>445</number><number>446</number>"
        "<congress>115</congress></amendment></amendments></bill></billStatus>"
    )
    record = xml_to_record(root)

    assert record["bill"]["amendments"]["amendment"] == [
        {"number": ["445", "446"], "congress": "115"}
    ]
    assert record_problems(root, record) == []


def test_namespaced_tags_use_a_prefix_and_unknown_namespaces_keep_clark_notation() -> None:
    root = ElementTree.fromstring(
        '<billStatus><dublinCore xmlns:dc="http://purl.org/dc/elements/1.1/" '
        'xmlns:x="http://example.test/x"><dc:rights>Public</dc:rights><x:other>o</x:other>'
        "</dublinCore></billStatus>"
    )
    record = xml_to_record(root)

    assert record["dublinCore"] == {"dc:rights": "Public", "{http://example.test/x}other": "o"}
    assert record_problems(root, record) == []


def test_attributes_and_text_beside_children_are_kept() -> None:
    root = ElementTree.fromstring(
        '<billStatus><bill kind="x"><note lang="en">hello</note><a>1</a>loose text</bill></billStatus>'
    )
    # ``loose text`` is a tail of <a>, which would be lost: refuse it.
    with pytest.raises(ValueError, match="tail"):
        xml_to_record(root)

    root = ElementTree.fromstring(
        '<billStatus><bill kind="x">lead<note lang="en">hello</note></bill></billStatus>'
    )
    record = xml_to_record(root)

    assert record["bill"] == {"@kind": "x", "#text": "lead", "note": {"@lang": "en", "#text": "hello"}}
    assert record_problems(root, record) == []


def test_a_record_missing_a_path_or_a_value_is_reported() -> None:
    root = ElementTree.fromstring(
        "<billStatus><bill><title>T</title><notes><item><text>n</text></item></notes></bill></billStatus>"
    )
    record = xml_to_record(root)
    del record["bill"]["notes"]
    record["bill"]["title"] = "changed"

    problems = record_problems(root, record)

    assert any("/billStatus/bill/notes" in p for p in problems)
    assert any("title" in p for p in problems)


# -- typed promotion from the parser ------------------------------------------------
def _parse(name: str) -> dict:
    return parse_billstatus_xml((FIXTURES / name).read_bytes(), member_name=name)


def _texts(root: ElementTree.Element, xpath: str) -> list[str | None]:
    return [e.text for e in root.findall(xpath)]


def test_summaries_are_promoted_with_their_html_text() -> None:
    name = "BILLSTATUS-108s1839.xml"
    root = _root(name)
    data = _parse(name)

    expected = root.findall("./bill/summaries/summary")
    assert expected, "fixture must hold summaries"
    assert len(data["summaries"]) == len(expected)
    first = data["summaries"][0]
    assert first["version_code"] == expected[0].findtext("versionCode").strip()
    assert first["action_description"] == expected[0].findtext("actionDesc").strip()
    assert first["action_date"] == expected[0].findtext("actionDate").strip()
    assert first["source_ordinal"] == 1 and first["source_member"] == name
    assert first["text"] and first["text"] == (
        expected[0].findtext("text") or expected[0].findtext("cdata/text")
    ).strip()
    assert [s["source_ordinal"] for s in data["summaries"]] == list(range(1, len(expected) + 1))


def test_summaries_in_the_alternate_spelling_are_promoted() -> None:
    name = "BILLSTATUS-113hr4200.xml"  # <billNumber>, <summaries><billSummaries><item>
    root = _root(name)
    data = _parse(name)

    expected = root.findall("./bill/summaries/billSummaries/item")
    assert expected
    assert [s["version_code"] for s in data["summaries"]] == [
        e.findtext("versionCode").strip() for e in expected
    ]


def test_laws_are_promoted() -> None:
    name = "BILLSTATUS-119s4138.xml"
    root = _root(name)
    data = _parse(name)

    expected = root.findall("./bill/laws/item")
    assert expected
    assert [(x["law_type"], x["law_number"]) for x in data["laws"]] == [
        (e.findtext("type").strip(), e.findtext("number").strip()) for e in expected
    ]


def test_related_bills_are_promoted_with_their_relationships() -> None:
    name = "BILLSTATUS-113hr4200.xml"
    root = _root(name)
    data = _parse(name)

    expected = root.findall("./bill/relatedBills/item")
    assert len(data["related_bills"]) == len(expected) == 2
    first = data["related_bills"][0]
    assert first["related_congress"] == 113
    assert first["related_bill_type"] == "hr"  # lower case, like core.bill.bill_type
    assert first["related_bill_number"] == "5405"
    assert first["title"] == "Promoting Job Creation and Reducing Small Business Burdens Act"
    assert first["latest_action_date"] == "2014-09-17"
    assert first["latest_action_text"].startswith("Received in the Senate")
    assert first["relationships"] == [{"type": "Related bill", "identified_by": "CRS"}]
    assert data["related_bills"][1]["relationships"][0]["type"] == "Identical bill"


def test_amendments_are_promoted_with_their_sponsor_by_bioguide_id() -> None:
    name = "BILLSTATUS-118s4640.xml"
    root = _root(name)
    data = _parse(name)

    expected = root.findall("./bill/amendments/amendment")
    assert expected
    assert len(data["amendments"]) == len(expected)
    first = data["amendments"][0]
    assert (first["amendment_congress"], first["amendment_type"], first["amendment_number"]) == (
        118,
        "SAMDT",
        "3350",
    )
    assert first["chamber"] == "Senate"
    assert first["purpose"] == "In the nature of substitute."
    assert first["sponsor_bioguide_id"] == "O000174"
    assert first["latest_action_date"] == "2024-12-19"
    assert first["latest_action_text"].startswith("Amendment SA 3350 agreed to")
    assert first["submitted_at"] == "2024-12-19T05:00:00Z"
    assert first["source_ordinal"] == 1


def test_an_amendment_that_repeats_its_scalars_promotes_the_first_and_the_record_keeps_all() -> None:
    xml = (
        "<billStatus><bill><congress>115</congress><type>HR</type><number>3354</number>"
        "<amendments><amendment><number>445</number><description>d</description>"
        "<congress>115</congress><type>HAMDT</type><number>445</number>"
        "<description>d</description><congress>115</congress><type>HAMDT</type>"
        "<chamber>House of Representatives</chamber></amendment></amendments></bill></billStatus>"
    )
    data = parse_billstatus_xml(xml, member_name="BILLSTATUS-115hr3354.xml")

    assert len(data["amendments"]) == 1
    assert data["amendments"][0]["amendment_number"] == "445"
    assert data["record"]["bill"]["amendments"]["amendment"][0]["number"] == ["445", "445"]


def test_a_bill_without_the_optional_sections_promotes_nothing() -> None:
    xml = "<billStatus><bill><congress>118</congress><type>HR</type><number>1</number></bill></billStatus>"
    data = parse_billstatus_xml(xml)

    assert data["summaries"] == data["laws"] == data["related_bills"] == data["amendments"] == []
    assert data["record"] == {"bill": {"congress": "118", "type": "HR", "number": "1"}}
