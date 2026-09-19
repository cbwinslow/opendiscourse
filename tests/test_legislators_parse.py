"""Parsing, validation and dedupe for the congress-legislators Connector (no DB)."""

from __future__ import annotations

import pytest

from opendiscourse_research.ingestion.connector import STAGES, Connector
from opendiscourse_research.ingestion.legislators import (
    FILES,
    Legislator,
    LegislatorsConnector,
    dedupe_identifiers,
    parse_legislators,
    validate_legislators,
)

YAML = """
- id:
    bioguide: C000127
    fec: [S8WA00194, H2WA01054]
    govtrack: 300018
    lis:
    wikipedia: Maria Cantwell
  name: {first: Maria, last: Cantwell, official_full: Maria Cantwell}
- id: {bioguide: B000001}
  name: {first: Ann, last: Bee}
"""


def test_parse_flattens_lists_skips_nulls_and_stringifies() -> None:
    cantwell, bee = parse_legislators(YAML)
    assert cantwell.identifiers == (
        ("bioguide", "C000127"),
        ("fec", "S8WA00194"),
        ("fec", "H2WA01054"),
        ("govtrack", "300018"),
        ("wikipedia", "Maria Cantwell"),
    )
    assert cantwell.full_name == "Maria Cantwell"
    assert (bee.full_name, bee.given_name, bee.family_name) == ("Ann Bee", "Ann", "Bee")


def test_parse_rejects_record_without_bioguide() -> None:
    with pytest.raises(ValueError, match="no bioguide"):
        parse_legislators("- id: {govtrack: 1}\n  name: {first: A, last: B}\n")


def test_parse_rejects_non_mapping_record() -> None:
    with pytest.raises(ValueError, match="not a mapping"):
        parse_legislators("- edited\n")


def test_parse_rejects_non_list_document() -> None:
    with pytest.raises(ValueError, match="YAML list"):
        parse_legislators("a: 1")


def _person(bioguide: str, *pairs: tuple[str, str]) -> Legislator:
    return Legislator(bioguide, "N", None, None, (("bioguide", bioguide), *pairs))


def test_validate_rejects_empty_file() -> None:
    with pytest.raises(ValueError, match="contains no legislators"):
        validate_legislators({"a.yaml": []})


def test_validate_rejects_malformed_bioguide() -> None:
    with pytest.raises(ValueError, match="malformed"):
        validate_legislators({"a.yaml": [_person("c000127")]})


def test_validate_rejects_bioguide_repeated_across_files() -> None:
    with pytest.raises(ValueError, match="both a.yaml and b.yaml"):
        validate_legislators({"a.yaml": [_person("A000001")], "b.yaml": [_person("A000001")]})


def test_dedupe_drops_only_ids_shared_by_two_legislators() -> None:
    a = _person("A000001", ("fec", "X"), ("govtrack", "1"))
    b = _person("B000002", ("fec", "X"), ("govtrack", "2"))
    kept, report = dedupe_identifiers([a, b])
    assert report == [{"namespace": "fec", "external_id": "X", "bioguide_ids": ["A000001", "B000002"]}]
    assert ("fec", "X") not in kept[0].identifiers + kept[1].identifiers
    assert ("govtrack", "1") in kept[0].identifiers
    assert ("bioguide", "B000002") in kept[1].identifiers


def test_dedupe_collapses_repeats_within_one_legislator() -> None:
    kept, report = dedupe_identifiers([_person("A000001", ("fec", "X"), ("fec", "X"))])
    assert report == [] and kept[0].identifiers.count(("fec", "X")) == 1


def test_connector_implements_protocol_with_all_stages() -> None:
    connector = LegislatorsConnector()
    assert isinstance(connector, Connector)
    assert all(callable(getattr(connector, stage)) for stage in STAGES)
    assert FILES == ("legislators-current.yaml", "legislators-historical.yaml")
