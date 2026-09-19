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
    "run_id",
)


def _query(name: str) -> str:
    """Read a named, version-controlled people query."""
    return (_QUERY_ROOT / f"{name}.sql").read_text()


def promote_legislators(
    conn: psycopg.Connection,
    rows: Iterable[tuple[str, str, str | None, str | None, str, str, UUID, UUID | str]],
) -> dict[str, Any]:
    """Load ``(bioguide, full_name, given, family, namespace, id, artifact_id, run_id)`` rows.

    Runs in one transaction on the caller's connection, so a failure leaves the
    warehouse untouched and a rerun with the same rows changes nothing.
    """
    new_ids: dict[str, UUID] = {}
    staged = 0
    with conn.transaction():
        cur = conn.cursor()
        # Serialize concurrent loads: READ COMMITTED NOT EXISTS cannot see another
        # transaction's uncommitted person and would create a duplicate.
        cur.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended('congress.legislators:promote', 0))"
        )
        cur.execute(_query("create_legislator_stage"))
        with cur.copy(
            f"COPY legislator_stage ({', '.join(STAGE_COLUMNS)}) FROM STDIN"
        ) as copy:
            for bioguide, full, given, family, namespace, external, artifact, run in rows:
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
                        run,
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
                "bioguide_person_created": row["bioguide_person_created"],
            }
            for row in cur.fetchall()
        ]
    return {
        "legislators": len(new_ids),
        "identifiers_staged": staged,
        "people_created": people_created,
        "identifiers_created": identifiers_created,
        "identifiers_already_present": staged - identifiers_created - len(conflicts),
        "possible_duplicate_people": sum(c["bioguide_person_created"] for c in conflicts),
        "conflicts": conflicts,
    }


TERM_STAGE_COLUMNS = (
    "bioguide",
    "artifact_id",
    "chamber",
    "role",
    "start_date",
    "end_date",
    "state_ocd",
    "state_label",
    "state_class",
    "post_ocd",
    "post_division_label",
    "post_division_class",
    "post_label",
    "post_role",
    "metadata",
)


def congress_chamber_organizations(conn: psycopg.Connection) -> tuple[UUID, UUID]:
    """The House and Senate organizations (US ``lower`` and ``upper``): exactly one of each.

    They come from the OpenStates baseline. Guessing or creating one here would fork
    organization identity, so a missing or ambiguous chamber is an error that names the fix.
    """
    with conn.cursor() as cur:
        cur.execute(_query("congress_chamber_organizations"))
        found: dict[str, list[UUID]] = {}
        for row in cur.fetchall():
            found.setdefault(row["organization_type"], []).append(row["organization_id"])
    for kind, name in (("lower", "House"), ("upper", "Senate")):
        if len(found.get(kind, [])) != 1:
            raise RuntimeError(
                f"expected exactly one US {name} organization ({kind}), found "
                f"{len(found.get(kind, []))}; run `research-db load-openstates-organizations`"
            )
    return found["lower"][0], found["upper"][0]


def promote_terms(conn: psycopg.Connection, rows: Iterable[tuple[Any, ...]]) -> dict[str, int]:
    """Load staged legislator terms as divisions, posts and memberships in one transaction.

    ``rows`` follow ``TERM_STAGE_COLUMNS`` (``metadata`` a JSON string). People are matched by
    BioGuide only. Returns counts; a rerun with the same rows inserts and updates nothing.
    """
    house, senate = congress_chamber_organizations(conn)
    params = {"house": house, "senate": senate}
    staged = 0
    with conn.transaction():
        cur = conn.cursor()
        cur.execute("SELECT pg_advisory_xact_lock(hashtextextended('congress.legislators:terms', 0))")
        cur.execute(_query("create_term_stage"))
        with cur.copy(f"COPY term_stage ({', '.join(TERM_STAGE_COLUMNS)}) FROM STDIN") as copy:
            for row in rows:
                copy.write_row(row)
                staged += 1
        cur.execute(_query("count_unresolved_terms"))
        unresolved = cur.fetchone()["unresolved"]
        cur.execute(_query("insert_term_divisions"))
        divisions = cur.rowcount
        cur.execute(_query("insert_term_posts"), params)
        posts = cur.rowcount
        cur.execute(_query("upsert_term_memberships"), params)
        outcomes = [row["inserted"] for row in cur.fetchall()]
    inserted = sum(outcomes)
    return {
        "terms_staged": staged,
        "terms_unresolved": unresolved,
        "divisions_created": divisions,
        "posts_created": posts,
        "memberships_created": inserted,
        "memberships_updated": len(outcomes) - inserted,
        "memberships_unchanged": staged - unresolved - len(outcomes),
    }
