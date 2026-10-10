"""Census relationship files and block equivalency files into the crosswalk (Story 10.3)."""

from __future__ import annotations

import hashlib
import uuid
import zipfile
from collections.abc import Iterator
from pathlib import Path
from typing import Self

import pytest
from db_cluster import cloned_database
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert

from opendiscourse_research.catalog import sync_inventory
from opendiscourse_research.db import session
from opendiscourse_research.ingestion import census_crosswalk as cw
from opendiscourse_research.models.core import geography_table
from opendiscourse_research.repositories.legislation import register_artifact

BOM = "﻿"
HEADER = (
    "OID_CD119_20|GEOID_CD119_20|NAMELSAD_CD119_20|AREALAND_CD119_20|AREAWATER_CD119_20|MTFCC_CD119_20|FUNCSTAT_CD119_20|"
    "OID_COUNTY_20|GEOID_COUNTY_20|NAMELSAD_COUNTY_20|AREALAND_COUNTY_20|AREAWATER_COUNTY_20|MTFCC_COUNTY_20|"
    "CLASSFP_COUNTY_20|FUNCSTAT_COUNTY_20|AREALAND_PART|AREAWATER_PART"
)


def _row(district: str, county: str, land: str = "10", water: str = "2") -> str:
    return f"1|{district}|Congressional District|100|5|G5200|N|2|{county}|Name County|50|4|G4020|H1|A|{land}|{water}"


def _relationship_text(*rows: str) -> str:
    return BOM + "\n".join([HEADER, *rows]) + "\n"


def test_relationship_parser_reads_by_column_name_and_keeps_blank_sides() -> None:
    body = _relationship_text(_row("0101", "01003"), _row("0101", ""), _row("", "01005", land=""))
    rows = list(cw.parse_relationship(body.lstrip(BOM), "cd119", "county20"))
    assert [number for number, _ in rows] == [2, 3, 4]
    first = rows[0][1]
    assert (first["district_geoid"], first["overlap_geoid"], first["area_land_part"]) == ("0101", "01003", 10)
    assert rows[1][1]["overlap_geoid"] is None
    assert rows[2][1]["district_geoid"] is None and rows[2][1]["area_land_part"] is None
    assert first["raw"]["NAMELSAD_COUNTY_20"] == "Name County"


def test_relationship_parser_refuses_a_file_for_the_wrong_district_family() -> None:
    with pytest.raises(ValueError, match="GEOID_SLDU2024_20"):
        list(cw.parse_relationship(_relationship_text(_row("0101", "01003")).lstrip(BOM), "sldu", "county20"))


def test_relationship_parser_refuses_a_ragged_row() -> None:
    with pytest.raises(ValueError, match="fields"):
        list(cw.parse_relationship(HEADER + "\n1|0101|x\n", "cd119", "county20"))


def test_block_parser_checks_header_geoid_width_and_code() -> None:
    good = iter(["GEOID,CDFP\n", "010010201001000,06\n", "010010201001001,ZZ\n"])
    assert list(cw.parse_block_assignment(good, "cd119")) == [
        (2, "010010201001000", "06"),
        (3, "010010201001001", "ZZ"),
    ]
    with pytest.raises(ValueError, match="GEOID,SLDUST"):
        list(cw.parse_block_assignment(iter(["GEOID,CDFP\n"]), "sldu"))
    with pytest.raises(ValueError, match="malformed"):
        list(cw.parse_block_assignment(iter(["GEOID,CDFP\n", "0100102,06\n"]), "cd119"))


def test_every_family_overlap_and_file_name_is_defined() -> None:
    assert set(cw.FAMILIES) == {"cd119", "sldu", "sldl"}
    assert "tract20" in cw.OVERLAPS and "zcta520" in cw.OVERLAPS and "ua20" in cw.OVERLAPS
    assert cw.relationship_filename("sldl", "county20") == "tab20_sldl202420_county20_natl.txt"
    assert cw.relationship_filename("cd119", "tract20") == "tab20_cd11920_tract20_natl.txt"
    keys = [a["artifact_key"] for a in cw.bef_artifacts()]
    assert keys == ["census-bef-cd119", "census-bef-sldu", "census-bef-sldl"]


def test_relationship_plan_fails_when_the_publisher_omits_an_expected_file(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Response:
        text = '<a href="tab20_cd11920_county20_natl.txt">x</a>'

        def raise_for_status(self) -> None:
            return None

    class _Client:
        def __enter__(self) -> Self:
            return self

        def __exit__(self, *exc: object) -> None:
            return None

        def get(self, url: str) -> _Response:
            return _Response()

    monkeypatch.setattr(cw, "client", lambda: _Client())
    with pytest.raises(ValueError, match="missing"):
        cw.discover_relationship_artifacts()


# ---- database ---------------------------------------------------------------------------


_RUN = uuid.uuid4().hex[:6]


@pytest.fixture(scope="module")
def catalog_database() -> Iterator[None]:
    with cloned_database():
        sync_inventory()
        yield


def _geography(geography_type: str, geoid: str) -> None:
    with session() as active:
        active.execute(insert(geography_table()).values(geography_type=geography_type, geoid=geoid).on_conflict_do_nothing())


def _register(dataset: str, key: str, path: Path) -> None:
    """Retain the bytes at a checksum-specific path, as the downloader does, then register them."""
    data = path.read_bytes()
    checksum = hashlib.sha256(data).hexdigest()
    retained = path.with_name(f"{path.stem}.{checksum}{path.suffix}")
    retained.write_bytes(data)
    register_artifact(
        dataset,
        f"https://example.test/{key}",
        str(retained),
        key,
        status="downloaded",
        checksum_sha256=checksum,
        bytes_downloaded=len(data),
        metadata={},
    )


def _plan(dataset: str, *items: dict[str, object], state: str = "downloaded") -> dict[str, object]:
    return {"state": state, "dataset": dataset, "artifacts": list(items)}


def _counts(artifact_key: str) -> dict[str, int]:
    with session() as active:
        row = active.execute(
            text(
                "SELECT count(*) AS n, count(*) FILTER (WHERE weight_type='none') AS unweighted, "
                "count(*) FILTER (WHERE method='block_assignment') AS blocks "
                "FROM core.geography_crosswalk c JOIN ingest.artifact a ON a.artifact_id=c.source_artifact_id "
                "WHERE a.artifact_key=:k"
            ),
            {"k": artifact_key},
        ).one()
    return {"n": row.n, "unweighted": row.unweighted, "blocks": row.blocks}


@pytest.mark.db
def test_relationship_rows_load_unweighted_with_area_in_metadata_and_rerun_is_a_no_op(
    catalog_database: None, tmp_path: Path
) -> None:
    _geography("congressional_district", "0101")
    _geography("congressional_district", "0102")
    path = tmp_path / "rel.txt"
    path.write_text(_relationship_text(_row("0101", "01003", land="7"), _row("0102", "01003"), _row("0101", "")), encoding="utf-8")
    key = f"census-relationship-cd119-county20-{_RUN}"
    _register(cw.RELATIONSHIP_DATASET, key, path)
    item = {"artifact_key": key, "kind": "relationship", "family": "cd119", "overlap": "county20"}
    plan = _plan(cw.RELATIONSHIP_DATASET, item)

    assert cw.stage_crosswalk(plan) == {key: 3}
    staged_plan = {**plan, "state": "staged"}
    first = cw.load_crosswalk(staged_plan)[key]
    assert first["staged"] == 3 and first["stored"] == 2 and first["blank_side"] == 1 and first["inserted"] == 2
    assert _counts(key) == {"n": 2, "unweighted": 2, "blocks": 0}
    with session() as active:
        meta = active.execute(
            text(
                "SELECT c.metadata, c.weight, c.from_vintage, c.to_vintage, c.method FROM core.geography_crosswalk c "
                "JOIN core.geography f ON f.geography_id=c.from_geography_id AND f.geoid='0101' "
                "JOIN ingest.artifact a ON a.artifact_id=c.source_artifact_id WHERE a.artifact_key=:k"
            ),
            {"k": key},
        ).one()
        county = active.execute(
            text("SELECT state_fips, county_fips FROM core.geography WHERE geography_type='county' AND geoid='01003'")
        ).one()
    assert meta.weight is None and meta.method == "relationship"
    assert (meta.from_vintage, meta.to_vintage) == (2024, 2020)
    assert meta.metadata["land_part"] == 7 and meta.metadata["overlap_kind"] == "county20"
    assert (county.state_fips, county.county_fips) == ("01", None)  # county GEOID has no county prefix

    again = cw.load_crosswalk({**plan, "state": "loaded"})[key]
    assert again["inserted"] == 0 and again["stored"] == 2
    assert cw.validate_crosswalk({**plan, "state": "loaded"})["ok"]
    # Restaging after a load keeps one row per source line.
    assert cw.stage_crosswalk({**plan, "state": "staged"}) == {key: 3}


@pytest.mark.db
def test_block_assignment_rows_are_whole_block_assignments(catalog_database: None, tmp_path: Path) -> None:
    _geography("congressional_district", "0101")
    _geography("congressional_district", "0200")
    archive = tmp_path / "cd119.zip"
    body = "GEOID,CDFP\n010010201001000,01\n010010201001001,01\n020010001001000,00\n"
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("01_AL_CD119.txt", "GEOID,CDFP\n010010201001000,01\n")  # state member: not staged
        z.writestr("NationalCD119.txt", body)
    key = f"census-bef-cd119-{_RUN}"
    _register(cw.BEF_DATASET, key, archive)
    item = {"artifact_key": key, "kind": "bef", "family": "cd119", "member": "NationalCD119.txt"}
    plan = _plan(cw.BEF_DATASET, item)

    assert cw.stage_crosswalk(plan) == {key: 3}
    result = cw.load_crosswalk({**plan, "state": "staged"})[key]
    assert result["stored"] == 3 and result["geographies_created"] == 3
    assert _counts(key) == {"n": 3, "unweighted": 0, "blocks": 3}
    with session() as active:
        row = active.execute(
            text(
                "SELECT c.weight_type, c.weight, c.quality_flag, c.from_vintage, c.to_vintage, b.geography_type, b.parent_geoid "
                "FROM core.geography_crosswalk c JOIN core.geography b ON b.geography_id=c.from_geography_id "
                "JOIN ingest.artifact a ON a.artifact_id=c.source_artifact_id WHERE a.artifact_key=:k "
                "ORDER BY c.source_ordinal LIMIT 1"
            ),
            {"k": key},
        ).one()
    assert (row.weight_type, row.weight, row.quality_flag) == ("assignment", 1.0, "whole_block_tabulation")
    assert (row.from_vintage, row.to_vintage, row.geography_type) == (2020, 2024, "block")
    assert row.parent_geoid == "010010201001"
    assert cw.load_crosswalk({**plan, "state": "loaded"})[key]["inserted"] == 0


@pytest.mark.db
def test_a_district_code_without_a_tiger_district_fails_the_load_with_the_codes(
    catalog_database: None, tmp_path: Path
) -> None:
    _geography("sldu", "01001")
    archive = tmp_path / "sldu24.zip"
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("NationalSLDU24.txt", "GEOID,SLDUST\n010010201001000,001\n010010201001001,99X\n")
    key = f"census-bef-sldu-{_RUN}"
    _register(cw.BEF_DATASET, key, archive)
    item = {"artifact_key": key, "kind": "bef", "family": "sldu", "member": "NationalSLDU24.txt"}
    plan = _plan(cw.BEF_DATASET, item)
    cw.stage_crosswalk(plan)
    with pytest.raises(ValueError, match="99X"):
        cw.load_crosswalk({**plan, "state": "staged"})
    assert _counts(key)["n"] == 0  # the failed file left no partial rows


@pytest.mark.db
def test_stage_refuses_a_plan_that_is_not_downloaded(catalog_database: None) -> None:
    with pytest.raises(ValueError, match="downloaded"):
        cw.stage_crosswalk({"state": "draft", "dataset": cw.BEF_DATASET, "artifacts": []})
    with pytest.raises(ValueError, match="staged"):
        cw.load_crosswalk({"state": "downloaded", "dataset": cw.BEF_DATASET, "artifacts": []})
