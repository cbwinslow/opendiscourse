"""TIGER/Line national-boundary package planning utilities."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from ..capacity import GiB, remote_size, storage_preview
from ..config import settings

# Core layers confirmed present with this exact filename pattern:
# TIGER{year}/{DIR}/tl_{year}_us_{layer}.zip. Tract/block-group/block layers
# are deliberately not included here -- their archives are much larger and
# organized per-state rather than one national file, a distinct addition
# rather than a parametrization of this one.
LAYER_DIRS = (
    ("STATE", "state"),
    ("COUNTY", "county"),
    ("CBSA", "cbsa"),
)

# ZCTA boundaries are redefined each decennial census, and Census renames
# both the directory and filename suffix to match -- confirmed live: the
# 2010-vintage `ZCTA5/..._zcta510.zip` 404s starting TIGER2021, while the
# 2020-vintage `ZCTA520/..._zcta520.zip` 404s before TIGER2020 (both exist
# in the 2020 transition year). A single hardcoded ZCTA520 directory (the
# original Phase 1 fix) silently 404s for every year before 2020.
_ZCTA_CUTOVER_YEAR = 2020


def _zcta_layer(year: int) -> str:
    if year < _ZCTA_CUTOVER_YEAR:
        return f"ZCTA5/tl_{year}_us_zcta510.zip"
    return f"ZCTA520/tl_{year}_us_zcta520.zip"


# Confirmed live: Census did not publish a national CBSA delineation file
# under TIGER2022 -- every filename tried under TIGER2022/CBSA/ 404s, and
# the directory listing has no CBSA entry for that year at all. A genuine
# one-year publishing gap, not a naming guess; extend this if a future
# vintage turns out to have a similar gap in a different layer.
_MISSING_LAYERS: dict[int, frozenset[str]] = {2022: frozenset({"cbsa"})}


def tiger_layers(year: int) -> tuple[str, ...]:
    missing = _MISSING_LAYERS.get(year, frozenset())
    core = tuple(
        f"{directory}/tl_{year}_us_{layer}.zip"
        for directory, layer in LAYER_DIRS
        if layer not in missing
    )
    return core + (_zcta_layer(year),)


def _root() -> Path:
    root = Path(settings.data_root).resolve().parent / "meta" / "bulk-plans"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _boundary_vintage(resource: dict[str, Any]) -> int | None:
    if resource.get("dataset_id") != "census.tiger":
        return None
    parts = str(resource.get("resource_key", "")).split(":")
    if len(parts) != 3 or parts[0] != "national" or parts[2] != "core-boundaries":
        return None
    try:
        return int(parts[1])
    except ValueError:
        return None


def build_tiger_bulk_plan(
    basket_name: str, resources: list[dict[str, Any]]
) -> dict[str, Any]:
    """Create a review-only plan for one vintage's national TIGER core boundaries."""
    years = sorted(
        {year for resource in resources if (year := _boundary_vintage(resource))}
    )
    if len(years) != 1:
        raise ValueError(
            "Select exactly one vintage's national TIGER core boundary package."
        )
    year = years[0]
    base = f"https://www2.census.gov/geo/tiger/TIGER{year}"
    artifacts = [
        {
            "artifact_key": f"tiger-{year}-{path.split('/')[-1][:-4]}",
            # Derived from the filename's own layer suffix (e.g.
            # "tl_2019_us_zcta510.zip" -> "zcta510"), not the directory name
            # -- the ZCTA directory ("ZCTA5") and its vintage-suffixed layer
            # kind ("zcta510") deliberately differ, since tiger_load.py's
            # LAYER_INFO is keyed by the vintage-suffixed kind (its shapefile
            # attribute columns are vintage-suffixed too: GEOID10/GEOID20).
            "kind": path.split("/")[-1].removesuffix(".zip").split("_us_", 1)[1],
            "url": f"{base}/{path}",
            "filename": path.split("/")[-1],
            "boundary_vintage": year,
        }
        for path in tiger_layers(year)
    ]
    return {
        "version": 1,
        "state": "draft",
        "provider": "census",
        "dataset": "census.tiger",
        "format": "TIGER/Line Shapefile ZIP",
        "created_at": datetime.now(UTC).isoformat(),
        "basket": basket_name,
        "selection": {
            "boundary_vintage": year,
            "package": "national_core_boundaries",
            "layers": [item["kind"] for item in artifacts],
        },
        "canonical_load_scope": "not approved; select boundary layers after the PostGIS loader is available",
        "artifacts": artifacts,
        "storage": {
            "state": "unpreviewed",
            "stage_multiplier": 3.0,
            "database_multiplier": 2.0,
            "reserve_gib": 100,
        },
        "provenance": {
            "source_page": base + "/",
            "note": "Each ZIP remains immutable. A spatial loader must record boundary vintage and artifact lineage in core.geography_boundary.",
        },
    }


def write_tiger_bulk_plan(basket_name: str, resources: list[dict[str, Any]]) -> Path:
    path = _root() / f"tiger-{basket_name}.yaml"
    temp = path.with_suffix(".yaml.part")
    temp.write_text(
        yaml.safe_dump(build_tiger_bulk_plan(basket_name, resources), sort_keys=False)
    )
    temp.replace(path)
    return path


def preview_tiger_bulk_plan(
    path: Path, update: Callable[[str], None] | None = None
) -> dict[str, Any]:
    """Measure TIGER archive sizes without downloading them."""
    plan = yaml.safe_load(path.read_text()) or {}
    if plan.get("format") != "TIGER/Line Shapefile ZIP":
        raise ValueError(f"{path} is not a TIGER bulk plan")
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
