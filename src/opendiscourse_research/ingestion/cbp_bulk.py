"""County Business Patterns bulk-package planning utilities."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from ..capacity import GiB, remote_size, storage_preview
from ..config import settings


def cbp_files(year: int) -> tuple[str, ...]:
    """Return this year's CBP filenames, using Census's 2-digit-year convention.

    Only the subset confirmed present across the full available range
    (verified directly against the 2009, 2015, and 2023 directory
    listings) -- optional extras like congressional-district (`cd`) and
    combined-statistical-area (`csa`) bundles are published for some years
    only, and `cd` even changes file extension (.zip vs .xlsx) between
    them, so they are deliberately left out of this reliable core set
    rather than guessed per year.
    """
    yy = f"{year % 100:02d}"
    return (
        f"cbp{yy}us.zip",
        f"cbp{yy}st.zip",
        f"cbp{yy}pr_ia_st.zip",
        f"cbp{yy}msa.zip",
        f"cbp{yy}co.zip",
        f"cbp{yy}pr_ia_co.zip",
        f"zbp{yy}totals.zip",
        f"zbp{yy}detail.zip",
    )


def _root() -> Path:
    root = Path(settings.data_root).resolve().parent / "meta" / "bulk-plans"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _package_year(resource: dict[str, Any]) -> int | None:
    if (
        resource.get("dataset_id") != "census.business_patterns"
        or resource.get("resource_type") != "Complete CSV bundle"
    ):
        return None
    try:
        prefix, year = str(resource["resource_key"]).split(":", 1)
        return int(year) if prefix == "full" else None
    except (KeyError, ValueError):
        return None


def build_cbp_bulk_plan(
    basket_name: str, resources: list[dict[str, Any]]
) -> dict[str, Any]:
    """Create a disabled plan for an official complete CBP annual release."""
    years = sorted(
        {year for resource in resources if (year := _package_year(resource))}
    )
    if not years:
        raise ValueError(
            "Select a CBP complete CSV bundle before creating a bulk plan."
        )
    if len(years) != 1:
        raise ValueError(
            "Create one CBP plan per release year so revision and schema evidence remain clear."
        )
    year = years[0]
    base = f"https://www2.census.gov/programs-surveys/cbp/datasets/{year}"
    artifacts = [
        {
            "artifact_key": f"cbp-{year}-{name.rsplit('.', 1)[0]}",
            "kind": "source_data",
            "url": f"{base}/{name}",
            "filename": name,
            "release_year": year,
        }
        for name in cbp_files(year)
    ]
    return {
        "version": 1,
        "state": "draft",
        "provider": "census",
        "dataset": "census.business_patterns",
        "format": "CBP CSV-in-ZIP",
        "created_at": datetime.now(UTC).isoformat(),
        "basket": basket_name,
        "selection": {"release_year": year, "package": "complete_csv_bundle"},
        "canonical_load_scope": "not approved; choose geography and NAICS filters before enabling a load",
        "artifacts": artifacts,
        "storage": {
            "state": "unpreviewed",
            "stage_multiplier": 1.0,
            "database_multiplier": 1.5,
            "reserve_gib": 100,
        },
        "provenance": {
            "source_page": f"https://www.census.gov/data/datasets/{year}/econ/cbp/{year}-cbp.html",
            "note": "Files preserve published CBP geography and industry source schemas before canonical loading.",
        },
        "next": [
            "Run cbp-bulk-preview to record exact sizes.",
            "Review files and canonical geography/NAICS scope before approval.",
        ],
    }


def write_cbp_bulk_plan(basket_name: str, resources: list[dict[str, Any]]) -> Path:
    plan = build_cbp_bulk_plan(basket_name, resources)
    path = _root() / f"cbp-{basket_name}.yaml"
    temp = path.with_suffix(".yaml.part")
    temp.write_text(yaml.safe_dump(plan, sort_keys=False))
    temp.replace(path)
    return path


def preview_cbp_bulk_plan(
    path: Path, update: Callable[[str], None] | None = None
) -> dict[str, Any]:
    """Measure every CBP artifact without downloading content."""
    plan = yaml.safe_load(path.read_text()) or {}
    if plan.get("format") != "CBP CSV-in-ZIP":
        raise ValueError(f"{path} is not a CBP bulk plan")
    artifacts = plan.get("artifacts", [])
    objects = []
    for artifact in artifacts:
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
            "artifact_count": len(artifacts),
            "generated_at": datetime.now(UTC).isoformat(),
        }
    )
    output = path.with_suffix(".preview.json")
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    report["report"] = str(output)
    return report
