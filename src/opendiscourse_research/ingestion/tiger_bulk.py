"""TIGER/Line boundary-package planning utilities."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from ..capacity import GiB, remote_size, storage_preview
from ..config import settings
from ..providers.census import census_directory_links
from .base import client

LAYER_DIRS = (
    ("STATE", "state"),
    ("COUNTY", "county"),
    ("CBSA", "cbsa"),
)

_ZCTA_CUTOVER_YEAR = 2020

# Story 10.2 is intentionally one verified political-boundary vintage. Each
# future political vintage must be checked against Census before admission.
_POLITICAL_PACKAGES: dict[int, dict[str, int | str]] = {
    2024: {
        "congress": 119,
        "legislative_year": 2024,
        "valid_from": "2024-01-01",
    }
}
_POLITICAL_DIRECTORIES = (
    ("CD", "cd119"),
    ("SLDU", "sldu"),
    ("SLDL", "sldl"),
)


def _zcta_layer(year: int) -> str:
    if year < _ZCTA_CUTOVER_YEAR:
        return f"ZCTA5/tl_{year}_us_zcta510.zip"
    return f"ZCTA520/tl_{year}_us_zcta520.zip"


_MISSING_LAYERS: dict[int, frozenset[str]] = {2022: frozenset({"cbsa"})}


def tiger_layers(year: int) -> tuple[str, ...]:
    """Return the small national core-boundary members for one TIGER vintage."""
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


def _selection(resource: dict[str, Any]) -> tuple[int, str] | None:
    """Return the reviewed vintage and package for one TIGER catalog resource."""
    if resource.get("dataset_id") != "census.tiger":
        return None
    parts = str(resource.get("resource_key", "")).split(":")
    if len(parts) == 3 and parts[0] == "national" and parts[2] == "core-boundaries":
        try:
            return int(parts[1]), "national_core_boundaries"
        except ValueError:
            return None
    if len(parts) == 3 and parts[0] == "political" and parts[2] == "cd119-sld2024":
        try:
            return int(parts[1]), "political_district_boundaries"
        except ValueError:
            return None
    return None


def _national_core_artifacts(year: int) -> list[dict[str, Any]]:
    base = f"https://www2.census.gov/geo/tiger/TIGER{year}"
    return [
        {
            "artifact_key": f"tiger-{year}-{path.split('/')[-1][:-4]}",
            "kind": path.split("/")[-1].removesuffix(".zip").split("_us_", 1)[1],
            "url": f"{base}/{path}",
            "filename": path.split("/")[-1],
            "boundary_vintage": year,
        }
        for path in tiger_layers(year)
    ]


def discover_political_tiger_artifacts(year: int) -> list[dict[str, Any]]:
    """Enumerate exactly the political ZIPs Census publishes for one reviewed vintage.

    Census publishes 2024 CD/SLD TIGER/Line files state-by-state. Discovery uses
    the provider directory indexes instead of a hand-maintained state list, so
    missing chambers are represented by publisher absence rather than guessed 404s.
    """
    if year not in _POLITICAL_PACKAGES:
        raise ValueError(
            f"No reviewed TIGER political-boundary package is defined for {year}"
        )
    base = f"https://www2.census.gov/geo/tiger/TIGER{year}"
    artifacts: list[dict[str, Any]] = []
    with client() as http:
        for directory, kind in _POLITICAL_DIRECTORIES:
            index_url = f"{base}/{directory}/"
            response = http.get(index_url)
            response.raise_for_status()
            pattern = re.compile(
                rf"^tl_{year}_(?P<state>[0-9]{{2}})_{re.escape(kind)}[.]zip$"
            )
            matches = []
            for url in census_directory_links(index_url, response.text):
                filename = url.rsplit("/", 1)[-1]
                match = pattern.fullmatch(filename)
                if match:
                    matches.append((url, filename, match.group("state")))
            if not matches:
                raise ValueError(
                    f"Census published no {kind} ZIP members at {index_url}"
                )
            for url, filename, state_fips in sorted(matches):
                artifacts.append(
                    {
                        "artifact_key": f"tiger-{year}-{kind}-{state_fips}",
                        "kind": kind,
                        "url": url,
                        "filename": filename,
                        "boundary_vintage": year,
                        "state_fips": state_fips,
                    }
                )
    natural_keys = {(item["kind"], item["state_fips"]) for item in artifacts}
    if len(natural_keys) != len(artifacts):
        raise ValueError("Census political TIGER discovery produced duplicate members")
    return artifacts


def build_tiger_bulk_plan(
    basket_name: str, resources: list[dict[str, Any]]
) -> dict[str, Any]:
    """Create a review-only plan for one exact TIGER boundary package."""
    selections = sorted(
        {
            selected
            for resource in resources
            if (selected := _selection(resource)) is not None
        }
    )
    if len(selections) != 1:
        raise ValueError("Select exactly one TIGER boundary package.")
    year, package = selections[0]

    if package == "national_core_boundaries":
        artifacts = _national_core_artifacts(year)
        selection: dict[str, Any] = {
            "boundary_vintage": year,
            "package": package,
            "layers": [item["kind"] for item in artifacts],
        }
        source_pages = [f"https://www2.census.gov/geo/tiger/TIGER{year}/"]
    else:
        political = _POLITICAL_PACKAGES[year]
        artifacts = discover_political_tiger_artifacts(year)
        selection = {
            "boundary_vintage": year,
            "package": package,
            "layers": ["cd119", "sldu", "sldl"],
            "congress": int(political["congress"]),
            "legislative_year": int(political["legislative_year"]),
            "valid_from": str(political["valid_from"]),
        }
        base = f"https://www2.census.gov/geo/tiger/TIGER{year}"
        source_pages = [f"{base}/CD/", f"{base}/SLDU/", f"{base}/SLDL/"]

    return {
        "version": 1,
        "state": "draft",
        "provider": "census",
        "dataset": "census.tiger",
        "format": "TIGER/Line Shapefile ZIP",
        "created_at": datetime.now(UTC).isoformat(),
        "basket": basket_name,
        "selection": selection,
        "canonical_load_scope": (
            "not approved; select boundary layers after storage preview"
        ),
        "artifacts": artifacts,
        "storage": {
            "state": "unpreviewed",
            "stage_multiplier": 3.0,
            "database_multiplier": 2.0,
            "reserve_gib": 100,
        },
        "provenance": {
            "source_pages": source_pages,
            "note": (
                "Each Census ZIP remains immutable. Canonical boundaries retain "
                "boundary vintage, reviewed validity, and artifact lineage."
            ),
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
