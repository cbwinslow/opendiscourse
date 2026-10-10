"""The reviewed Census-to-OCD crosswalk: derivation rules and file invariants (no database)."""

from __future__ import annotations

import csv
import importlib.util
import re
from collections import Counter
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CROSSWALK = ROOT / "inventory" / "geography" / "ocd-sld-crosswalk-2024.csv"


@pytest.fixture(scope="module")
def builder():
    spec = importlib.util.spec_from_file_location("build_ocd_sld_crosswalk", ROOT / "scripts" / "build_ocd_sld_crosswalk.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    ("chamber", "geoid", "name", "expected"),
    [
        ("sldl", "25001", "1st Barnstable District", "state:ma/sldl:1st_barnstable"),
        ("sldl", "25006", "Barnstable-Dukes-Nantucket District", "state:ma/sldl:barnstable_dukes_and_nantucket"),
        ("sldu", "25D08", "Second Worcester District", "state:ma/sldu:2nd_worcester"),
        ("sldu", "25D01", "Berkshire-Hampden-Franklin-Hampshire District", "state:ma/sldu:berkshire_hampden_franklin_and_hampshire"),
        ("sldl", "33001", "State House District Belknap 01", "state:nh/sldl:belknap_1"),
        ("sldl", "50A-1", "Addison-1 State House District", "state:vt/sldl:addison-1"),
        ("sldu", "50ADD", "Addison Senatorial District", "state:vt/sldu:addison"),
        ("sldu", "50CHS", "Chittenden South East Senatorial District", "state:vt/sldu:chittenden-southeast"),
        ("sldu", "11003", "Ward 3", "district:dc/ward:3"),
        ("sldl", "72040", "State House District 40", "territory:pr/sldl:40"),
    ],
)
def test_ocd_id_is_derived_from_the_official_census_name(builder, chamber: str, geoid: str, name: str, expected: str) -> None:
    assert builder.derive(chamber, geoid, name) == expected


def test_a_district_without_a_rule_is_refused_not_guessed(builder) -> None:
    with pytest.raises(ValueError, match="no rule"):
        builder.derive("sldu", "33001", "State Senate District 1")  # plain number: linked by code, never by this file


def test_reviewed_file_is_complete_and_one_to_one() -> None:
    rows = list(csv.DictReader(CROSSWALK.open()))
    assert Counter(r["census_geoid"][:2] + r["chamber"] for r in rows) == {
        "25sldl": 160, "25sldu": 40, "33sldl": 164, "50sldl": 109, "50sldu": 16, "11sldu": 8, "72sldl": 40, "72sldu": 8,
    }
    assert len({r["ocd_division_id"] for r in rows}) == len(rows)
    assert len({(r["chamber"], r["census_geoid"]) for r in rows}) == len(rows)
    assert all(re.fullmatch(r"ocd-division/country:us/(state:[a-z]{2}|district:dc|territory:pr)/(sld[ul]|ward):[a-z0-9_-]+", r["ocd_division_id"]) for r in rows)


def test_every_accepted_exception_carries_its_evidence() -> None:
    rows = list(csv.DictReader(CROSSWALK.open()))
    with_evidence = {r["census_geoid"] for r in rows if r["exception_evidence"]}
    assert with_evidence == {"50ORC", "50WWB"}
