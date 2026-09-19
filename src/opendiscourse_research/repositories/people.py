"""Set-based promotion of legislator identity into ``core.person``.

SQL only. People are matched by an existing BioGuide identifier and nothing
else; identifiers already owned by another person are reported, never moved.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import psycopg

_QUERY_ROOT = Path(__file__).resolve().parents[3] / "sql" / "query" / "people"

STAGE_COLUMNS = (
    "bioguide",
    "new_person_id",
    "full_name",
    "given_name",
    "family_name",
    "namespace",
    "external_id",
    "artifact_id",
)


def _query(name: str) -> str:
    """Read a named, version-controlled people query."""
    return (_QUERY_ROOT / f"{name}.sql").read_text()


def promote_legislators(
    conn: psycopg.Connection,
    rows: Iterable[tuple[str, str, str | None, str | None, str, str, UUID]],
) -> dict[str, Any]:
    """Load ``(bioguide, full_name, given, family, namespace, id, artifact_id)`` rows.

    Runs in one transaction on the caller's connection, so a failure leaves the
    warehouse untouched and a rerun with the same rows changes nothing.
    """
    new_ids: dict[str, UUID] = {}
    staged = 0
    with conn.transaction():
        cur = conn.cursor()
        cur.execute(_query("create_legislator_stage"))
        with cur.copy(
            f"COPY legislator_stage ({', '.join(STAGE_COLUMNS)}) FROM STDIN"
        ) as copy:
            for bioguide, full, given, family, namespace, external, artifact in rows:
                copy.write_row(
                    (
                        bioguide,
                        new_ids.setdefault(bioguide, uuid4()),
                        full,
                        given,
                        family,
                        namespace,
                        external,
                        artifact,
                    )
                )
                staged += 1
        cur.execute(_query("insert_new_legislator_people"))
        people_created = cur.rowcount
        cur.execute(_query("insert_legislator_identifiers"))
        identifiers_created = cur.rowcount
        cur.execute(_query("legislator_identifier_conflicts"))
        conflicts = [
            {
                "bioguide": row["bioguide"],
                "namespace": row["namespace"],
                "external_id": row["external_id"],
                "existing_person_id": str(row["existing_person_id"]),
                "bioguide_person_id": str(row["bioguide_person_id"]),
            }
            for row in cur.fetchall()
        ]
    return {
        "legislators": len(new_ids),
        "identifiers_staged": staged,
        "people_created": people_created,
        "identifiers_created": identifiers_created,
        "identifiers_already_present": staged - identifiers_created - len(conflicts),
        "conflicts": conflicts,
    }
