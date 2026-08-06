"""PostGIS staging and canonical loading for approved TIGER/Line archives."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from psycopg.types.json import Jsonb

from ..db import connect

LAYER_INFO = {
    "state": ("state", "GEOID", "NAME", "STATEFP", None),
    "county": ("county", "GEOID", "NAME", "STATEFP", "COUNTYFP"),
    "cbsa": ("cbsa", "GEOID", "NAME", None, None),
    "zcta520": ("zcta", "GEOID20", "ZCTA5CE20", None, None),
}


def _scope(plan: dict[str, Any]) -> set[str]:
    layers = set(plan.get("canonical_load_scope", {}).get("layers", []))
    unknown = layers - set(LAYER_INFO)
    if unknown or not layers:
        raise ValueError(
            f"Choose one or more supported TIGER layers: {sorted(LAYER_INFO)}"
        )
    return layers


def _artifact(conn: Any, key: str) -> dict[str, Any]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT artifact_id, local_path FROM ingest.artifact WHERE artifact_key = %s AND status IN ('downloaded', 'skipped')",
            (key,),
        )
        row = cur.fetchone()
    if row is None:
        raise ValueError(f"Required TIGER artifact {key!r} has not been downloaded")
    return row


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
            "TIGER loading requires the spatial extra: `uv sync --extra spatial`"
        ) from exc
    total = 0
    with connect() as conn:
        for item in plan["artifacts"]:
            layer = str(item["kind"])
            if layer not in _scope(plan):
                continue
            artifact = _artifact(conn, item["artifact_key"])
            if update:
                update(f"Reading TIGER {layer} features")
            _geography_type, geoid_key, name_key, state_key, county_key = LAYER_INFO[
                layer
            ]
            info = pyogrio.read_info(Path(artifact["local_path"]))
            for start in range(0, int(info["features"]), 1_000):
                # ZCTA geometry can be large. Bounded reads prevent a complete
                # nationwide layer from occupying all process memory at once.
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
                    geoid = raw.get(geoid_key)
                    if not geoid:
                        raise ValueError(
                            f"TIGER {layer} row {ordinal} has no {geoid_key}"
                        )
                    geometry = feature.geometry
                    if geometry is None or geometry.is_empty:
                        continue
                    rows.append(
                        (
                            artifact["artifact_id"],
                            layer,
                            ordinal,
                            geoid,
                            raw.get(name_key),
                            raw.get(state_key) if state_key else None,
                            raw.get(county_key) if county_key else None,
                            Jsonb(raw),
                            bytes(geometry.wkb),
                        )
                    )
                if rows:
                    with conn.cursor() as cur:
                        cur.executemany(
                            "INSERT INTO stage.tiger_feature (artifact_id, layer, source_ordinal, geoid, name, state_fips, county_fips, raw, geom) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,ST_Transform(ST_SetSRID(ST_GeomFromWKB(%s),4269),4326)) ON CONFLICT DO NOTHING",
                            rows,
                        )
                    total += len(rows)
            conn.commit()
    return total


def load_tiger(
    plan: dict[str, Any], update: Callable[[str], None] | None = None
) -> int:
    """Promote staged features into vintage-specific, artifact-linked boundaries."""
    if plan.get("state") != "staged":
        raise ValueError("TIGER plan must be staged before canonical loading")
    layers = list(_scope(plan))
    vintage = int(plan["selection"]["boundary_vintage"])
    if update:
        update("Creating TIGER geographies and boundaries")
    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            """INSERT INTO core.geography (geography_type, geoid, name, state_fips, county_fips)
          SELECT DISTINCT CASE layer WHEN 'zcta520' THEN 'zcta' ELSE layer END, geoid, name, state_fips, county_fips
          FROM stage.tiger_feature WHERE layer = ANY(%s)
          ON CONFLICT (geography_type, geoid) DO UPDATE SET name=EXCLUDED.name, state_fips=EXCLUDED.state_fips, county_fips=EXCLUDED.county_fips""",
            (layers,),
        )
        cur.execute(
            """INSERT INTO core.geography_boundary (geography_id, boundary_vintage, geom, source_artifact_id)
          SELECT geography.geography_id, %s, feature.geom, feature.artifact_id
          FROM stage.tiger_feature feature JOIN core.geography geography ON geography.geography_type = CASE feature.layer WHEN 'zcta520' THEN 'zcta' ELSE feature.layer END AND geography.geoid = feature.geoid
          WHERE feature.layer = ANY(%s)
          ON CONFLICT (geography_id, boundary_vintage) DO UPDATE SET geom=EXCLUDED.geom, source_artifact_id=EXCLUDED.source_artifact_id""",
            (vintage, layers),
        )
        total = cur.rowcount
        conn.commit()
    return total
