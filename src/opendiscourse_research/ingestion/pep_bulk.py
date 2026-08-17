"""Population Estimates Program vintage-package planning utilities."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from ..capacity import GiB, remote_size, storage_preview
from ..config import settings

# Each PEP vintage series has its own base path and filename casing
# convention -- confirmed directly against the live Census directory
# listings rather than assumed (2020-2025 uses NST-EST/uppercase and
# ALLDATA/uppercase; 2010-2020 uses nst-est/lowercase and alldata/lowercase).
# Only add a series here after checking its real files; a wrong guess would
# silently 404 rather than fetch the wrong data, but still fail confusingly.
VINTAGE_SERIES: dict[str, dict[str, str]] = {
    "2020-2025": {
        "state_file": "NST-EST{year}-ALLDATA.csv",
        "county_file": "co-est{year}-alldata.csv",
    },
    "2010-2020": {
        "state_file": "nst-est{year}-alldata.csv",
        "county_file": "co-est{year}-alldata.csv",
    },
}


def _root() -> Path:
    root = Path(settings.data_root).resolve().parent / "meta" / "bulk-plans"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _series(resource: dict[str, Any]) -> str | None:
    if (
        resource.get("dataset_id") != "census.population_estimates"
        or resource.get("resource_type") != "National, state, and county totals"
    ):
        return None
    prefix, _, series = str(resource.get("resource_key", "")).partition(":")
    return series if prefix == "vintage" and series in VINTAGE_SERIES else None


def build_pep_bulk_plan(
    basket_name: str, resources: list[dict[str, Any]]
) -> dict[str, Any]:
    """Create a disabled plan for one PEP vintage series without mixing revisions."""
    series_set = sorted(
        {series for resource in resources if (series := _series(resource))}
    )
    if len(series_set) != 1:
        raise ValueError(
            "Select exactly one PEP vintage package; vintages must not be co-mingled."
        )
    series = series_set[0]
    year = int(series.split("-")[1])
    files = VINTAGE_SERIES[series]
    base = f"https://www2.census.gov/programs-surveys/popest/datasets/{series}"
    state_file = files["state_file"].format(year=year)
    county_file = files["county_file"].format(year=year)
    artifacts = [
        {
            "artifact_key": f"pep-{series}-state-totals",
            "kind": "state_totals",
            "url": f"{base}/state/totals/{state_file}",
            "filename": state_file,
            "release_year": year,
        },
        {
            "artifact_key": f"pep-{series}-county-totals",
            "kind": "county_totals",
            "url": f"{base}/counties/totals/{county_file}",
            "filename": county_file,
            "release_year": year,
        },
    ]
    return {
        "version": 1,
        "state": "draft",
        "provider": "census",
        "dataset": "census.population_estimates",
        "format": "PEP CSV vintage",
        "created_at": datetime.now(UTC).isoformat(),
        "basket": basket_name,
        "selection": {
            "vintage": series,
            "release_year": year,
            "package": "national_state_county_totals",
        },
        "canonical_load_scope": "not approved; choose geography filters before enabling a load",
        "artifacts": artifacts,
        "storage": {
            "state": "unpreviewed",
            "stage_multiplier": 1.0,
            "database_multiplier": 1.5,
            "reserve_gib": 100,
        },
        "provenance": {
            "note": "The complete release vintage is a separate source system; do not mix it with another vintage."
        },
    }


def write_pep_bulk_plan(basket_name: str, resources: list[dict[str, Any]]) -> Path:
    path = _root() / f"pep-{basket_name}.yaml"
    temp = path.with_suffix(".yaml.part")
    temp.write_text(
        yaml.safe_dump(build_pep_bulk_plan(basket_name, resources), sort_keys=False)
    )
    temp.replace(path)
    return path


def preview_pep_bulk_plan(
    path: Path, update: Callable[[str], None] | None = None
) -> dict[str, Any]:
    """Measure a PEP vintage package without downloading its CSV contents."""
    plan = yaml.safe_load(path.read_text()) or {}
    if plan.get("format") != "PEP CSV vintage":
        raise ValueError(f"{path} is not a PEP bulk plan")
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
