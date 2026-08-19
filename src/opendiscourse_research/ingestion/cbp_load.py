"""Staging and canonical loading for approved County Business Patterns artifacts."""

from __future__ import annotations

import csv
import io
from collections.abc import Callable
from pathlib import Path
from typing import Any
from zipfile import ZipFile

from psycopg.types.json import Jsonb
from sqlalchemy import select

from ..db import connect, session
from ..models.catalog import artifact_table

LEVELS = ("us", "state", "county")


def _level_suffix(level: str) -> str:
    return "co" if level == "county" else "st" if level == "state" else "us"


def _member_name(year: int, level: str) -> str:
    """Return the .txt member name inside that year's ZIP for one geography level."""
    return f"cbp{year % 100:02d}{_level_suffix(level)}.txt"


def _artifact_key(year: int, level: str) -> str:
    """Match cbp_bulk.py's artifact_key: f"cbp-{year}-{filename stem}"."""
    return f"cbp-{year}-cbp{year % 100:02d}{_level_suffix(level)}"


def _resolve_member(archive: ZipFile, expected: str) -> str:
    """Match a CBP ZIP member case-insensitively.

    Confirmed live: the 2009 US-level archive stores its member as
    `Cbp09us.txt` (capitalized) while every other year checked uses
    lowercase -- a one-year publishing quirk, not a naming convention to
    special-case by year.
    """
    names = archive.namelist()
    if expected in names:
        return expected
    lowered = {name.lower(): name for name in names}
    match = lowered.get(expected.lower())
    if match is None:
        raise KeyError(f"No member matching {expected!r} in {names!r}")
    return match


def _artifact(key: str) -> dict[str, Any]:
    """Return a downloaded CBP artifact through immutable typed evidence storage."""
    table = artifact_table()
    with session() as active_session:
        row = active_session.execute(
            select(table.c.artifact_id, table.c.local_path).where(
                table.c.artifact_key == key,
                table.c.status.in_(("downloaded", "skipped")),
            )
        ).mappings().first()
    if row is None:
        raise ValueError(f"Required CBP artifact {key!r} has not been downloaded")
    return dict(row)


def _scope(plan: dict[str, Any]) -> set[str]:
    levels = set(plan.get("canonical_load_scope", {}).get("geography_levels", []))
    unknown = levels - set(LEVELS)
    if unknown:
        raise ValueError(f"Unsupported CBP geography levels: {sorted(unknown)}")
    if not levels:
        raise ValueError("Approved CBP plan is missing canonical geography levels")
    return levels


def stage_cbp(plan: dict[str, Any], update: Callable[[str], None] | None = None) -> int:
    """Parse approved CBP ZIP members into immutable provider-shaped staging rows."""
    if plan.get("state") != "downloaded":
        raise ValueError("CBP plan must be downloaded before staging")
    year = int(plan["selection"]["release_year"])
    total = 0
    with connect() as conn:
        for level in sorted(_scope(plan)):
            artifact = _artifact(_artifact_key(year, level))
            member = _member_name(year, level)
            if update:
                update(f"Staging CBP {level} rows")
            with ZipFile(Path(artifact["local_path"])) as archive:
                member = _resolve_member(archive, member)
                with archive.open(member) as binary:
                    reader = csv.DictReader(
                        io.TextIOWrapper(binary, encoding="utf-8-sig", newline="")
                    )
                    rows = []
                    for ordinal, row in enumerate(reader, start=1):
                        # Confirmed live: the 2015 county-level file uses
                        # uppercase column headers (NAICS, FIPSTATE, ...)
                        # while every other year checked uses lowercase --
                        # load_cbp's raw->>'naics' style lookups are
                        # case-sensitive, so an unnormalized row silently
                        # produced NULL for every field, cascading into a
                        # NOT NULL violation on canonical load. Normalizing
                        # here keeps `raw` consistent regardless of a given
                        # year's source casing.
                        normalized = {key.lower(): value for key, value in row.items()}
                        rows.append(
                            (
                                artifact["artifact_id"],
                                member,
                                ordinal,
                                level,
                                Jsonb(normalized),
                            )
                        )
                        if len(rows) == 2_000:
                            with conn.cursor() as cur:
                                cur.executemany(
                                    "INSERT INTO stage.cbp_row (artifact_id, source_member, source_ordinal, geography_level, raw) VALUES (%s, %s, %s, %s, %s) ON CONFLICT DO NOTHING",
                                    rows,
                                )
                            total += len(rows)
                            rows = []
                    if rows:
                        with conn.cursor() as cur:
                            cur.executemany(
                                "INSERT INTO stage.cbp_row (artifact_id, source_member, source_ordinal, geography_level, raw) VALUES (%s, %s, %s, %s, %s) ON CONFLICT DO NOTHING",
                                rows,
                            )
                        total += len(rows)
            conn.commit()
    return total


def load_cbp(plan: dict[str, Any], update: Callable[[str], None] | None = None) -> int:
    """Promote staged CBP rows into idempotent, artifact-linked facts."""
    if plan.get("state") != "staged":
        raise ValueError("CBP plan must be staged before canonical loading")
    year = int(plan["selection"]["release_year"])
    levels = list(_scope(plan))
    if update:
        update("Creating CBP geographies")
    with connect() as conn, conn.cursor() as cur:
        # Scoped to this plan's own artifacts -- without this, the query
        # pulled from every CBP year ever staged into stage.cbp_row (no
        # per-plan partition), the same class of bug fixed in load_tiger:
        # each additional year staged makes the next year's load scan
        # more unrelated data and contend for the same core.geography rows
        # with whatever else is concurrently loading. Confirmed live via
        # pg_stat_activity: an unscoped 2012 load held long-running locks
        # that blocked a concurrent 2011 retry and even a schema migration.
        artifact_ids = [
            _artifact(_artifact_key(year, level))["artifact_id"]
            for level in levels
        ]
        cur.execute(
            """WITH source AS (
              SELECT geography_level, raw FROM stage.cbp_row WHERE geography_level = ANY(%s) AND artifact_id = ANY(%s)
            ), geographies AS (
              SELECT DISTINCT CASE geography_level WHEN 'county' THEN 'county' WHEN 'state' THEN 'state' ELSE 'nation' END AS geography_type,
                CASE geography_level WHEN 'county' THEN (raw->>'fipstate') || (raw->>'fipscty') WHEN 'state' THEN raw->>'fipstate' ELSE 'us' END AS geoid,
                CASE WHEN geography_level IN ('county', 'state') THEN raw->>'fipstate' END AS state_fips,
                CASE WHEN geography_level = 'county' THEN raw->>'fipscty' END AS county_fips FROM source
            ) INSERT INTO core.geography (geography_type, geoid, state_fips, county_fips)
            SELECT geography_type, geoid, state_fips, county_fips FROM geographies
            ON CONFLICT (geography_type, geoid) DO UPDATE SET state_fips = COALESCE(core.geography.state_fips, EXCLUDED.state_fips), county_fips = COALESCE(core.geography.county_fips, EXCLUDED.county_fips)""",
            (levels, artifact_ids),
        )
        if update:
            update("Promoting staged CBP rows to canonical facts")
        cur.execute(
            """WITH source AS (
              SELECT artifact_id, source_member, source_ordinal, geography_level, raw FROM stage.cbp_row WHERE geography_level = ANY(%s) AND artifact_id = ANY(%s)
            ) INSERT INTO fact.business_pattern
              (release_year, geography_id, naics, legal_form, establishments, employment, first_quarter_payroll, annual_payroll, flags, source_artifact_id, source_member, source_ordinal)
            SELECT %s, geography.geography_id, source.raw->>'naics', COALESCE(source.raw->>'lfo', ''),
              CASE WHEN source.raw->>'est' ~ '^-?[0-9]+$' THEN (source.raw->>'est')::bigint END,
              CASE WHEN source.raw->>'emp' ~ '^-?[0-9]+$' THEN (source.raw->>'emp')::bigint END,
              CASE WHEN source.raw->>'qp1' ~ '^-?[0-9]+$' THEN (source.raw->>'qp1')::numeric END,
              CASE WHEN source.raw->>'ap' ~ '^-?[0-9]+$' THEN (source.raw->>'ap')::numeric END,
              jsonb_strip_nulls(jsonb_build_object('emp_nf', source.raw->>'emp_nf', 'qp1_nf', source.raw->>'qp1_nf', 'ap_nf', source.raw->>'ap_nf')),
              source.artifact_id, source.source_member, source.source_ordinal
            FROM source JOIN core.geography geography ON geography.geography_type = CASE source.geography_level WHEN 'county' THEN 'county' WHEN 'state' THEN 'state' ELSE 'nation' END
              AND geography.geoid = CASE source.geography_level WHEN 'county' THEN (source.raw->>'fipstate') || (source.raw->>'fipscty') WHEN 'state' THEN source.raw->>'fipstate' ELSE 'us' END
            ON CONFLICT (source_artifact_id, source_member, source_ordinal) DO UPDATE SET establishments = EXCLUDED.establishments,
              employment = EXCLUDED.employment, first_quarter_payroll = EXCLUDED.first_quarter_payroll, annual_payroll = EXCLUDED.annual_payroll, flags = EXCLUDED.flags""",
            (levels, artifact_ids, year),
        )
        total = cur.rowcount
        conn.commit()
    return total
