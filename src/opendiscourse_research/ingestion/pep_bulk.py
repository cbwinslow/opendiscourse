"""Population Estimates Program vintage-package planning utilities."""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Callable

import yaml

from ..capacity import GiB, remote_size, storage_preview
from ..config import settings


def _root() -> Path:
    root = Path(settings.data_root).resolve().parent / "meta" / "bulk-plans"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _year(resource: dict[str, Any]) -> int | None:
    if resource.get("dataset_id") != "census.population_estimates" or resource.get("resource_type") != "National, state, and county totals": return None
    try:
        prefix, year = str(resource["resource_key"]).split(":", 1)
        return int(year) if prefix == "vintage" else None
    except (KeyError, ValueError): return None


def build_pep_bulk_plan(basket_name: str, resources: list[dict[str, Any]]) -> dict[str, Any]:
    """Create a disabled plan for one PEP vintage without mixing revisions."""
    years = sorted({year for resource in resources if (year := _year(resource))})
    if len(years) != 1: raise ValueError("Select exactly one PEP vintage package; vintages must not be co-mingled.")
    year = years[0]; base = f"https://www2.census.gov/programs-surveys/popest/datasets/2020-{year}"
    artifacts = [{"artifact_key": f"pep-{year}-state-totals", "kind": "state_totals", "url": f"{base}/state/totals/NST-EST{year}-ALLDATA.csv", "filename": f"NST-EST{year}-ALLDATA.csv", "release_year": year}, {"artifact_key": f"pep-{year}-county-totals", "kind": "county_totals", "url": f"{base}/counties/totals/co-est{year}-alldata.csv", "filename": f"co-est{year}-alldata.csv", "release_year": year}]
    return {"version": 1, "state": "draft", "provider": "census", "dataset": "census.population_estimates", "format": "PEP CSV vintage", "created_at": datetime.now(timezone.utc).isoformat(), "basket": basket_name, "selection": {"vintage": year, "package": "national_state_county_totals"}, "canonical_load_scope": "not approved; choose geography filters before enabling a load", "artifacts": artifacts, "storage": {"state": "unpreviewed", "stage_multiplier": 1.0, "database_multiplier": 1.5, "reserve_gib": 100}, "provenance": {"note": "The complete release vintage is a separate source system; do not mix it with another vintage."}}


def write_pep_bulk_plan(basket_name: str, resources: list[dict[str, Any]]) -> Path:
    path = _root() / f"pep-{basket_name}.yaml"; temp = path.with_suffix(".yaml.part")
    temp.write_text(yaml.safe_dump(build_pep_bulk_plan(basket_name, resources), sort_keys=False)); temp.replace(path)
    return path


def preview_pep_bulk_plan(path: Path, update: Callable[[str], None] | None = None) -> dict[str, Any]:
    """Measure a PEP vintage package without downloading its CSV contents."""
    plan = yaml.safe_load(path.read_text()) or {}
    if plan.get("format") != "PEP CSV vintage": raise ValueError(f"{path} is not a PEP bulk plan")
    objects = []
    for artifact in plan["artifacts"]:
        if update: update(f"Sizing {artifact['artifact_key']}")
        objects.append(remote_size(artifact["url"]))
    s = plan["storage"]; report = storage_preview(objects, stage_multiplier=float(s["stage_multiplier"]), database_multiplier=float(s["database_multiplier"]), reserve_bytes=int(s["reserve_gib"]) * GiB)
    report.update({"state": "preview", "plan": str(path), "artifact_count": len(plan["artifacts"]), "generated_at": datetime.now(timezone.utc).isoformat()}); out = path.with_suffix(".preview.json"); out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n"); report["report"] = str(out)
    return report
