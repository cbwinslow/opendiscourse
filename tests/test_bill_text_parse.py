"""Story 11.3: BILLS XML parses across types and versions and the record is lossless."""

from __future__ import annotations

from pathlib import Path
from xml.etree import ElementTree

import pytest

from opendiscourse_research.ingestion.bill_text_parse import (
    parse_bills_xml,
    parse_xml_without_dtd,
)
from opendiscourse_research.ingestion.billstatus_record import (
    record_problems,
    xml_leaves,
    xml_to_record,
)
from opendiscourse_research.providers.govinfo import bills_member_identity

FIXTURES = Path(__file__).parent / "fixtures" / "bills"
FIXTURE_FILES = sorted(FIXTURES.glob("BILLS-*.xml"))


def test_fixtures_cover_types_and_versions() -> None:
    names = {p.name for p in FIXTURE_FILES}
    assert "BILLS-119hr23ih.xml" in names
    assert "BILLS-119hr23eh.xml" in names
    assert "BILLS-119hr23rh.xml" in names
    assert "BILLS-119hres1eh.xml" in names
    assert "BILLS-119s1pcs.xml" in names


@pytest.mark.parametrize("path", FIXTURE_FILES, ids=lambda p: p.name)
def test_record_captures_every_xml_path_and_value(path: Path) -> None:
    root = parse_xml_without_dtd(path.read_bytes())
    parsed = parse_bills_xml(path.read_bytes(), path.name)
    assert record_problems(root, parsed.record) == []


@pytest.mark.parametrize("path", FIXTURE_FILES, ids=lambda p: p.name)
def test_version_code_comes_from_the_filename(path: Path) -> None:
    identity = bills_member_identity(path.name)
    assert identity is not None
    parsed = parse_bills_xml(path.read_bytes(), path.name)
    assert (parsed.congress, parsed.bill_type, int(parsed.bill_number), parsed.version_code) == identity
    assert parsed.title
    assert parsed.published_at is not None


def test_introduced_house_bill_keeps_sponsor_name_ids_in_the_record() -> None:
    parsed = parse_bills_xml((FIXTURES / "BILLS-119hr23ih.xml").read_bytes(), "BILLS-119hr23ih.xml")
    desc = parsed.record["form"]["action"]["action-desc"]
    sponsor = desc["sponsor"]
    # always-array list tag, even with one sponsor
    first = sponsor[0] if isinstance(sponsor, list) else sponsor
    assert first["@name-id"] == "R000614"
    assert parsed.bill_stage == "Introduced-in-House"
    assert parsed.root_tag == "bill"


def test_a_resolution_uses_the_resolution_root_and_stage() -> None:
    parsed = parse_bills_xml((FIXTURES / "BILLS-119hres1eh.xml").read_bytes(), "BILLS-119hres1eh.xml")
    assert parsed.root_tag == "resolution"
    assert parsed.bill_type == "hres"
    assert parsed.version_code == "eh"
    assert parsed.bill_stage == "Engrossed-in-House"
    assert "resolution-body" in parsed.record


def test_a_doctype_is_stripped_and_never_fetched() -> None:
    raw = (FIXTURES / "BILLS-119s1pcs.xml").read_bytes()
    assert b"<!DOCTYPE" in raw
    root = parse_xml_without_dtd(raw)
    assert root.tag == "bill"
    parsed = parse_bills_xml(raw, "BILLS-119s1pcs.xml")
    assert parsed.version_code == "pcs"
    assert parsed.record["form"]["legis-num"] == "S. 1" or parsed.record["form"]["legis-num"]["#text"] == "S. 1"


def test_mixed_content_tails_are_kept_not_raised() -> None:
    root = parse_xml_without_dtd((FIXTURES / "BILLS-119hr23ih.xml").read_bytes())
    record = xml_to_record(root, capture_tails=True)
    assert record_problems(root, record) == []
    desc = record["form"]["action"]["action-desc"]
    sponsor = desc["sponsor"][0] if isinstance(desc["sponsor"], list) else desc["sponsor"]
    assert "#tail" in sponsor


def test_a_non_bills_name_is_refused() -> None:
    with pytest.raises(ValueError, match="not a BILLS"):
        parse_bills_xml(b"<bill/>", "readme.xml")


def test_a_tailed_leaf_uses_the_hash_text_path() -> None:
    root = ElementTree.fromstring("<bill><p>before <i>leaf</i> after</p></bill>")
    record = xml_to_record(root, capture_tails=True)
    assert record["p"]["i"] == {"#text": "leaf", "#tail": "after"}
    assert ("/bill/p/i/#text", "leaf") in xml_leaves(root)
    assert ("/bill/p/i", "leaf") not in xml_leaves(root)
    assert record_problems(root, record) == []


def test_nbsp_and_mdash_parse_without_fetching_a_dtd() -> None:
    raw = b"""<?xml version="1.0"?>
<!DOCTYPE bill PUBLIC "-//US Congress//DTDs/bill.dtd//EN" "bill.dtd">
<bill bill-stage="Introduced-in-House">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dublinCore>
      <dc:title>119 HR 1 IH: A&nbsp;title</dc:title>
      <dc:date>2025-01-03</dc:date>
    </dublinCore>
  </metadata>
  <form>
    <official-title>A&nbsp;title &mdash; &ldquo;quoted&rdquo; &amp; more</official-title>
  </form>
</bill>
"""
    root = parse_xml_without_dtd(raw)
    title = "".join(root.find("./form/official-title").itertext())
    assert "\u00a0" in title
    assert "\u2014" in title
    assert "\u201c" in title and "\u201d" in title
    assert "& more" in title
    parsed = parse_bills_xml(raw, "BILLS-119hr1ih.xml")
    assert parsed.bill_number == "1"


def test_xml_body_that_contradicts_the_filename_still_uses_the_filename() -> None:
    raw = (FIXTURES / "BILLS-119hr23ih.xml").read_bytes()
    parsed = parse_bills_xml(raw, "BILLS-119hr24ih.xml")
    assert parsed.bill_number == "24"
    assert parsed.stale_dublin_core == (119, "hr", 23, "ih")
    assert "119 HR 23 IH" in parsed.record["metadata"]["dublinCore"]["dc:title"]
