"""Save member biography, leadership, contact, social accounts, and district offices.

Statements live in ``sql/query/people/``. A second load of the same bytes does
not rewrite a row. Social accounts and district offices that leave the current
file are removed. People are linked on BioGuide only.
"""

from __future__ import annotations

from functools import cache
from pathlib import Path
from typing import Any
from uuid import UUID

import psycopg

_QUERY_ROOT = Path(__file__).resolve().parents[3] / "sql" / "query" / "people"
PROFILE_FILES = (
    "legislators-current.yaml",
    "legislators-historical.yaml",
    "legislators-social-media.yaml",
    "legislators-district-offices.yaml",
)


@cache
def _query(name: str) -> str:
    """Read a named, version-controlled query (once per process)."""
    return (_QUERY_ROOT / f"{name}.sql").read_text()


def _copy(cur: psycopg.Cursor, table: str, columns: tuple[str, ...], rows: list[tuple[Any, ...]]) -> None:
    if not rows:
        return
    with cur.copy(f"COPY {table} ({', '.join(columns)}) FROM STDIN") as copy:
        for row in rows:
            copy.write_row(row)


def _changed(cur: psycopg.Cursor, name: str, params: dict[str, Any] | None = None) -> int:
    cur.execute(_query(name), params or {})
    return len(cur.fetchall()) if cur.description else cur.rowcount


def publish_legislator_profile(
    conn: psycopg.Connection,
    *,
    people: list[tuple[Any, ...]],
    leadership: list[tuple[Any, ...]],
    social: list[tuple[Any, ...]],
    offices: list[tuple[Any, ...]],
    names: list[tuple[Any, ...]],
    sources: list[tuple[Any, ...]],
) -> dict[str, Any]:
    """Write one member-profile snapshot. ``rows`` are already parsed.

    Unknown BioGuide ids on a social account or a district office stay on the
    row with an empty person link and are listed here. They do not create a person.
    """
    with conn.transaction():
        cur = conn.cursor()
        cur.execute("SELECT pg_advisory_xact_lock(hashtextextended('congress.legislators:profile', 0))")
        for statement in _query("create_profile_stage").split(";"):
            if statement.strip():
                cur.execute(statement)
        _copy(
            cur,
            "profile_person",
            ("bioguide", "source_file", "artifact_id", "run_id", "birthday", "gender", "record"),
            people,
        )
        _copy(
            cur,
            "profile_leadership",
            ("bioguide", "chamber", "title", "start_date", "end_date", "artifact_id", "run_id"),
            leadership,
        )
        _copy(
            cur,
            "profile_social",
            ("bioguide", "network", "handle", "external_id", "artifact_id", "run_id", "record"),
            social,
        )
        _copy(
            cur,
            "profile_office",
            (
                "bioguide",
                "office_key",
                "address",
                "building",
                "suite",
                "city",
                "state",
                "zip",
                "phone",
                "fax",
                "hours",
                "latitude",
                "longitude",
                "artifact_id",
                "run_id",
                "record",
            ),
            offices,
        )
        _copy(
            cur,
            "profile_name",
            (
                "bioguide",
                "name_kind",
                "full_name",
                "given_name",
                "family_name",
                "source_vintage",
                "artifact_id",
                "run_id",
            ),
            names,
        )
        _copy(
            cur,
            "profile_source",
            ("source_file", "member_key", "bioguide", "record", "artifact_id", "run_id"),
            sources,
        )
        people_updated = _changed(cur, "upsert_profile_people")
        source_changed = _changed(cur, "upsert_profile_source_records")
        leadership_changed = _changed(cur, "upsert_profile_leadership")
        social_changed = _changed(cur, "upsert_profile_social")
        offices_changed = _changed(cur, "upsert_profile_offices")
        names_changed = _changed(cur, "upsert_profile_names")
        cur.execute("SELECT set_config('opendiscourse.resolver', 'on', true)")
        cur.execute(_query("clear_profile_name_pointers"))
        names_removed = _changed(cur, "delete_absent_profile_names")
        sources_removed = _changed(
            cur, "delete_absent_profile_source_records", {"files": list(PROFILE_FILES)}
        )
        leadership_removed = _changed(cur, "delete_absent_profile_leadership")
        social_removed = _changed(cur, "delete_absent_profile_social")
        offices_removed = _changed(cur, "delete_absent_profile_offices")
        cur.execute(_query("profile_unknown_bioguides"))
        unknown = [dict(row) for row in cur.fetchall()]
    return {
        "profile_people_updated": people_updated,
        "profile_sources_changed": source_changed,
        "profile_sources_removed": sources_removed,
        "leadership_changed": leadership_changed,
        "leadership_removed": leadership_removed,
        "social_changed": social_changed,
        "social_removed": social_removed,
        "offices_changed": offices_changed,
        "offices_removed": offices_removed,
        "profile_names_changed": names_changed,
        "profile_names_removed": names_removed,
        "profile_unknown_bioguides": unknown,
    }


def artifact_id(value: UUID | str) -> UUID:
    """COPY needs a uuid, not a string."""
    return value if isinstance(value, UUID) else UUID(str(value))
