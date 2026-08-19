"""Read-only validation for an isolated restored OpenStates provider database."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import psycopg
from psycopg.conninfo import conninfo_to_dict
from psycopg.rows import dict_row

from .config import settings
from .db import connect
from .openstatessnapshot import REQUIRED_VOTE_TABLES

_DATABASE_NAME = re.compile(r"^[a-z][a-z0-9_]{0,62}$")
_REQUIRED_CONGRESSES = {"118", "119"}
_COMPATIBILITY_VIEWS_SQL = (
    Path(__file__).resolve().parents[2]
    / "sql"
    / "query"
    / "legislation"
    / "publish_openstates_compatibility_views.sql"
)


def stage_connection(database: str) -> psycopg.Connection:
    """Open a local peer-authenticated connection to a validated stage database."""
    if not _DATABASE_NAME.fullmatch(database):
        raise ValueError(
            "stage database name must be lowercase letters, digits, and underscores"
        )
    parameters = conninfo_to_dict(settings.database_url)
    parameters["dbname"] = database
    return psycopg.connect(**parameters, row_factory=dict_row)


def build_stage_validation(
    database: str,
    tables: set[str],
    vote_counts: list[dict[str, Any]],
    extensions: list[str],
) -> dict[str, Any]:
    """Build a serializable stage-validation report from read-only observations."""
    missing = sorted(REQUIRED_VOTE_TABLES - tables)
    reported_congresses = {str(row.get("congress")) for row in vote_counts}
    missing_congresses = sorted(_REQUIRED_CONGRESSES - reported_congresses)
    populated = all(
        int(row.get("source_events") or 0) > 0
        and int(row.get("source_keys") or 0) > 0
        and int(row.get("source_person_votes") or 0) > 0
        for row in vote_counts
    )
    return {
        "schema": 1,
        "kind": "openstates_stage_validation",
        "generated_at": datetime.now(UTC).isoformat(),
        "database": database,
        "read_only": True,
        "table_count": len(tables),
        "missing_required_tables": missing,
        "missing_congresses": missing_congresses,
        "extensions": extensions,
        "vote_counts": vote_counts,
        "valid": not missing and not missing_congresses and populated,
        "next": (
            "Review this report before atomically changing the openstates_local FDW server."
            if not missing and not missing_congresses and populated
            else "Do not remap the FDW; staging validation is incomplete."
        ),
    }


def validate_openstates_stage(database: str) -> dict[str, Any]:
    """Inspect a completed stage database without changing source or canonical state."""
    with stage_connection(database) as conn, conn.cursor() as cur:
        cur.execute("SET TRANSACTION READ ONLY")
        cur.execute(
            """SELECT table_schema || '.' || table_name AS relation
            FROM information_schema.tables
            WHERE table_schema = 'public' AND table_type = 'BASE TABLE'"""
        )
        tables = {row["relation"] for row in cur.fetchall()}
        cur.execute(
            """SELECT s.identifier AS congress,
                      count(*) AS source_events,
                      count(DISTINCT v.identifier) AS source_keys,
                      min(v.updated_at) AS source_updated_at_min,
                      max(v.updated_at) AS source_updated_at_max
               FROM public.opencivicdata_voteevent v
               JOIN public.opencivicdata_legislativesession s
                 ON s.id = v.legislative_session_id
               WHERE s.identifier IN ('118', '119')
               GROUP BY s.identifier
               ORDER BY s.identifier"""
        )
        vote_counts = [dict(row) for row in cur.fetchall()]
        for row in vote_counts:
            cur.execute(
                """SELECT count(*) AS source_person_votes
                FROM public.opencivicdata_personvote pv
                WHERE pv.vote_event_id IN (
                  SELECT v.id
                  FROM public.opencivicdata_voteevent v
                  JOIN public.opencivicdata_legislativesession s
                    ON s.id = v.legislative_session_id
                  WHERE s.identifier = %s
                )""",
                (row["congress"],),
            )
            row.update(dict(cur.fetchone()))
        cur.execute("SELECT extname FROM pg_extension ORDER BY extname")
        extensions = [row["extname"] for row in cur.fetchall()]
        conn.rollback()
    result = build_stage_validation(database, tables, vote_counts, extensions)
    target = (
        Path(settings.data_root).expanduser().resolve().parent
        / "meta"
        / "validate"
        / "openstates"
        / f"{database}.json"
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps(result, indent=2, sort_keys=True, default=str) + "\n"
    )
    temporary.replace(target)
    result["report"] = str(target)
    return result


def publish_openstates_compatibility_views() -> None:
    """Publish project-owned views after an approved OpenStates FDW remap."""
    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT to_regclass('openstates_source.opencivicdata_person'), "
            "to_regclass('openstates_source.opencivicdata_bill'), "
            "to_regclass('openstates_source.opencivicdata_legislativesession'), "
            "to_regclass('openstates_source.opencivicdata_jurisdiction')"
        )
        if any(value is None for value in cur.fetchone().values()):
            raise ValueError(
                "OpenStates FDW is not provisioned; remap and validate it before publishing views"
            )
        cur.execute(_COMPATIBILITY_VIEWS_SQL.read_text())
