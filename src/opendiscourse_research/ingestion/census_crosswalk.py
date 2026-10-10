"""Census district relationship files and block equivalency files into ``core.geography_crosswalk``.

Two official families, both for the 119th-Congress (``cd119``) and 2024 state legislative
(``sldu``, ``sldl``) plans:

* Relationship files: which counties, tracts, places and so on each district overlaps.
  Stored as unweighted rows (``weight_type='none'``); the overlap areas are evidence in metadata
  and never a population weight.
* Block equivalency files (BEF): which district each 2020 census block was tabulated into.
  Stored as whole-block assignments (``weight_type='assignment'``, weight 1). Where a plan
  splits a block, TIGER polygons remain the boundary truth.

Flow, as for the other Census bulk families: plan -> size preview -> approve -> resumable
download into ``DATA_ROOT`` -> stage -> load -> validate. Every row keeps its source artifact
and source line number.
"""

from __future__ import annotations

import csv
import io
import json
import zipfile
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from functools import cache
from pathlib import Path
from typing import Any

import yaml

from ..capacity import GiB, remote_size, storage_preview
from ..config import settings
from ..db import connect
from ..providers.census import census_directory_links
from ..repositories.artifacts import require_current_artifact
from .base import IngestionRun, client

_QUERY_ROOT = Path(__file__).resolve().parents[3] / "sql" / "query" / "geography"

RELATIONSHIP_DATASET = "census.redistricting_relationship"
BEF_DATASET = "census.redistricting_bef"
RELATIONSHIP_INDEX = "https://www2.census.gov/geo/docs/maps-data/data/rel2020/cd-sld/"
BEF_BASE = "https://www2.census.gov/programs-surveys/decennial/rdo/mapping-files/2025"

#: Census geography vintage of every overlap geography and block in these files.
CENSUS_VINTAGE = 2020
#: The district plans, as ``inventory/geography-vintages.yaml`` fixes them for the first slice.
PLAN_VINTAGE = 2024

#: One entry per district family: the TIGER geography type, the file tag in relationship file
#: names, the BEF archive and member, and the width of the district code in a TIGER GEOID.
FAMILIES: dict[str, dict[str, str]] = {
    "cd119": {
        "district_type": "congressional_district",
        "tag": "cd11920",
        "district_column": "CD119_20",
        "bef_zip": "119-congressional-district-befs/cd119.zip",
        "bef_member": "NationalCD119.txt",
        "code_column": "CDFP",
    },
    "sldu": {
        "district_type": "sldu",
        "tag": "sldu202420",
        "district_column": "SLDU2024_20",
        "bef_zip": "2024-state-legislative-bef/sldu24.zip",
        "bef_member": "NationalSLDU24.txt",
        "code_column": "SLDUST",
    },
    "sldl": {
        "district_type": "sldl",
        "tag": "sldl202420",
        "district_column": "SLDL2024_20",
        "bef_zip": "2024-state-legislative-bef/sldl24.zip",
        "bef_member": "NationalSLDL24.txt",
        "code_column": "SLDLST",
    },
}

#: Relationship-file token -> (geography type, GEOID starts with state FIPS, then county FIPS).
OVERLAPS: dict[str, tuple[str, bool, bool]] = {
    "aiannh20": ("aiannh", False, False),
    "county20": ("county", True, False),
    "cousub20": ("county_subdivision", True, True),
    "place20": ("place", True, False),
    "sdcombo20": ("school_district_combined", True, False),
    "tract20": ("tract", True, True),
    "ua20": ("urban_area", False, False),
    "zcta520": ("zcta", False, False),
}

#: Plan states, advanced by ``bulk.advance_plan`` exactly as the TIGER plan does.
_PLAN_FORMAT = {
    RELATIONSHIP_DATASET: "Census relationship file TXT",
    BEF_DATASET: "Census block equivalency file ZIP",
}
# Stage and database growth per downloaded byte, measured from the national files (see PROJECT-STATE).
_STORAGE = {
    RELATIONSHIP_DATASET: {"stage_multiplier": 8.0, "database_multiplier": 8.0, "reserve_gib": 100},
    BEF_DATASET: {"stage_multiplier": 40.0, "database_multiplier": 200.0, "reserve_gib": 100},
}
_BATCH = 50_000


@cache
def _query(name: str) -> str:
    """Read a version-controlled geography query once per process."""
    return (_QUERY_ROOT / f"{name}.sql").read_text()


def _root() -> Path:
    root = Path(settings.data_root).resolve().parent / "meta" / "bulk-plans"
    root.mkdir(parents=True, exist_ok=True)
    return root


def relationship_filename(family: str, overlap: str) -> str:
    """Name of the national relationship file for one district family and overlap geography."""
    return f"tab20_{FAMILIES[family]['tag']}_{overlap}_natl.txt"


def discover_relationship_artifacts() -> list[dict[str, Any]]:
    """The national relationship files the publisher lists for the three district families.

    A file the directory does not list is a publisher absence and fails the plan; nothing is
    guessed from a 404.
    """
    with client() as http:
        response = http.get(RELATIONSHIP_INDEX)
        response.raise_for_status()
        listed = {url.rsplit("/", 1)[-1]: url for url in census_directory_links(RELATIONSHIP_INDEX, response.text)}
    artifacts: list[dict[str, Any]] = []
    missing: list[str] = []
    for family in FAMILIES:
        for overlap in OVERLAPS:
            name = relationship_filename(family, overlap)
            if name not in listed:
                missing.append(name)
                continue
            artifacts.append(
                {
                    "artifact_key": f"census-relationship-{family}-{overlap}",
                    "kind": "relationship",
                    "family": family,
                    "overlap": overlap,
                    "url": listed[name],
                    "filename": name,
                }
            )
    if missing:
        raise ValueError(f"Census relationship directory is missing {len(missing)} expected files: {sorted(missing)}")
    return artifacts


def bef_artifacts() -> list[dict[str, Any]]:
    """The three block equivalency ZIPs (the national member of each is the one staged)."""
    return [
        {
            "artifact_key": f"census-bef-{family}",
            "kind": "bef",
            "family": family,
            "member": info["bef_member"],
            "url": f"{BEF_BASE}/{info['bef_zip']}",
            "filename": info["bef_zip"].rsplit("/", 1)[-1],
        }
        for family, info in FAMILIES.items()
    ]


def build_crosswalk_plan(dataset: str) -> dict[str, Any]:
    """Create a review-only plan for one crosswalk dataset."""
    if dataset not in _PLAN_FORMAT:
        raise ValueError(f"Choose one of {sorted(_PLAN_FORMAT)}")
    artifacts = discover_relationship_artifacts() if dataset == RELATIONSHIP_DATASET else bef_artifacts()
    return {
        "version": 1,
        "state": "draft",
        "provider": "census",
        "dataset": dataset,
        "format": _PLAN_FORMAT[dataset],
        "created_at": datetime.now(UTC).isoformat(),
        "selection": {
            "families": list(FAMILIES),
            "census_vintage": CENSUS_VINTAGE,
            "plan_vintage": PLAN_VINTAGE,
        },
        "canonical_load_scope": "not approved; preview storage first",
        "artifacts": artifacts,
        "storage": {"state": "unpreviewed", **_STORAGE[dataset]},
        "provenance": {
            "source_pages": [RELATIONSHIP_INDEX if dataset == RELATIONSHIP_DATASET else BEF_BASE + "/"],
            "note": (
                "Each Census file stays immutable. Relationship rows carry no weight; block "
                "rows are whole-block tabulation assignments."
            ),
        },
    }


def write_crosswalk_plan(dataset: str) -> Path:
    """Write the plan beside the other bulk plans and return its path."""
    path = _root() / f"{dataset.replace('.', '-')}.yaml"
    temp = path.with_suffix(".yaml.part")
    temp.write_text(yaml.safe_dump(build_crosswalk_plan(dataset), sort_keys=False))
    temp.replace(path)
    return path


def preview_crosswalk_plan(path: Path, update: Callable[[str], None] | None = None) -> dict[str, Any]:
    """Measure archive sizes without downloading them; an unknown size is never approved."""
    plan = yaml.safe_load(path.read_text()) or {}
    if plan.get("dataset") not in _PLAN_FORMAT:
        raise ValueError(f"{path} is not a Census crosswalk plan")
    objects = []
    for artifact in plan["artifacts"]:
        if update:
            update(f"Sizing {artifact['artifact_key']}")
        objects.append(remote_size(artifact["url"]))
    s = plan["storage"]
    report = storage_preview(
        objects,
        stage_multiplier=float(s["stage_multiplier"]),
        database_multiplier=float(s["database_multiplier"]),
        reserve_bytes=int(s["reserve_gib"]) * GiB,
    )
    report.update(
        {
            "state": "preview",
            "plan": str(path),
            "artifact_count": len(plan["artifacts"]),
            "generated_at": datetime.now(UTC).isoformat(),
        }
    )
    out = path.with_suffix(".preview.json")
    out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    report["report"] = str(out)
    return report


def _district_geoid_column(header: list[str], family: str) -> tuple[int, int]:
    """Indexes of the district GEOID and the overlap GEOID, found by name, never by position."""
    district = f"GEOID_{FAMILIES[family]['district_column']}"
    geoid_columns = [i for i, name in enumerate(header) if name.startswith("GEOID_")]
    if header.count(district) != 1 or len(geoid_columns) != 2:
        raise ValueError(f"relationship file for {family} must have {district} and exactly one other GEOID column: {header}")
    district_index = header.index(district)
    other = [i for i in geoid_columns if i != district_index]
    if len(other) != 1:
        raise ValueError(f"relationship file for {family} does not name a second geography: {header}")
    return district_index, other[0]


def _integer(value: str | None) -> int | None:
    value = (value or "").strip()
    return int(value) if value else None


def parse_relationship(text: str, family: str, overlap: str) -> Iterator[tuple[int, dict[str, Any]]]:
    """Yield ``(source line number, staged row)`` for each data row of one relationship file.

    The line number counts the header as line 1, so the first data row is line 2. A row whose
    district or overlap GEOID is blank is kept (with ``None``) so the counts reconcile.
    """
    reader = csv.reader(io.StringIO(text), delimiter="|")
    try:
        header = [name.lstrip("﻿").strip() for name in next(reader)]
    except StopIteration:
        raise ValueError("relationship file is empty") from None
    district_at, overlap_at = _district_geoid_column(header, family)
    land, water = header.index("AREALAND_PART"), header.index("AREAWATER_PART")
    for number, row in enumerate(reader, start=2):
        if len(row) != len(header):
            raise ValueError(f"relationship line {number} has {len(row)} fields; header has {len(header)}")
        yield number, {
            "family": family,
            "overlap_kind": overlap,
            "district_geoid": row[district_at].strip() or None,
            "overlap_geoid": row[overlap_at].strip() or None,
            "area_land_part": _integer(row[land]),
            "area_water_part": _integer(row[water]),
            "raw": dict(zip(header, row, strict=True)),
        }


def parse_block_assignment(lines: Iterator[str], family: str) -> Iterator[tuple[int, str, str]]:
    """Yield ``(source line number, block GEOID, district code)`` for one national BEF member."""
    code_column = FAMILIES[family]["code_column"]
    header = next(lines, None)
    if header is None or [name.strip() for name in header.lstrip("﻿").split(",")] != ["GEOID", code_column]:
        raise ValueError(f"{family} block equivalency file must start with GEOID,{code_column}; got {header!r}")
    for number, line in enumerate(lines, start=2):
        geoid, _, code = line.strip().partition(",")
        if len(geoid) != 15 or not geoid.isdigit() or not code or "," in code:
            raise ValueError(f"{family} block equivalency line {number} is malformed: {line!r}")
        yield number, geoid, code


def _artifact(item: dict[str, Any]) -> dict[str, Any]:
    return require_current_artifact(item["artifact_key"], label="Census crosswalk", dataset_id=None)


def _stage_relationship(conn: Any, item: dict[str, Any], artifact: dict[str, Any]) -> int:
    text = Path(artifact["local_path"]).read_text(encoding="utf-8-sig")
    rows = list(parse_relationship(text, item["family"], item["overlap"]))
    with conn.cursor() as cur:
        cur.execute("DELETE FROM stage.census_relationship_row WHERE artifact_id = %s", (artifact["artifact_id"],))
        with cur.copy(
            "COPY stage.census_relationship_row (artifact_id, source_ordinal, family, overlap_kind, "
            "district_geoid, overlap_geoid, area_land_part, area_water_part, raw) FROM STDIN"
        ) as copy:
            for number, row in rows:
                copy.write_row(
                    (
                        artifact["artifact_id"],
                        number,
                        row["family"],
                        row["overlap_kind"],
                        row["district_geoid"],
                        row["overlap_geoid"],
                        row["area_land_part"],
                        row["area_water_part"],
                        json.dumps(row["raw"]),
                    )
                )
    return len(rows)


def _stage_block_assignment(conn: Any, item: dict[str, Any], artifact: dict[str, Any]) -> int:
    staged = 0
    with zipfile.ZipFile(artifact["local_path"]) as archive, archive.open(item["member"]) as raw, conn.cursor() as cur:
        cur.execute("DELETE FROM stage.census_block_assignment WHERE artifact_id = %s", (artifact["artifact_id"],))
        lines = iter(io.TextIOWrapper(raw, encoding="utf-8"))
        with cur.copy(
            "COPY stage.census_block_assignment (artifact_id, source_ordinal, family, block_geoid, district_code) FROM STDIN"
        ) as copy:
            for number, geoid, code in parse_block_assignment(lines, item["family"]):
                copy.write_row((artifact["artifact_id"], number, item["family"], geoid, code))
                staged += 1
    return staged


def _scope(plan: dict[str, Any], *states: str) -> list[dict[str, Any]]:
    if plan.get("state") not in states:
        raise ValueError(f"Crosswalk plan must be {' or '.join(states)}, found {plan.get('state')!r}")
    if plan.get("dataset") not in _PLAN_FORMAT:
        raise ValueError("Plan is not a Census crosswalk plan")
    return list(plan["artifacts"])


def stage_crosswalk(plan: dict[str, Any], update: Callable[[str], None] | None = None) -> dict[str, int]:
    """Parse every downloaded file into source-shaped staging rows, one transaction per file.

    Re-staging a file replaces its own staged rows only; the retained bytes are never touched.
    Returns staged rows by artifact key.
    """
    artifacts = _scope(plan, "downloaded", "staged")
    counts: dict[str, int] = {}
    with connect() as conn:
        for item in artifacts:
            if update:
                update(f"Staging {item['artifact_key']}")
            artifact = _artifact(item)
            stage = _stage_relationship if item["kind"] == "relationship" else _stage_block_assignment
            counts[item["artifact_key"]] = stage(conn, item, artifact)
            conn.commit()
    return counts


def load_crosswalk(plan: dict[str, Any], update: Callable[[str], None] | None = None) -> dict[str, dict[str, int]]:
    """Promote staged rows into ``core.geography_crosswalk``, one transaction per file.

    Idempotent: the natural key (endpoints, vintages, method, artifact, source line) makes a
    rerun insert nothing. After each file the stored rows plus the rows with a blank side must
    equal the staged rows; anything else is reported by code and fails the load.
    """
    artifacts = _scope(plan, "staged", "loaded")
    dataset = plan["dataset"]
    results: dict[str, dict[str, int]] = {}
    with IngestionRun(dataset, {"action": "load_crosswalk", "artifact_count": len(artifacts)}, mode="manual") as run:
        total = 0
        with connect() as conn:
            for item in artifacts:
                if update:
                    update(f"Loading {item['artifact_key']}")
                artifact = _artifact(item)
                family = FAMILIES[item["family"]]
                params: dict[str, Any] = {
                    "artifact_id": artifact["artifact_id"],
                    "dataset_id": dataset,
                    "district_type": family["district_type"],
                }
                with conn.cursor() as cur:
                    if item["kind"] == "relationship":
                        geography_type, state_prefix, county_prefix = OVERLAPS[item["overlap"]]
                        params.update(
                            geography_type=geography_type,
                            state_prefix=state_prefix,
                            county_prefix=county_prefix,
                            from_vintage=PLAN_VINTAGE,
                            to_vintage=CENSUS_VINTAGE,
                        )
                        cur.execute(_query("crosswalk_relationship_geographies"), params)
                        created = len(cur.fetchall())
                        cur.execute(_query("crosswalk_relationship"), params)
                    else:
                        params.update(from_vintage=CENSUS_VINTAGE, to_vintage=PLAN_VINTAGE)
                        cur.execute(_query("crosswalk_block_geographies"), params)
                        created = len(cur.fetchall())
                        cur.execute(_query("crosswalk_block_assignment"), params)
                    inserted = len(cur.fetchall())
                    cur.execute(_query("crosswalk_reconcile"), params)
                    counts = cur.fetchone()
                    staged = counts["relationship_staged"] + counts["block_staged"]
                    unmatched = staged - counts["relationship_blank_side"] - counts["stored"]
                    if unmatched or counts["weighted_relationship"] or counts["bad_assignment"]:
                        detail: list[dict[str, Any]] = []
                        if unmatched and item["kind"] == "bef":
                            cur.execute(_query("crosswalk_unmatched_codes"), params)
                            detail = [dict(row) for row in cur.fetchmany(20)]
                        conn.rollback()
                        raise ValueError(
                            f"{item['artifact_key']} does not reconcile: staged {staged}, stored {counts['stored']}, "
                            f"blank side {counts['relationship_blank_side']}, unmatched {unmatched}, "
                            f"weighted relationship rows {counts['weighted_relationship']}, "
                            f"bad assignment rows {counts['bad_assignment']}; first unmatched codes: {detail}"
                        )
                conn.commit()
                results[item["artifact_key"]] = {
                    "staged": staged,
                    "stored": counts["stored"],
                    "inserted": inserted,
                    "blank_side": counts["relationship_blank_side"],
                    "geographies_created": created,
                }
                total += inserted
        run.record_count = total
    return results


def validate_crosswalk(plan: dict[str, Any]) -> dict[str, Any]:
    """Re-check the retained files, staging and stored rows without writing anything."""
    artifacts = _scope(plan, "loaded", "staged")
    report: dict[str, Any] = {"artifacts": {}, "ok": True}
    with connect() as conn, conn.cursor() as cur:
        for item in artifacts:
            artifact = _artifact(item)
            cur.execute(_query("crosswalk_reconcile"), {"artifact_id": artifact["artifact_id"]})
            counts = dict(cur.fetchone())
            staged = counts["relationship_staged"] + counts["block_staged"]
            ok = (
                staged - counts["relationship_blank_side"] == counts["stored"]
                and not counts["weighted_relationship"]
                and not counts["bad_assignment"]
            )
            report["artifacts"][item["artifact_key"]] = {**counts, "ok": ok}
            report["ok"] = report["ok"] and ok
    return report
