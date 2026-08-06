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

BASE = "https://www2.census.gov/geo/tiger/TIGER2020"
LAYERS = (
    "STATE/tl_2020_us_state.zip",
    "COUNTY/tl_2020_us_county.zip",
    "CBSA/tl_2020_us_cbsa.zip",
    "ZCTA520/tl_2020_us_zcta520.zip",
)


def _root() -> Path:
    root = Path(settings.data_root).resolve().parent / "meta" / "bulk-plans"
    root.mkdir(parents=True, exist_ok=True)
    return root


def build_tiger_bulk_plan(
    basket_name: str, resources: list[dict[str, Any]]
) -> dict[str, Any]:
    """Create a review-only plan for national 2020 TIGER core boundaries."""
    if (
        len(resources) != 1
        or resources[0].get("dataset_id") != "census.tiger"
        or resources[0].get("resource_key") != "national:2020:core-boundaries"
    ):
        raise ValueError(
            "Select exactly the 2020 TIGER/Line national core boundary package."
        )
    artifacts = [
        {
            "artifact_key": f"tiger-2020-{path.split('/')[-1][:-4]}",
            "kind": path.split("/")[0].lower(),
            "url": f"{BASE}/{path}",
            "filename": path.split("/")[-1],
            "boundary_vintage": 2020,
        }
        for path in LAYERS
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
            "boundary_vintage": 2020,
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
            "source_page": BASE + "/",
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
