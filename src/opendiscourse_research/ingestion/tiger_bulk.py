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

# Core layers confirmed present with this exact filename pattern for every
# vintage checked (2016, 2020, 2023): TIGER{year}/{DIR}/tl_{year}_us_{layer}.zip.
# Tract/block-group/block layers are deliberately not included here -- their
# archives are much larger and organized per-state rather than one national
# file, a distinct addition rather than a parametrization of this one.
LAYER_DIRS = (
    ("STATE", "state"),
    ("COUNTY", "county"),
    ("CBSA", "cbsa"),
    ("ZCTA520", "zcta520"),
)


def tiger_layers(year: int) -> tuple[str, ...]:
    return tuple(
        f"{directory}/tl_{year}_us_{layer}.zip" for directory, layer in LAYER_DIRS
    )


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
            "kind": path.split("/")[0].lower(),
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
