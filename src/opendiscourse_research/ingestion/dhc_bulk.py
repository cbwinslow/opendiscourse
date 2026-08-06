"""2020 Decennial DHC complete-package planning utilities.

The archive is intentionally only planned here: its GEO and segment records
must be joined by LOGRECNO in a dedicated loader, not treated as ACS tables.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from ..capacity import GiB, remote_size, storage_preview
from ..config import settings


def _root() -> Path:
    root = Path(settings.data_root).resolve().parent / "meta" / "bulk-plans"
    root.mkdir(parents=True, exist_ok=True)
    return root


def build_dhc_bulk_plan(
    basket_name: str, resources: list[dict[str, Any]]
) -> dict[str, Any]:
    """Create a review-only plan for the complete 2020 DHC national archive."""
    matching = [
        item
        for item in resources
        if item.get("dataset_id") == "census.decennial"
        and item.get("resource_key") == "dhc:2020:national"
    ]
    if len(matching) != 1 or len(resources) != 1:
        raise ValueError(
            "Select exactly the 2020 DHC complete national archive; it cannot be combined with another package."
        )
    url = "https://www2.census.gov/programs-surveys/decennial/2020/data/demographic-and-housing-characteristics-file/National/us2020.dhc.zip"
    matrix = "https://www2.census.gov/programs-surveys/decennial/2020/technical-documentation/complete-tech-docs/demographic-and-housing-characteristics-file-and-demographic-profile/2020-dhc-table-matrix.xlsx"
    return {
        "version": 1,
        "state": "draft",
        "provider": "census",
        "dataset": "census.decennial",
        "format": "2020 DHC segmented pipe-delimited ZIP",
        "created_at": datetime.now(UTC).isoformat(),
        "basket": basket_name,
        "selection": {
            "product": "DHC",
            "release_year": 2020,
            "package": "complete_national_archive",
        },
        "canonical_load_scope": "not approved; select summary levels and DHC tables",
        "artifacts": [
            {
                "artifact_key": "dhc-2020-national",
                "kind": "complete_national_archive",
                "url": url,
                "filename": "us2020.dhc.zip",
                "release_year": 2020,
            },
            {
                "artifact_key": "dhc-2020-table-matrix",
                "kind": "table_matrix",
                "url": matrix,
                "filename": "2020-dhc-table-matrix.xlsx",
                "release_year": 2020,
            },
        ],
        "storage": {
            "state": "unpreviewed",
            "stage_multiplier": 4.0,
            "database_multiplier": 2.0,
            "reserve_gib": 100,
        },
        "provenance": {
            "source_page": url.rsplit("/", 1)[0] + "/",
            "note": "The official matrix maps table variables to segment positions. GEO records and segments retain member/ordinal lineage.",
        },
    }


def write_dhc_bulk_plan(basket_name: str, resources: list[dict[str, Any]]) -> Path:
    path = _root() / f"dhc-{basket_name}.yaml"
    temp = path.with_suffix(".yaml.part")
    temp.write_text(
        yaml.safe_dump(build_dhc_bulk_plan(basket_name, resources), sort_keys=False)
    )
    temp.replace(path)
    return path


def preview_dhc_bulk_plan(
    path: Path, update: Callable[[str], None] | None = None
) -> dict[str, Any]:
    """Measure the DHC archive without downloading its contents."""
    plan = yaml.safe_load(path.read_text()) or {}
    if plan.get("format") != "2020 DHC segmented pipe-delimited ZIP":
        raise ValueError(f"{path} is not a DHC bulk plan")
    objects = []
    for artifact in plan["artifacts"]:
        if update:
            update(f"Sizing {artifact['artifact_key']}")
        objects.append(remote_size(artifact["url"]))
    storage = plan["storage"]
    report = storage_preview(
        objects,
        stage_multiplier=float(storage["stage_multiplier"]),
        database_multiplier=float(storage["database_multiplier"]),
        reserve_bytes=int(storage["reserve_gib"]) * GiB,
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
