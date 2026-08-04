"""Staging and canonical loading for approved County Business Patterns artifacts."""
from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import Any, Callable
from zipfile import ZipFile

from psycopg.types.json import Jsonb

from ..db import connect


MEMBERS = {"us": "cbp23us.txt", "state": "cbp23st.txt", "county": "cbp23co.txt"}


def _artifact(conn: Any, key: str) -> dict[str, Any]:
    with conn.cursor() as cur:
        cur.execute("SELECT artifact_id, local_path FROM ingest.artifact WHERE artifact_key = %s AND status IN ('downloaded', 'skipped')", (key,))
        row = cur.fetchone()
    if row is None:
        raise ValueError(f"Required CBP artifact {key!r} has not been downloaded")
    return row


def _scope(plan: dict[str, Any]) -> set[str]:
    levels = set(plan.get("canonical_load_scope", {}).get("geography_levels", []))
    unknown = levels - set(MEMBERS)
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
            artifact = _artifact(conn, f"cbp-{year}-cbp23{'co' if level == 'county' else 'st' if level == 'state' else 'us'}")
            member = MEMBERS[level]
            if update: update(f"Staging CBP {level} rows")
            with ZipFile(Path(artifact["local_path"])) as archive, archive.open(member) as binary:
                reader = csv.DictReader(io.TextIOWrapper(binary, encoding="utf-8-sig", newline=""))
                rows = []
                for ordinal, row in enumerate(reader, start=1):
                    rows.append((artifact["artifact_id"], member, ordinal, level, Jsonb(row)))
                    if len(rows) == 2_000:
                        with conn.cursor() as cur:
                            cur.executemany("INSERT INTO stage.cbp_row (artifact_id, source_member, source_ordinal, geography_level, raw) VALUES (%s, %s, %s, %s, %s) ON CONFLICT DO NOTHING", rows)
                        total += len(rows); rows = []
                if rows:
                    with conn.cursor() as cur:
                        cur.executemany("INSERT INTO stage.cbp_row (artifact_id, source_member, source_ordinal, geography_level, raw) VALUES (%s, %s, %s, %s, %s) ON CONFLICT DO NOTHING", rows)
                    total += len(rows)
            conn.commit()
    return total


def _number(value: str | None) -> int | None:
    try:
        return int(value) if value not in (None, "", "N") else None
    except ValueError:
        return None


def load_cbp(plan: dict[str, Any], update: Callable[[str], None] | None = None) -> int:
    """Promote staged CBP rows into idempotent, artifact-linked facts."""
    year = int(plan["selection"]["release_year"])
    total = 0
    with connect() as conn, conn.cursor() as read, conn.cursor() as cur:
        read.execute("SELECT artifact_id, source_member, source_ordinal, geography_level, raw FROM stage.cbp_row WHERE geography_level = ANY(%s) ORDER BY artifact_id, source_member, source_ordinal", (list(_scope(plan)),))
        while rows := read.fetchmany(2_000):
            for entry in rows:
                raw = entry["raw"]
                level = entry["geography_level"]
                if level == "county":
                    geoid, geo_type = f"{raw['fipstate']}{raw['fipscty']}", "county"
                    state, county = raw["fipstate"], raw["fipscty"]
                elif level == "state":
                    geoid, geo_type, state, county = raw["fipstate"], "state", raw["fipstate"], None
                else:
                    geoid, geo_type, state, county = "us", "nation", None, None
                cur.execute("""INSERT INTO core.geography (geography_type, geoid, state_fips, county_fips)
                    VALUES (%s, %s, %s, %s) ON CONFLICT (geography_type, geoid) DO UPDATE SET
                    state_fips = COALESCE(core.geography.state_fips, EXCLUDED.state_fips), county_fips = COALESCE(core.geography.county_fips, EXCLUDED.county_fips)
                    RETURNING geography_id""", (geo_type, geoid, state, county))
                geography_id = cur.fetchone()["geography_id"]
                flags = {key: raw.get(key) for key in ("emp_nf", "qp1_nf", "ap_nf") if raw.get(key)}
                cur.execute("""INSERT INTO fact.business_pattern
                    (release_year, geography_id, naics, legal_form, establishments, employment, first_quarter_payroll, annual_payroll, flags, source_artifact_id, source_member, source_ordinal)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (source_artifact_id, source_member, source_ordinal) DO UPDATE SET
                    establishments=EXCLUDED.establishments, employment=EXCLUDED.employment, first_quarter_payroll=EXCLUDED.first_quarter_payroll, annual_payroll=EXCLUDED.annual_payroll, flags=EXCLUDED.flags""",
                    (year, geography_id, raw.get("naics", ""), raw.get("lfo", ""), _number(raw.get("est")), _number(raw.get("emp")), _number(raw.get("qp1")), _number(raw.get("ap")), Jsonb(flags), entry["artifact_id"], entry["source_member"], entry["source_ordinal"]))
                total += 1
            conn.commit()
            if update: update(f"Loaded {total} CBP facts")
    return total
