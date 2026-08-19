"""PostGIS staging and canonical loading for approved TIGER/Line archives."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from psycopg.types.json import Jsonb
from sqlalchemy import select

from ..db import connect, session
from ..models.catalog import artifact_table

LAYER_INFO = {
    "state": ("state", "GEOID", "NAME", "STATEFP", None),
    "county": ("county", "GEOID", "NAME", "STATEFP", "COUNTYFP"),
    "cbsa": ("cbsa", "GEOID", "NAME", None, None),
    # ZCTA boundaries are redefined each decennial census, and Census
    # vintage-suffixes the shapefile's own attribute column names to match
    # (confirmed live via the 2019 file's DBF header: GEOID10/ZCTA5CE10, not
    # GEOID/ZCTA5CE) -- both vintages load into the same "zcta" geography
    # type/table, just from differently-named source columns.
    "zcta510": ("zcta", "GEOID10", "ZCTA5CE10", None, None),
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


def _artifact(key: str) -> dict[str, Any]:
    """Return a downloaded TIGER artifact through immutable typed evidence storage."""
    table = artifact_table()
    with session() as active_session:
        row = active_session.execute(
            select(table.c.artifact_id, table.c.local_path).where(
                table.c.artifact_key == key,
                table.c.status.in_(("downloaded", "skipped")),
            )
        ).mappings().first()
    if row is None:
        raise ValueError(f"Required TIGER artifact {key!r} has not been downloaded")
    return dict(row)


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
            artifact = _artifact(item["artifact_key"])
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
        # Scoped to this plan's own artifacts -- without this, the query pulled
        # from every vintage ever staged into stage.tiger_feature (this table
        # has no per-plan partition). Confirmed live: once a second vintage
        # (2016) was staged alongside the first (2020), CBSA delineations
        # renamed between them (e.g. "Atlanta-Sandy Springs-Alpharetta, GA" ->
        # "...-Roswell, GA") produced two rows for the same (geography_type,
        # geoid) in one INSERT's SELECT DISTINCT, which Postgres rejects for
        # ON CONFLICT DO UPDATE ("cannot affect row a second time") -- this
        # was latent and never triggered while only one vintage existed.
        artifact_ids = [
            _artifact(item["artifact_key"])["artifact_id"]
            for item in plan["artifacts"]
            if str(item["kind"]) in layers
        ]
        cur.execute(
            """INSERT INTO core.geography (geography_type, geoid, name, state_fips, county_fips)
          SELECT DISTINCT CASE WHEN layer IN ('zcta510', 'zcta520') THEN 'zcta' ELSE layer END, geoid, name, state_fips, county_fips
          FROM stage.tiger_feature WHERE layer = ANY(%s) AND artifact_id = ANY(%s)
          ON CONFLICT (geography_type, geoid) DO UPDATE SET name=EXCLUDED.name, state_fips=EXCLUDED.state_fips, county_fips=EXCLUDED.county_fips""",
            (layers, artifact_ids),
        )
        cur.execute(
            """INSERT INTO core.geography_boundary (geography_id, boundary_vintage, geom, source_artifact_id)
          SELECT geography.geography_id, %s, feature.geom, feature.artifact_id
          FROM stage.tiger_feature feature JOIN core.geography geography ON geography.geography_type = CASE WHEN feature.layer IN ('zcta510', 'zcta520') THEN 'zcta' ELSE feature.layer END AND geography.geoid = feature.geoid
          WHERE feature.layer = ANY(%s) AND feature.artifact_id = ANY(%s)
          ON CONFLICT (geography_id, boundary_vintage) DO UPDATE SET geom=EXCLUDED.geom, source_artifact_id=EXCLUDED.source_artifact_id""",
            (vintage, layers, artifact_ids),
        )
        total = cur.rowcount
        conn.commit()
    return total
