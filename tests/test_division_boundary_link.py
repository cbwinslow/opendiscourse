"""Division -> boundary linking by identifier (Story 10.3 matrix rows, ADR-0006)."""

from __future__ import annotations

import re
import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest
from db_cluster import cloned_database
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert

from opendiscourse_research.catalog import sync_inventory
from opendiscourse_research.db import session
from opendiscourse_research.ingestion.division_boundary import (
    STATE_FIPS,
    link_division_boundaries,
    validate_vintage,
)
from opendiscourse_research.models.core import (
    division_table,
    geography_boundary_table,
    geography_table,
)
from opendiscourse_research.repositories.legislation import register_artifact

pytestmark = pytest.mark.db

_RUN = uuid.uuid4().hex[:6]
QUERY_ROOT = Path(__file__).resolve().parents[1] / "sql" / "query" / "geography"


@pytest.fixture(scope="module")
def catalog_database() -> Iterator[None]:
    """Private migrated copy; the shared warehouse is never touched."""
    with cloned_database():
        sync_inventory()
        yield


@pytest.fixture(scope="module")
def artifact_id(catalog_database: None) -> uuid.UUID:
    return register_artifact(
        "census.tiger", f"https://example.test/{_RUN}.zip", f"/tmp/{_RUN}.zip", f"link-{_RUN}", metadata={}
    )["artifact_id"]


def _boundary(geography_type: str, geoid: str, artifact: uuid.UUID, vintage: int = 2024) -> None:
    geographies, boundaries = geography_table(), geography_boundary_table()
    with session() as active:
        gid = active.execute(
            insert(geographies)
            .values(geography_type=geography_type, geoid=geoid, name=f"name-{geoid}")
            .on_conflict_do_nothing()
            .returning(geographies.c.geography_id)
        ).scalar()
        if gid is None:
            gid = active.execute(
                text("SELECT geography_id FROM core.geography WHERE geography_type=:t AND geoid=:g"),
                {"t": geography_type, "g": geoid},
            ).scalar_one()
        active.execute(
            insert(boundaries).values(
                geography_id=gid, boundary_vintage=vintage, geom="SRID=4326;POINT(-77 38.9)", source_artifact_id=artifact
            )
        )


def _division(ocd: str, artifact: uuid.UUID, classification: str = "cd") -> None:
    with session() as active:
        active.execute(
            insert(division_table())
            .values(ocd_division_id=ocd, label=ocd, classification=classification, source_artifact_id=artifact)
            .on_conflict_do_nothing()
        )


def _links() -> dict[str, tuple[str, int | None, int | None]]:
    with session() as active:
        rows = active.execute(
            text(
                "SELECT d.ocd_division_id, l.relationship_kind, l.congress, l.legislative_year "
                "FROM core.division_boundary l JOIN core.division d USING (division_id)"
            )
        ).all()
    return {r[0]: (r[1], r[2], r[3]) for r in rows}


def test_links_house_sld_and_delegate_divisions_by_code(catalog_database: None, artifact_id: uuid.UUID) -> None:
    for geography_type, geoid in [
        ("congressional_district", "0101"),
        ("congressional_district", "0200"),
        ("congressional_district", "1198"),
        ("sldu", "01001"),
        ("sldl", "01002"),
    ]:
        _boundary(geography_type, geoid, artifact_id)
    for ocd in ("state:al/cd:1", "state:ak/cd:at-large", "district:dc"):
        _division(f"ocd-division/country:us/{ocd}", artifact_id)
    _division("ocd-division/country:us/state:al/cd:at-large", artifact_id)  # AL has 7 districts: no 0100
    _division("ocd-division/country:us/state:al/cd:9", artifact_id)  # beyond the current plan
    _division("ocd-division/country:us/territory:dt", artifact_id, "territory")  # historical territory
    # An SLD division that already exists must be reused, a numeric one is seeded from the boundary.
    _division("ocd-division/country:us/state:al/sldu:1", artifact_id, "sldu")

    report = link_division_boundaries()

    links = _links()
    assert links["ocd-division/country:us/state:al/cd:1"] == ("legal_boundary", 119, None)
    assert links["ocd-division/country:us/state:ak/cd:at-large"] == ("legal_boundary", 119, None)
    assert links["ocd-division/country:us/district:dc"] == ("delegate_district", 119, None)
    assert links["ocd-division/country:us/state:al/sldu:1"] == ("legal_boundary", None, 2024)
    assert links["ocd-division/country:us/state:al/sldl:2"] == ("legal_boundary", None, 2024)  # seeded
    assert report.seeded_divisions == 1  # sldl:2; sldu:1 pre-existed
    assert "ocd-division/country:us/state:al/cd:at-large" not in links
    assert "ocd-division/country:us/state:al/cd:9" not in links
    assert report.new_links == 5
    unlinked = {row["ocd_division_id"] for row in report.unlinked_divisions}
    assert {
        "ocd-division/country:us/state:al/cd:at-large",
        "ocd-division/country:us/state:al/cd:9",
    } <= unlinked
    assert "ocd-division/country:us/territory:dt" not in links
    by_family = {row["geography_type"]: row for row in report.families}
    assert by_family["congressional_district"]["boundaries"] == 3
    assert by_family["congressional_district"]["linked"] == 3
    assert by_family["sldu"]["linked"] == 1 and by_family["sldl"]["linked"] == 1


def test_second_run_changes_nothing(catalog_database: None, artifact_id: uuid.UUID) -> None:
    before = _links()
    report = link_division_boundaries()
    assert report.new_links == 0 and report.seeded_divisions == 0
    assert _links() == before


def test_unreviewed_name_coded_districts_are_reported_not_guessed(catalog_database: None, artifact_id: uuid.UUID) -> None:
    _boundary("sldl", "25999", artifact_id)
    _boundary("sldu", "50QRS", artifact_id)  # a Vermont-style code that is not in the reviewed crosswalk
    _boundary("sldu", "09ZZZ", artifact_id)
    _boundary("congressional_district", "09ZZ", artifact_id)
    report = link_division_boundaries()
    by_family = {row["geography_type"]: row for row in report.families}
    assert by_family["sldu"]["unlinked"] >= 1
    assert by_family["sldu"]["placeholder_unlinked"] >= 1
    assert by_family["congressional_district"]["placeholder_unlinked"] >= 1
    with session() as active:
        invented = active.execute(
            text("SELECT count(*) FROM core.division WHERE ocd_division_id ILIKE '%qrs%'")
        ).scalar_one()
    assert invented == 0


def test_reviewed_crosswalk_pairs_link_by_identifier_and_retire_phantoms(catalog_database: None, artifact_id: uuid.UUID) -> None:
    """MA '25001' (1st Barnstable) links to OCD ``1st_barnstable``; the old numeric seed is retired."""
    _boundary("sldl", "25001", artifact_id)
    _boundary("sldu", "50ADD", artifact_id)
    with session() as active:
        active.execute(
            text(
                "INSERT INTO core.division (ocd_division_id, label, classification, source_artifact_id, metadata)"
                " VALUES ('ocd-division/country:us/state:ma/sldl:1', 'seeded', 'sldl', :a,"
                " '{\"seeded_from\": \"census.tiger\", \"geoid\": \"25001\"}')"
            ),
            {"a": artifact_id},
        )
    report = link_division_boundaries()
    assert report.retired_divisions == 1
    with session() as active:
        rows = dict(
            active.execute(
                text(
                    "SELECT d.ocd_division_id, l.metadata->>'rule' FROM core.division_boundary l"
                    " JOIN core.division d USING (division_id)"
                    " WHERE d.ocd_division_id IN ('ocd-division/country:us/state:ma/sldl:1st_barnstable',"
                    " 'ocd-division/country:us/state:vt/sldu:addison')"
                )
            ).all()
        )
        phantom = active.execute(
            text("SELECT count(*) FROM core.division WHERE ocd_division_id = 'ocd-division/country:us/state:ma/sldl:1'")
        ).scalar_one()
    assert rows == {
        "ocd-division/country:us/state:ma/sldl:1st_barnstable": "reviewed_ocd_crosswalk",
        "ocd-division/country:us/state:vt/sldu:addison": "reviewed_ocd_crosswalk",
    }
    assert phantom == 0
    assert link_division_boundaries().crosswalk_links == 0  # idempotent


def test_letter_suffixed_codes_get_the_open_civic_data_id_by_rule(catalog_database: None, artifact_id: uuid.UUID) -> None:
    """Maryland '01A' is OCD ``sldl:1a`` and Alaska '00A' is ``sldu:a``; no other state is guessed."""
    _boundary("sldl", "2401A", artifact_id)
    _boundary("sldu", "0200A", artifact_id)
    _boundary("sldl", "5001A", artifact_id)  # a state outside the reviewed list
    link_division_boundaries()
    with session() as active:
        ids = set(
            active.execute(
                text("SELECT ocd_division_id FROM core.division WHERE ocd_division_id ~ 'sld[ul]:[0-9]*[a-z]$'")
            ).scalars()
        )
    assert ids == {"ocd-division/country:us/state:md/sldl:1a", "ocd-division/country:us/state:ak/sldu:a"}
    with session() as active:
        linked = active.execute(
            text(
                "SELECT count(*) FROM core.division_boundary l JOIN core.division d USING (division_id)"
                " WHERE d.ocd_division_id IN ('ocd-division/country:us/state:md/sldl:1a',"
                " 'ocd-division/country:us/state:ak/sldu:a')"
            )
        ).scalar_one()
    assert linked == 2


def test_wrong_vintage_requests_are_refused() -> None:
    for kwargs in ({"congress": 118}, {"legislative_year": 2022}, {"boundary_vintage": 2023}):
        with pytest.raises(ValueError):
            link_division_boundaries(**kwargs)
    with pytest.raises(ValueError, match="2023"):
        validate_vintage(119, 2024, 2023)


def test_a_stored_link_to_the_wrong_vintage_fails_the_run(catalog_database: None, artifact_id: uuid.UUID) -> None:
    _boundary("congressional_district", "0301", artifact_id, vintage=2023)
    _division("ocd-division/country:us/state:az/cd:1", artifact_id)
    with session() as active:
        active.execute(
            text(
                "INSERT INTO core.division_boundary "
                "(division_id, boundary_id, congress, relationship_kind, source_artifact_id) "
                "SELECT d.division_id, b.boundary_id, 119, 'legal_boundary', :a "
                "FROM core.division d, core.geography g JOIN core.geography_boundary b USING (geography_id) "
                "WHERE d.ocd_division_id='ocd-division/country:us/state:az/cd:1' AND g.geoid='0301' "
                "AND b.boundary_vintage=2023"
            ),
            {"a": artifact_id},
        )
    with pytest.raises(ValueError, match="wrong boundary vintage"):
        link_division_boundaries()
    with session() as active:
        active.execute(text("DELETE FROM core.division_boundary WHERE congress=119 AND boundary_id IN "
                            "(SELECT boundary_id FROM core.geography_boundary WHERE boundary_vintage=2023)"))


def test_state_codes_cover_states_dc_and_territories() -> None:
    assert len(STATE_FIPS) == 56
    assert len(set(STATE_FIPS.values())) == 56
    assert STATE_FIPS["al"] == "01" and STATE_FIPS["dc"] == "11" and STATE_FIPS["pr"] == "72"


@pytest.mark.parametrize("name", ["link_divisions", "seed_sld_divisions", "wrong_vintage_links"])
def test_linking_sql_never_joins_or_filters_on_display_names(name: str) -> None:
    """Join and WHERE conditions use codes only; a name may be written as a label, never compared."""
    sql = re.sub(r"--[^\n]*", "", (QUERY_ROOT / f"{name}.sql").read_text()).lower()
    conditions = re.findall(r"\bon\b(?! conflict)(.*?)(?=\bjoin\b|\bwhere\b|\bgroup\b|\border\b|\bunion\b|\bon conflict\b|;)", sql, re.DOTALL)
    conditions += re.findall(r"\bwhere\b(.*?)(?=\bgroup\b|\border\b|\bunion\b|\bon conflict\b|;|\)\s*insert)", sql, re.DOTALL)
    assert conditions, name
    for condition in conditions:
        for forbidden in ("label", ".name", " like ", "ilike"):
            assert forbidden not in condition, (name, forbidden, condition.strip())
