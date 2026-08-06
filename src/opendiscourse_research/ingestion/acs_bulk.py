"""Transparent ACS table-based summary-file bulk planning utilities."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from ..capacity import GiB, remote_size, storage_preview
from ..config import settings

TABLE_BASED_FIRST_YEAR = 2022
BULK_PACKAGE_FIRST_YEAR = 2021


def _root() -> Path:
    """Return the managed directory for generated, reviewable bulk plans."""
    root = Path(settings.data_root).resolve().parent / "meta" / "bulk-plans"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _table_id(resource: dict[str, Any]) -> tuple[int, str] | None:
    """Parse a synchronized ACS resource key into its release and table ID."""
    if (
        resource.get("dataset_id") != "census.acs_5"
        or resource.get("resource_type") != "Detailed Table"
    ):
        return None
    try:
        year_text, table_id = str(resource["resource_key"]).split(":", 1)
        year = int(year_text)
    except (KeyError, ValueError):
        return None
    return (year, table_id.upper()) if year >= TABLE_BASED_FIRST_YEAR else None


def _full_package_year(resource: dict[str, Any]) -> int | None:
    """Parse a bulk-browser package resource into an ACS release year."""
    if (
        resource.get("dataset_id") != "census.acs_5_bulk"
        or resource.get("resource_type") != "Full Detailed Tables"
    ):
        return None
    try:
        prefix, year_text = str(resource["resource_key"]).split(":", 1)
        year = int(year_text)
    except (KeyError, ValueError):
        return None
    return year if prefix == "full" and year >= BULK_PACKAGE_FIRST_YEAR else None


def build_acs5_bulk_plan(
    basket_name: str, resources: list[dict[str, Any]]
) -> dict[str, Any]:
    """Resolve selected modern ACS detailed tables into explicit source files.

    Table-based summary files contain estimates and margins of error for every
    published geography in a single file per Detailed Table. This function is
    deliberately planning-only: no remote request or data acquisition occurs.
    """
    packages = sorted(
        {year for resource in resources if (year := _full_package_year(resource))}
    )
    selected = sorted(
        {entry for resource in resources if (entry := _table_id(resource))}
    )
    if packages and selected:
        raise ValueError(
            "Choose either full ACS bulk packages or individual Detailed Tables, not both in one plan."
        )
    if packages:
        return _full_package_plan(basket_name, packages)
    if not selected:
        raise ValueError(
            "Select one or more 2022+ ACS 5-year Detailed Tables before creating a bulk plan. Profiles and Subject Tables use different bulk products."
        )
    artifacts: list[dict[str, Any]] = []
    for year in sorted({year for year, _ in selected}):
        base = f"https://www2.census.gov/programs-surveys/acs/summary_file/{year}/table-based-SF"
        artifacts.extend(
            [
                {
                    "artifact_key": f"acs5-{year}-geography",
                    "kind": "geography",
                    "url": f"{base}/documentation/Geos{year}5YR.txt",
                    "filename": f"Geos{year}5YR.txt",
                    "release_year": year,
                },
                {
                    "artifact_key": f"acs5-{year}-table-shells",
                    "kind": "table_shells",
                    "url": f"{base}/documentation/ACS{year}5YR_Table_Shells.txt",
                    "filename": f"ACS{year}5YR_Table_Shells.txt",
                    "release_year": year,
                },
            ]
        )
    for year, table_id in selected:
        artifacts.append(
            {
                "artifact_key": f"acs5-{year}-{table_id.lower()}",
                "kind": "detailed_table",
                "table_id": table_id,
                "release_year": year,
                "url": f"https://www2.census.gov/programs-surveys/acs/summary_file/{year}/table-based-SF/data/5YRData/acsdt5y{year}-{table_id.lower()}.dat",
                "filename": f"acsdt5y{year}-{table_id.lower()}.dat",
            }
        )
    return {
        "version": 1,
        "state": "draft",
        "provider": "census",
        "dataset": "census.acs_5_bulk",
        "format": "ACS table-based summary file",
        "created_at": datetime.now(UTC).isoformat(),
        "basket": basket_name,
        "selection": {
            "release_years": sorted({year for year, _ in selected}),
            "detailed_tables": [
                {"year": year, "table_id": table_id} for year, table_id in selected
            ],
            "table_count": len(selected),
        },
        "geography": {
            "source_coverage": "all geographies published in each selected table",
            "canonical_load_scope": "not approved; choose geography filters before enabling a load",
        },
        "artifacts": artifacts,
        "storage": {
            "state": "unpreviewed",
            "stage_multiplier": 1.0,
            "database_multiplier": 1.5,
            "reserve_gib": 100,
        },
        "provenance": {
            "source_format_documentation": "https://www.census.gov/programs-surveys/acs/data/summary-file.html",
            "note": "Each selected Detailed Table file contains estimates and margins of error; checksums and byte sizes are captured only during preflight/download.",
        },
        "next": [
            "Run `research-db ingest acs-bulk-preview --plan <path>` to resolve byte sizes and storage requirements.",
            "Review every artifact and select canonical geography filters before changing this plan from draft.",
            "After download, run `acs-bulk-stage`, then `acs-bulk-load`; both retain immutable artifact lineage.",
        ],
    }


def _full_package_plan(basket_name: str, years: list[int]) -> dict[str, Any]:
    """Build a disabled plan for complete, release-level ACS Summary Files."""
    artifacts: list[dict[str, Any]] = []
    for year in years:
        base = f"https://www2.census.gov/programs-surveys/acs/summary_file/{year}/table-based-SF"
        artifacts.extend(
            [
                {
                    "artifact_key": f"acs5-{year}-full",
                    "kind": "full_detailed_tables",
                    "url": f"{base}/data/5YRData/5YRData.zip",
                    "filename": "5YRData.zip",
                    "release_year": year,
                },
                {
                    "artifact_key": f"acs5-{year}-geography",
                    "kind": "geography",
                    "url": f"{base}/documentation/Geos{year}5YR.txt",
                    "filename": f"Geos{year}5YR.txt",
                    "release_year": year,
                },
                {
                    "artifact_key": f"acs5-{year}-table-shells",
                    "kind": "table_shells",
                    "url": f"{base}/documentation/ACS{year}5YR_Table_Shells.txt",
                    "filename": f"ACS{year}5YR_Table_Shells.txt",
                    "release_year": year,
                },
            ]
        )
    return {
        "version": 1,
        "state": "draft",
        "provider": "census",
        "dataset": "census.acs_5_bulk",
        "format": "ACS table-based summary file",
        "created_at": datetime.now(UTC).isoformat(),
        "basket": basket_name,
        "selection": {
            "release_years": years,
            "package": "full_detailed_tables",
            "table_count": "all Detailed Tables",
        },
        "geography": {
            "source_coverage": "all geographies published in each release",
            "canonical_load_scope": "not approved; choose geography filters before enabling a load",
        },
        "artifacts": artifacts,
        "storage": {
            "state": "unpreviewed",
            "stage_multiplier": 1.0,
            "database_multiplier": 1.5,
            "reserve_gib": 100,
        },
        "provenance": {
            "source_format_documentation": "https://www.census.gov/programs-surveys/acs/data/summary-file.html",
            "note": "Complete release package; checksums and byte sizes are captured only during preflight/download.",
        },
        "next": [
            "Run `research-db ingest acs-bulk-preview --plan <path>` to resolve byte sizes and storage requirements.",
            "Review every artifact and select canonical geography filters before changing this plan from draft.",
            "Complete release packages are preview/download-only until a dedicated archive loader is approved.",
        ],
    }


def write_acs5_bulk_plan(basket_name: str, resources: list[dict[str, Any]]) -> Path:
    """Write an explicit disabled bulk plan atomically under lake metadata."""
    plan = build_acs5_bulk_plan(basket_name, resources)
    path = _root() / f"acs5-{basket_name}.yaml"
    temporary = path.with_suffix(".yaml.part")
    temporary.write_text(yaml.safe_dump(plan, sort_keys=False))
    temporary.replace(path)
    return path


def preview_acs5_bulk_plan(
    path: Path, update: Callable[[str], None] | None = None
) -> dict[str, Any]:
    """Measure every planned source file and write a non-mutating preview report."""
    plan = yaml.safe_load(path.read_text()) or {}
    if (
        plan.get("dataset") != "census.acs_5_bulk"
        or plan.get("format") != "ACS table-based summary file"
    ):
        raise ValueError(f"{path} is not an ACS 5-year table-based bulk plan")
    artifacts = plan.get("artifacts", [])
    if not artifacts:
        raise ValueError(f"{path} does not contain any artifacts")
    objects = []
    for artifact in artifacts:
        if update:
            update(f"Sizing {artifact['artifact_key']}")
        objects.append(remote_size(artifact["url"]))
    storage = plan.get("storage", {})
    report = storage_preview(
        objects,
        stage_multiplier=float(storage.get("stage_multiplier", 1.0)),
        database_multiplier=float(storage.get("database_multiplier", 1.5)),
        reserve_bytes=int(storage.get("reserve_gib", 100)) * GiB,
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
