"""Evidence-led validation for completed TIGER/Line bulk plans."""

from __future__ import annotations

import re
from copy import deepcopy
from functools import cache
from pathlib import Path
from typing import Any

from ..db import connect
from ..repositories.artifacts import require_current_artifact
from .tiger_load import LAYER_INFO, _scope, load_tiger

_QUERY_ROOT = Path(__file__).resolve().parents[3] / "sql" / "query" / "census" / "tiger"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_OFFICIAL_TIGER_PREFIX = "https://www2.census.gov/geo/tiger/TIGER"


@cache
def _query(name: str) -> str:
    """Read one version-controlled TIGER validation query."""
    return (_QUERY_ROOT / f"{name}.sql").read_text()


def _artifact_evidence(
    item: dict[str, Any],
    artifact: dict[str, Any],
    *,
    source_features: int,
    official_host_required: bool,
) -> dict[str, Any]:
    """Return stable evidence checks for one retained TIGER source artifact."""
    expected_url = str(item["url"])
    remote_url = str(artifact.get("remote_url") or "")
    checksum = str(artifact.get("checksum_sha256") or "")
    bytes_downloaded = int(artifact.get("bytes_downloaded") or 0)
    local_path = Path(str(artifact.get("local_path") or ""))
    checks = {
        "url_matches_plan": remote_url == expected_url,
        "official_census_url": (
            remote_url.startswith(_OFFICIAL_TIGER_PREFIX)
            if official_host_required
            else True
        ),
        "positive_bytes": bytes_downloaded > 0,
        "sha256": bool(_SHA256.fullmatch(checksum)),
        "local_file_exists": local_path.is_file(),
        "positive_source_features": source_features > 0,
    }
    return {
        "artifact_key": item["artifact_key"],
        "layer": item["kind"],
        "state_fips": item.get("state_fips"),
        "remote_url": remote_url,
        "local_path": str(local_path),
        "bytes": bytes_downloaded,
        "checksum_sha256": checksum,
        "source_features": source_features,
        "checks": checks,
        "passed": all(checks.values()),
    }


def _snapshot(
    plan: dict[str, Any], *, official_host_required: bool = True
) -> dict[str, Any]:
    """Read source, stage, and canonical evidence without mutating the warehouse."""
    if plan.get("state") != "loaded":
        raise ValueError("TIGER validation requires a loaded plan")

    try:
        import pyogrio
    except ImportError as exc:
        raise RuntimeError(
            "TIGER validation requires the spatial extra: uv sync --extra spatial"
        ) from exc

    layers = sorted(_scope(plan))
    vintage = int(plan["selection"]["boundary_vintage"])
    valid_from = plan["selection"].get("valid_from")
    valid_to = plan["selection"].get("valid_to")
    selected = [
        item for item in plan.get("artifacts", []) if str(item.get("kind")) in layers
    ]
    if not selected:
        raise ValueError("TIGER plan has no artifacts in its approved load scope")

    artifact_reports: list[dict[str, Any]] = []
    layer_reports: dict[str, dict[str, Any]] = {
        layer: {
            "layer": layer,
            "artifact_count": 0,
            "source_features": 0,
            "staged_rows": 0,
            "staged_geoids": 0,
            "loaded_boundaries": 0,
            "valid_from_mismatches": 0,
            "valid_to_mismatches": 0,
        }
        for layer in layers
    }

    with connect() as conn, conn.cursor() as cur:
        for item in selected:
            layer = str(item["kind"])
            artifact = require_current_artifact(
                str(item["artifact_key"]), label="TIGER", dataset_id="census.tiger"
            )
            local_path = Path(str(artifact.get("local_path") or ""))
            source_features = (
                int(pyogrio.read_info(local_path)["features"])
                if local_path.is_file()
                else 0
            )

            evidence = _artifact_evidence(
                item,
                artifact,
                source_features=source_features,
                official_host_required=official_host_required,
            )
            cur.execute(
                _query("validate_artifact"),
                {
                    "artifact_id": artifact["artifact_id"],
                    "layer": layer,
                    "geography_type": LAYER_INFO[layer]["geography_type"],
                    "vintage": vintage,
                    "valid_from": valid_from,
                    "valid_to": valid_to,
                },
            )
            row = cur.fetchone()
            if row is None:
                raise ValueError(f"No validation row returned for {item['artifact_key']}")
            evidence.update(
                {
                    "staged_rows": int(row["staged_rows"]),
                    "staged_geoids": int(row["staged_geoids"]),
                    "loaded_boundaries": int(row["loaded_boundaries"]),
                    "valid_from_mismatches": int(row["valid_from_mismatches"]),
                    "valid_to_mismatches": int(row["valid_to_mismatches"]),
                }
            )
            evidence["reconciled"] = (
                evidence["source_features"]
                == evidence["staged_rows"]
                == evidence["staged_geoids"]
                == evidence["loaded_boundaries"]
                and evidence["valid_from_mismatches"] == 0
                and evidence["valid_to_mismatches"] == 0
            )
            evidence["passed"] = evidence["passed"] and evidence["reconciled"]
            artifact_reports.append(evidence)

            summary = layer_reports[layer]
            summary["artifact_count"] += 1
            for field in (
                "source_features",
                "staged_rows",
                "staged_geoids",
                "loaded_boundaries",
                "valid_from_mismatches",
                "valid_to_mismatches",
            ):
                summary[field] += int(evidence[field])

    for summary in layer_reports.values():
        summary["reconciled"] = (
            summary["source_features"]
            == summary["staged_rows"]
            == summary["staged_geoids"]
            == summary["loaded_boundaries"]
            and summary["valid_from_mismatches"] == 0
            and summary["valid_to_mismatches"] == 0
        )

    selection_checks: dict[str, bool] = {}
    if plan["selection"].get("package") == "political_district_boundaries":
        selection_checks = {
            "boundary_vintage_2024": vintage == 2024,
            "congress_119": int(plan["selection"].get("congress", 0)) == 119,
            "legislative_year_2024": int(
                plan["selection"].get("legislative_year", 0)
            )
            == 2024,
            "valid_from_2024_01_01": valid_from == "2024-01-01",
            "exact_layers": set(layers) == {"cd119", "sldu", "sldl"},
        }

    total_bytes = sum(int(row["bytes"]) for row in artifact_reports)
    passed = (
        all(row["passed"] for row in artifact_reports)
        and all(row["reconciled"] for row in layer_reports.values())
        and all(selection_checks.values())
    )
    return {
        "passed": passed,
        "selection": {
            "package": plan["selection"].get("package"),
            "boundary_vintage": vintage,
            "valid_from": valid_from,
            "valid_to": valid_to,
            "layers": layers,
            "checks": selection_checks,
        },
        "artifact_count": len(artifact_reports),
        "retained_bytes": total_bytes,
        "layers": [layer_reports[layer] for layer in layers],
        "artifacts": artifact_reports,
    }


def _canonical_fingerprint(snapshot: dict[str, Any]) -> list[tuple[Any, ...]]:
    """Return the count/validity state an idempotent promotion must preserve."""
    return [
        (
            row["layer"],
            row["artifact_count"],
            row["source_features"],
            row["staged_rows"],
            row["staged_geoids"],
            row["loaded_boundaries"],
            row["valid_from_mismatches"],
            row["valid_to_mismatches"],
        )
        for row in snapshot["layers"]
    ]


def validate_tiger_plan(
    plan: dict[str, Any],
    *,
    rerun_load: bool = False,
    official_host_required: bool = True,
) -> dict[str, Any]:
    """Validate a completed TIGER plan and optionally prove promotion idempotency.

    The rerun option never downloads or restages source data. It replays only
    canonical upserts against already-retained/staged artifacts and compares the
    canonical count/validity fingerprint before and after.
    """
    before = _snapshot(plan, official_host_required=official_host_required)
    result: dict[str, Any] = {
        **before,
        "idempotency": {"attempted": False, "stable": None},
    }
    if not rerun_load:
        return result

    replay = deepcopy(plan)
    replay["state"] = "staged"
    promoted = load_tiger(replay)
    after = _snapshot(plan, official_host_required=official_host_required)
    stable = _canonical_fingerprint(before) == _canonical_fingerprint(after)
    result["after_rerun"] = {
        "passed": after["passed"],
        "layers": after["layers"],
    }
    result["idempotency"] = {
        "attempted": True,
        "promoted_rows": promoted,
        "stable": stable,
    }
    result["passed"] = bool(before["passed"] and after["passed"] and stable)
    return result
