"""Set-based promotion of legislator identity into ``core.person``.

SQL only. People are matched by an existing BioGuide identifier and nothing
else; identifiers already owned by another person are reported, never moved.
"""

from __future__ import annotations

from collections.abc import Iterable
from functools import cache
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import psycopg
from psycopg.types.json import Jsonb

from ..identity_merge import (
    Identifier,
    SamePerson,
    linked_identifiers,
    load_same_person,
)

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


# One lock for every code path that creates a person or writes an identifier, so a
# concurrent writer cannot create a duplicate of a person another has not committed.
PERSON_IDENTITY_LOCK = "core.person:identity"

# Namespaces where a person has exactly one value; a second, different one is a conflict.
SINGLE_VALUED = ("bioguide",)

# Every table that references core.person; a test compares this with the catalog.
PERSON_REFERENCES = (
    "core.person_identifier",
    "core.bill_sponsorship",
    "core.membership",
    "fact.member_vote",
    "core.person_name_source",
    "core.committee_assignment",
    "core.voteview_member",
    "core.person_leadership",
    "core.person_social_account",
    "core.district_office",
)

# Repointed by their own statement: a plain UPDATE would collide with the survivor's assertions.
_NAME_SOURCES = "core.person_name_source"


@cache
def _query(name: str) -> str:
    """Read a named, version-controlled people query (once per process)."""
    return (_QUERY_ROOT / f"{name}.sql").read_text()


def lock_person_identity(cur: psycopg.Cursor) -> None:
    """Serialize person creation and identifier writes until the transaction ends."""
    cur.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))", (PERSON_IDENTITY_LOCK,))


def resolve_person(
    cur: psycopg.Cursor,
    identifiers: list[Identifier],
    *,
    dataset_id: str,
    subject: str,
    new_person: dict[str, Any],
    run_id: UUID | str | None = None,
    artifact_id: UUID | str | None = None,
    exceptions: list[SamePerson] | None = None,
) -> dict[str, Any]:
    """Find, create or refuse the person a source record describes (ADR-0005, Decision 1).

    The owners of any asserted identifier decide: none creates a person, one gets the
    remaining identifiers attached, two or more are a conflict and nothing is written.
    Identifiers never move between persons and names are never consulted. Reviewed
    ``same_person`` exceptions add their survivor to the asserted set.
    """
    lock_person_identity(cur)
    asserted = linked_identifiers(identifiers, exceptions)
    if not asserted:
        raise ValueError("resolve_person needs at least one identifier; it never matches by name")
    arrays = {
        "namespaces": [namespace for namespace, _ in asserted],
        "external_ids": [external_id for _, external_id in asserted],
    }
    cur.execute(_query("find_identifier_owners"), arrays)
    owners = [row["person_id"] for row in cur.fetchall()]
    wanted = {external for namespace, external in asserted if namespace in SINGLE_VALUED}
    if len(wanted) > 1:  # the source itself gives one person two BioGuide ids
        _record_conflict(cur, "bioguide_mismatch", dataset_id, subject, owners, asserted, run_id)
        return {"outcome": "bioguide_mismatch", "person_id": None, "attached": 0}
    if len(owners) > 1:
        _record_conflict(cur, "multiple_owners", dataset_id, subject, owners, asserted, run_id)
        return {"outcome": "multiple_owners", "person_id": None, "attached": 0}
    if owners:
        person_id = owners[0]
        cur.execute(_query("person_bioguides"), {"person_id": person_id})
        held = {row["external_id"] for row in cur.fetchall()}
        if held and wanted - held:
            _record_conflict(cur, "bioguide_mismatch", dataset_id, subject, owners, asserted, run_id)
            return {"outcome": "bioguide_mismatch", "person_id": None, "attached": 0}
        outcome = "matched"
    else:
        cur.execute(_query("insert_person"), {**new_person, "metadata": Jsonb(new_person["metadata"])})
        person_id = cur.fetchone()["person_id"]
        outcome = "created"
    cur.execute(
        _query("attach_person_identifiers"),
        {"person_id": person_id, "artifact_id": artifact_id, "run_id": run_id, **arrays},
    )
    return {"outcome": outcome, "person_id": person_id, "attached": len(cur.fetchall())}


def _record_conflict(
    cur: psycopg.Cursor,
    kind: str,
    dataset_id: str,
    subject: str,
    person_ids: list[UUID],
    asserted: list[Identifier],
    run_id: UUID | str | None,
) -> None:
    cur.execute(
        _query("record_identity_conflict"),
        {
            "dataset_id": dataset_id,
            "run_id": run_id,
            "kind": kind,
            "subject": subject,
            "person_ids": sorted(person_ids),
            "identifiers": Jsonb([list(pair) for pair in asserted]),
        },
    )


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
        lock_person_identity(cur)
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
        cur.execute(_query("resolve_legislator_groups"))
        cur.execute(_query("insert_new_legislator_people"))
        people_created = cur.rowcount
        cur.execute(_query("insert_legislator_identifiers"))
        identifiers_created = cur.rowcount
        cur.execute(_query("record_legislator_conflicts"))
        conflicts = [
            {
                "bioguide": row["subject"].removeprefix("bioguide:"),
                "kind": row["kind"],
                "person_ids": [str(person_id) for person_id in row["person_ids"]],
            }
            for row in cur.fetchall()
        ]
        cur.execute(_query("count_conflicted_legislator_identifiers"))
        identifiers_skipped = cur.fetchone()["skipped"]
    return {
        "legislators": len(new_ids),
        "identifiers_staged": staged,
        "people_created": people_created,
        "identifiers_created": identifiers_created,
        "identifiers_already_present": staged - identifiers_created - identifiers_skipped,
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
    "contact",
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


def merge_person(
    conn: psycopg.Connection,
    exception: SamePerson,
    run_id: UUID | str | None = None,
) -> dict[str, Any]:
    """Apply one reviewed ``same_person`` exception in a single transaction.

    Identifiers, sponsorships, memberships, committee seats and votes move to the survivor.
    A committee seat keeps the roster id that was loaded; only the person it points at
    changes. A vote the
    survivor also cast is kept whole in ``ingest.person_merge_vote`` and dropped from
    the fact table; a term that would collide with the survivor's aborts the merge. Name
    assertions move too; where the survivor asserts the same kind, dataset and vintage its
    own stands and the duplicate's is dropped (counted). The duplicate is deleted last.
    Already merged (or never created) is a no-op.
    """
    with conn.transaction():
        cur = conn.cursor()
        lock_person_identity(cur)
        survivor = _sole_owner(cur, exception.survivor)
        duplicate = _sole_owner(cur, exception.duplicate)
        if duplicate is None or duplicate == survivor:
            return {"exception": exception.id, "status": "already_merged"}
        if survivor is None:
            return {"exception": exception.id, "status": "survivor_missing"}
        params = {"survivor": survivor, "duplicate": duplicate}
        cur.execute(_query("merge_bioguide_collisions"), params)
        if cur.fetchone()["collisions"]:
            raise ValueError(
                f"{exception.id}: the duplicate holds a BioGuide id the survivor does not; "
                "these are two people, nothing was merged"
            )
        cur.execute(_query("merge_membership_collisions"), params)
        collisions = cur.fetchone()["collisions"]
        if collisions:
            raise ValueError(
                f"{exception.id}: {collisions} membership terms of the duplicate collide with the "
                "survivor's; resolve them by hand, nothing was merged"
            )
        merge_id = uuid4()
        cur.execute(
            _query("record_person_merge"),
            {
                "merge_id": merge_id,
                "exception_id": exception.id,
                "survivor": survivor,
                "duplicate": duplicate,
                "run_id": run_id,
            },
        )
        cur.execute(_query("merge_preserve_colliding_votes"), {**params, "merge_id": merge_id})
        counts: dict[str, int] = {"member_vote_preserved": cur.rowcount}
        # The survivor's assertion stands where both have one; the duplicate's is dropped and counted.
        cur.execute(_query("merge_name_source_collisions"), params)
        counts["person_name_source_dropped"] = cur.fetchone()["collisions"]
        cur.execute(_query("merge_repoint_name_sources"), params)
        counts[_NAME_SOURCES] = cur.rowcount
        for table in PERSON_REFERENCES:
            if table == _NAME_SOURCES:
                continue
            cur.execute(_query("merge_repoint").format(table=table), params)
            counts[table] = cur.rowcount
        # A person that was itself the survivor of an earlier merge keeps its audit trail.
        cur.execute(_query("merge_repoint_audit"), params)
        cur.execute(_query("resolve_merged_conflicts"), {**params, "resolution": f"merged: {exception.id}"})
        cur.execute("DELETE FROM core.person WHERE person_id = %(duplicate)s", params)
        cur.execute(
            "UPDATE ingest.person_merge SET counts = %(counts)s WHERE person_merge_id = %(merge_id)s",
            {"counts": Jsonb(counts), "merge_id": merge_id},
        )
    return {
        "exception": exception.id,
        "status": "merged",
        "survivor": str(survivor),
        "duplicate": str(duplicate),
        "counts": counts,
    }


def _sole_owner(cur: psycopg.Cursor, identifier: Identifier) -> UUID | None:
    cur.execute(
        _query("find_identifier_owners"),
        {"namespaces": [identifier[0]], "external_ids": [identifier[1]]},
    )
    rows = cur.fetchall()
    return rows[0]["person_id"] if rows else None


def merge_reviewed_people(conn: psycopg.Connection, exceptions: list[SamePerson] | None = None) -> list[dict[str, Any]]:
    """Apply every reviewed ``same_person`` exception; safe to rerun."""
    exceptions = load_same_person() if exceptions is None else exceptions
    return [merge_person(conn, exception) for exception in exceptions]
