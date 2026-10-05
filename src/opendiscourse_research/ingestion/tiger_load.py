"""PostGIS staging and canonical loading for approved TIGER/Line archives."""

from __future__ import annotations

from collections.abc import Callable
from functools import cache
from pathlib import Path
from typing import Any

from psycopg.types.json import Jsonb

from ..db import connect
from ..repositories.artifacts import require_current_artifact
from ..repositories.names import upsert_geography_name_sources

_QUERY_ROOT = Path(__file__).resolve().parents[3] / "sql" / "query" / "census" / "tiger"

LAYER_INFO: dict[str, dict[str, Any]] = {
    "state": {
        "geography_type": "state",
        "geoid": "GEOID",
        "name": "NAME",
        "state": "STATEFP",
        "county": None,
        "name_kind": "short",
        "expected": {},
    },
    "county": {
        "geography_type": "county",
        "geoid": "GEOID",
        "name": "NAME",
        "state": "STATEFP",
        "county": "COUNTYFP",
        "name_kind": "short",
        "expected": {},
    },
    "cbsa": {
        "geography_type": "cbsa",
        "geoid": "GEOID",
        "name": "NAME",
        "state": None,
        "county": None,
        "name_kind": "short",
        "expected": {},
    },
    "zcta510": {
        "geography_type": "zcta",
        "geoid": "GEOID10",
        "name": "ZCTA5CE10",
        "state": None,
        "county": None,
        "name_kind": None,
        "expected": {},
    },
    "zcta520": {
        "geography_type": "zcta",
        "geoid": "GEOID20",
        "name": "ZCTA5CE20",
        "state": None,
        "county": None,
        "name_kind": None,
        "expected": {},
    },
    "cd119": {
        "geography_type": "congressional_district",
        "geoid": "GEOID",
        "name": "NAMELSAD",
        "state": "STATEFP",
        "county": None,
        "name_kind": "full",
        "expected": {"CDSESSN": "119"},
    },
    "sldu": {
        "geography_type": "sldu",
        "geoid": "GEOID",
        "name": "NAMELSAD",
        "state": "STATEFP",
        "county": None,
        "name_kind": "full",
        "expected": {"LSY": "2024"},
    },
    "sldl": {
        "geography_type": "sldl",
        "geoid": "GEOID",
        "name": "NAMELSAD",
        "state": "STATEFP",
        "county": None,
        "name_kind": "full",
        "expected": {"LSY": "2024"},
    },
}


@cache
def _query(name: str) -> str:
    """Read a version-controlled TIGER query once per process."""
    return (_QUERY_ROOT / f"{name}.sql").read_text()


def _scope(plan: dict[str, Any]) -> set[str]:
    layers = set(plan.get("canonical_load_scope", {}).get("layers", []))
    unknown = layers - set(LAYER_INFO)
    if unknown or not layers:
        raise ValueError(
            f"Choose one or more supported TIGER layers: {sorted(LAYER_INFO)}"
        )
    return layers


def _artifact(key: str) -> dict[str, Any]:
    """Return the current downloaded TIGER artifact version."""
    return require_current_artifact(key, label="TIGER")


def _validate_fields(layer: str, raw: dict[str, str | None], ordinal: int) -> None:
    info = LAYER_INFO[layer]
    for field, expected in info["expected"].items():
        if raw.get(field) != expected:
            raise ValueError(
                f"TIGER {layer} row {ordinal} has {field}={raw.get(field)!r}; "
                f"expected {expected!r}"
            )


def stage_tiger(
    plan: dict[str, Any], update: Callable[[str], None] | None = None
) -> int:
    """Parse approved shapefiles into source-shaped PostGIS staging features."""
    if plan.get("state") != "downloaded":
        raise ValueError("TIGER plan must be downloaded before staging")
    try:
        import pyogrio
    except ImportError as exc:
        raise RuntimeError(
            "TIGER loading requires the spatial extra: uv sync --extra spatial"
        ) from exc

    total = 0
    scope = _scope(plan)
    with connect() as conn:
        for item in plan["artifacts"]:
            layer = str(item["kind"])
            if layer not in scope:
                continue
            artifact = _artifact(item["artifact_key"])
            if update:
                update(f"Reading TIGER {layer} features")
            info = LAYER_INFO[layer]
            source_info = pyogrio.read_info(Path(artifact["local_path"]))
            source_features = int(source_info["features"])
            parsed = 0
            for start in range(0, source_features, 1_000):
                frame = pyogrio.read_dataframe(
                    Path(artifact["local_path"]),
                    skip_features=start,
                    max_features=1_000,
                )
                rows = []
                for offset, (_, feature) in enumerate(frame.iterrows()):
                    ordinal = start + offset + 1
                    raw = {
                        str(key): (None if value is None else str(value))
                        for key, value in feature.drop(labels="geometry").items()
                    }
                    _validate_fields(layer, raw, ordinal)
                    geoid = raw.get(info["geoid"])
                    if not geoid:
                        raise ValueError(
                            f"TIGER {layer} row {ordinal} has no {info['geoid']}"
                        )
                    geometry = feature.geometry
                    if geometry is None or geometry.is_empty:
                        raise ValueError(
                            f"TIGER {layer} row {ordinal} has empty geometry"
                        )
                    rows.append(
                        (
                            artifact["artifact_id"],
                            layer,
                            ordinal,
                            geoid,
                            raw.get(info["name"]),
                            raw.get(info["state"]) if info["state"] else None,
                            raw.get(info["county"]) if info["county"] else None,
                            Jsonb(raw),
                            bytes(geometry.wkb),
                        )
                    )
                if rows:
                    with conn.cursor() as cur:
                        cur.executemany(_query("insert_stage"), rows)
                    parsed += len(rows)
            if parsed != source_features:
                raise ValueError(
                    f"TIGER {layer} parsed {parsed} features; source reports "
                    f"{source_features}"
                )
            conn.commit()
            with conn.cursor() as cur:
                cur.execute(
                    _query("stage_count"),
                    {"artifact_id": artifact["artifact_id"], "layer": layer},
                )
                staged = int(cur.fetchone()["row_count"])
            if staged != source_features:
                raise ValueError(
                    f"TIGER {layer} staged {staged} rows; source reports "
                    f"{source_features}"
                )
            total += parsed
    return total


def load_tiger(
    plan: dict[str, Any], update: Callable[[str], None] | None = None
) -> int:
    """Promote staged features into vintage-specific, artifact-linked boundaries."""
    if plan.get("state") != "staged":
        raise ValueError("TIGER plan must be staged before canonical loading")
    layers = sorted(_scope(plan))
    vintage = int(plan["selection"]["boundary_vintage"])
    valid_from = plan["selection"].get("valid_from")
    valid_to = plan["selection"].get("valid_to")
    if update:
        update("Creating TIGER geographies and boundaries")

    artifact_ids = [
        _artifact(item["artifact_key"])["artifact_id"]
        for item in plan["artifacts"]
        if str(item["kind"]) in layers
    ]
    if not artifact_ids:
        raise ValueError("TIGER plan resolved no approved artifacts")

    with connect() as conn, conn.cursor() as cur:
        params = {"layers": layers, "artifact_ids": artifact_ids}
        cur.execute(_query("upsert_geographies"), params)
        cur.fetchall()

        cur.execute(_query("name_rows"), params)
        assertions = []
        for row in cur.fetchall():
            name_kind = LAYER_INFO[row["layer"]]["name_kind"]
            if name_kind is None:
                continue
            assertions.append(
                {
                    "geography_id": row["geography_id"],
                    "name_kind": name_kind,
                    "name": row["name"],
                    "dataset_id": "census.tiger",
                    "source_vintage": str(vintage),
                    "artifact_id": row["artifact_id"],
                    "payload_id": None,
                    "run_id": None,
                }
            )
        upsert_geography_name_sources(cur, assertions)

        boundary_params = {
            **params,
            "vintage": vintage,
            "valid_from": valid_from,
            "valid_to": valid_to,
        }
        cur.execute(_query("upsert_boundaries"), boundary_params)
        total = len(cur.fetchall())

        cur.execute(_query("reconciliation"), boundary_params)
        reconciliation = cur.fetchall()
        for row in reconciliation:
            if int(row["staged_rows"]) != int(row["loaded_boundaries"]):
                raise ValueError(
                    f"TIGER {row['layer']} reconciliation failed: "
                    f"{row['staged_rows']} staged rows, "
                    f"{row['loaded_boundaries']} loaded boundaries"
                )
        conn.commit()
    return total
