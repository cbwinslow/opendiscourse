"""Staging and canonical loading for approved Population Estimates Program artifacts."""

from __future__ import annotations

import csv
from collections.abc import Callable
from pathlib import Path
from typing import Any

from psycopg.types.json import Jsonb

from ..db import connect


def _scope(plan: dict[str, Any]) -> set[str]:
    levels = set(plan.get("canonical_load_scope", {}).get("geography_levels", []))
    unknown = levels - {"nation", "state", "county"}
    if unknown or not levels:
        raise ValueError(
            f"Choose one or more supported PEP geography levels (nation, state, county); got {sorted(unknown)}"
        )
    return levels


def _artifact(conn: Any, key: str) -> dict[str, Any]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT artifact_id, local_path FROM ingest.artifact WHERE artifact_key = %s AND status IN ('downloaded', 'skipped')",
            (key,),
        )
        row = cur.fetchone()
    if row is None:
        raise ValueError(f"Required PEP artifact {key!r} has not been downloaded")
    return row


def stage_pep(plan: dict[str, Any], update: Callable[[str], None] | None = None) -> int:
    """Stage source-shaped PEP CSV rows, retaining each artifact and row ordinal."""
    if plan.get("state") != "downloaded":
        raise ValueError("PEP plan must be downloaded before staging")
    year = int(plan["selection"]["vintage"])
    requested = _scope(plan)
    artifacts = [
        ("state", f"pep-{year}-state-totals"),
        ("county", f"pep-{year}-county-totals"),
    ]
    total = 0
    with connect() as conn:
        for level, key in artifacts:
            if level not in requested and not (
                level == "state" and "nation" in requested
            ):
                continue
            artifact = _artifact(conn, key)
            if update:
                update(f"Staging PEP {level} totals")
            # PEP county names include characters such as ñ; published CSVs use
            # the single-byte Latin-1 encoding rather than UTF-8.
            with Path(artifact["local_path"]).open(
                encoding="latin-1", newline=""
            ) as source:
                rows = []
                for ordinal, row in enumerate(csv.DictReader(source), start=1):
                    sumlev = row.get("SUMLEV", "")
                    geography_level = (
                        "county"
                        if sumlev == "050"
                        else "state"
                        if sumlev == "040"
                        else "nation"
                        if sumlev == "010"
                        else "other"
                    )
                    if geography_level not in requested:
                        continue
                    rows.append(
                        (
                            artifact["artifact_id"],
                            Path(artifact["local_path"]).name,
                            ordinal,
                            geography_level,
                            Jsonb(row),
                        )
                    )
                    if len(rows) == 2_000:
                        with conn.cursor() as cur:
                            cur.executemany(
                                "INSERT INTO stage.pep_row (artifact_id, source_member, source_ordinal, geography_level, raw) VALUES (%s, %s, %s, %s, %s) ON CONFLICT DO NOTHING",
                                rows,
                            )
                        total += len(rows)
                        rows = []
                if rows:
                    with conn.cursor() as cur:
                        cur.executemany(
                            "INSERT INTO stage.pep_row (artifact_id, source_member, source_ordinal, geography_level, raw) VALUES (%s, %s, %s, %s, %s) ON CONFLICT DO NOTHING",
                            rows,
                        )
                    total += len(rows)
            conn.commit()
    return total


def load_pep(plan: dict[str, Any], update: Callable[[str], None] | None = None) -> int:
    """Promote staged PEP annual estimates without co-mingling release vintages."""
    if plan.get("state") != "staged":
        raise ValueError("PEP plan must be staged before canonical loading")
    vintage = int(plan["selection"]["vintage"])
    levels = list(_scope(plan))
    if update:
        update("Creating PEP geographies")
    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            """WITH source AS (
            SELECT geography_level, raw FROM stage.pep_row WHERE geography_level = ANY(%s)
          ), geographies AS (
            SELECT DISTINCT geography_level AS geography_type,
              CASE geography_level WHEN 'county' THEN lpad(raw->>'STATE', 2, '0') || lpad(raw->>'COUNTY', 3, '0') WHEN 'state' THEN lpad(raw->>'STATE', 2, '0') ELSE 'us' END AS geoid,
              COALESCE(raw->>'CTYNAME', raw->>'NAME') AS name,
              CASE WHEN geography_level IN ('state', 'county') THEN lpad(raw->>'STATE', 2, '0') END AS state_fips,
              CASE WHEN geography_level = 'county' THEN lpad(raw->>'COUNTY', 3, '0') END AS county_fips
            FROM source
          ) INSERT INTO core.geography (geography_type, geoid, name, state_fips, county_fips)
          SELECT geography_type, geoid, name, state_fips, county_fips FROM geographies
          ON CONFLICT (geography_type, geoid) DO UPDATE SET name = COALESCE(core.geography.name, EXCLUDED.name), state_fips = COALESCE(core.geography.state_fips, EXCLUDED.state_fips), county_fips = COALESCE(core.geography.county_fips, EXCLUDED.county_fips)""",
            (levels,),
        )
        if update:
            update("Promoting staged PEP annual estimates")
        cur.execute(
            """WITH source AS (
            SELECT artifact_id, source_member, source_ordinal, geography_level, raw FROM stage.pep_row WHERE geography_level = ANY(%s)
          ), estimates AS (
            SELECT source.*, substring(field.key from '^POPESTIMATE([0-9]{4})$')::integer AS estimate_year, value::bigint AS population
            FROM source CROSS JOIN LATERAL jsonb_each_text(raw) AS field(key, value)
            WHERE field.key ~ '^POPESTIMATE[0-9]{4}$' AND field.value ~ '^-?[0-9]+$'
          ) INSERT INTO fact.population_estimate
            (release_vintage, estimate_year, geography_id, population, source_artifact_id, source_member, source_ordinal)
          SELECT %s, estimates.estimate_year, geography.geography_id, estimates.population, estimates.artifact_id, estimates.source_member, estimates.source_ordinal
          FROM estimates JOIN core.geography geography ON geography.geography_type = estimates.geography_level
            AND geography.geoid = CASE estimates.geography_level WHEN 'county' THEN lpad(estimates.raw->>'STATE', 2, '0') || lpad(estimates.raw->>'COUNTY', 3, '0') WHEN 'state' THEN lpad(estimates.raw->>'STATE', 2, '0') ELSE 'us' END
          ON CONFLICT (source_artifact_id, source_member, source_ordinal, estimate_year) DO UPDATE SET population = EXCLUDED.population""",
            (levels, vintage),
        )
        total = cur.rowcount
        conn.commit()
    return total
