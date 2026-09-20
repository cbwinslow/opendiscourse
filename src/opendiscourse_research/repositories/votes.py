"""SQL for roll-call votes read from official chamber files (Stories 11.1 and 11.2).

Every statement lives in ``sql/query/votes/``. A roll call is written in the caller's transaction:
the roll-call row (matched to an existing OpenStates one by ``us-<year>-lower-<number>`` or
``us-<year>-upper-<number>``, else inserted), its totals by party, one ``fact.member_vote`` per member
the file names *and* the warehouse knows by BioGuide id (House) or LIS member id (Senate), and last the
whole record. Members are never found by name.
"""

from __future__ import annotations

from functools import cache
from pathlib import Path
from typing import Any
from uuid import UUID

from psycopg.types.json import Jsonb

from .billstatus import superseded_artifact_ids

_QUERY_ROOT = Path(__file__).resolve().parents[3] / "sql" / "query" / "votes"
US_JURISDICTION_ID = "ocd-jurisdiction/country:us/government"
# The House's organization as OpenStates identifies it; how the existing roll calls point at it.
HOUSE_OCD_ORGANIZATION = "ocd-organization/24af4233-d9b5-5933-91b2-51d29f721037"
SENATE_OCD_ORGANIZATION = "ocd-organization/072da2ce-df81-52c3-9cc8-323e208cdf10"


@cache
def _query(name: str) -> str:
    """Read a named, version-controlled query template (once per process)."""
    return (_QUERY_ROOT / f"{name}.sql").read_text()


def house_external_id(year: int, number: int) -> str:
    """The key OpenStates uses for a House roll call, so an official file finds its existing row."""
    return f"us-{year}-lower-{number}"


def senate_external_id(year: int, number: int) -> str:
    """The key OpenStates uses for a Senate roll call, so an official file finds its existing row."""
    return f"us-{year}-upper-{number}"


def bioguide_people(conn: Any) -> dict[str, str]:
    """BioGuide id -> person id, for every person the warehouse holds."""
    with conn.cursor() as cur:
        cur.execute(_query("bioguide_people"))
        return {row["bioguide_id"]: str(row["person_id"]) for row in cur.fetchall()}


def lis_people(conn: Any) -> dict[str, str]:
    """LIS member id -> person id, for every senator the warehouse holds an LIS id for."""
    with conn.cursor() as cur:
        cur.execute(_query("lis_people"))
        return {row["lis_member_id"]: str(row["person_id"]) for row in cur.fetchall()}


def organization_id(conn: Any, ocd_id: str) -> str | None:
    """A chamber's organization id by its OCD identifier when the warehouse has seeded it, else None."""
    with conn.cursor() as cur:
        cur.execute(_query("find_organization_by_ocd"), {"ocd_id": ocd_id})
        row = cur.fetchone()
    return str(row["organization_id"]) if row else None


def house_organization_id(conn: Any) -> str | None:
    """The House's organization id when the warehouse has seeded it, else None."""
    return organization_id(conn, HOUSE_OCD_ORGANIZATION)


def senate_organization_id(conn: Any) -> str | None:
    """The Senate's organization id when the warehouse has seeded it, else None."""
    return organization_id(conn, SENATE_OCD_ORGANIZATION)


def try_sync_lock(conn: Any, key: str) -> bool:
    """Take the session-level advisory lock ``key``; False when another connection holds it."""
    with conn.cursor() as cur:
        cur.execute(_query("try_sync_lock"), {"key": key})
        row = cur.fetchone()
    return bool(row and row["acquired"])


def legislative_session_id(conn: Any, congress: int) -> str | None:
    """The session row of a Congress, or None if BILLSTATUS has not created it."""
    with conn.cursor() as cur:
        cur.execute(
            _query("find_legislative_session"),
            {"jurisdiction_id": US_JURISDICTION_ID, "identifier": str(congress)},
        )
        row = cur.fetchone()
    return str(row["legislative_session_id"]) if row else None


def loaded_roll_records(conn: Any, artifact_ids: list[str]) -> dict[str, list[str]]:
    """Artifact id -> the BioGuide ids its loaded record could not resolve, for loaded versions only."""
    if not artifact_ids:
        return {}
    with conn.cursor() as cur:
        cur.execute(_query("loaded_roll_records"), {"artifact_ids": artifact_ids})
        return {
            str(row["source_artifact_id"]): list(row["unresolved_bioguide_ids"])
            for row in cur.fetchall()
        }


def older_artifact_ids(conn: Any, artifact_id: str) -> list[UUID]:
    """Versions of this file's logical artifact that are strictly older than ``artifact_id``."""
    return superseded_artifact_ids(conn, artifact_id)


def save_house_roll_call(
    conn: Any,
    parsed: Any,
    *,
    year: int,
    artifact_id: str,
    session_id: str | None,
    organization_id: str | None,
    people: dict[str, str],
    older_versions: list[UUID],
) -> dict[str, Any]:
    """Write one parsed House roll call and its record in the caller's transaction.

    Returns ``roll_call_id``, ``inserted`` (a new row) or ``enriched`` (an OpenStates row that
    gained official fields), the typed vote count, ``unresolved`` BioGuide ids the warehouse does
    not know, and ``entries_without_id`` (entries with no ``name-id``, kept only in the record).
    """
    return _save_roll_call(
        conn,
        parsed,
        external_id=house_external_id(year, parsed.roll["roll_number"]),
        roll_year=year,
        artifact_id=artifact_id,
        session_id=session_id,
        organization_id=organization_id,
        people=people,
        older_versions=older_versions,
        roll_query="upsert_house_roll_call",
        vote_query="upsert_official_member_vote",
        member_key="bioguide_id",
        source="house_clerk",
        missing_id_unresolved=False,
    )


def save_senate_roll_call(
    conn: Any,
    parsed: Any,
    *,
    year: int,
    artifact_id: str,
    session_id: str | None,
    organization_id: str | None,
    people: dict[str, str],
    older_versions: list[UUID],
) -> dict[str, Any]:
    """Write one parsed Senate roll call and its record in the caller's transaction.

    Same result as :func:`save_house_roll_call`, with LIS member ids. A senator entry with no
    ``lis_member_id`` is not a vote we can attribute and is never matched by name: it is counted in
    ``entries_without_id`` and also listed in ``unresolved`` (as ``(no lis_member_id) <printed name>``),
    so the run is partial and the entry is visible until a person exists for it.
    """
    return _save_roll_call(
        conn,
        parsed,
        external_id=senate_external_id(year, parsed.roll["roll_number"]),
        roll_year=year,
        artifact_id=artifact_id,
        session_id=session_id,
        organization_id=organization_id,
        people=people,
        older_versions=older_versions,
        roll_query="upsert_senate_roll_call",
        vote_query="upsert_senate_member_vote",
        member_key="lis_member_id",
        source="senate_gov",
        missing_id_unresolved=True,
    )


def _save_roll_call(
    conn: Any,
    parsed: Any,
    *,
    external_id: str,
    roll_year: int,
    artifact_id: str,
    session_id: str | None,
    organization_id: str | None,
    people: dict[str, str],
    older_versions: list[UUID],
    roll_query: str,
    vote_query: str,
    member_key: str,
    source: str,
    missing_id_unresolved: bool,
) -> dict[str, Any]:
    """The shared write: roll call, totals by party, typed votes, then the record (last)."""
    roll = parsed.roll
    params = {
        **roll,
        "external_id": external_id,
        "roll_year": roll_year,
        "metadata": Jsonb({"source": source}),
        "organization_id": organization_id,
        "legislative_session_id": session_id,
        "source_artifact_id": artifact_id,
    }
    with conn.cursor() as cur:
        cur.execute(_query(roll_query), params)
        row = cur.fetchone()
        assert row is not None
        roll_call_id = str(row["roll_call_id"])
        if older_versions:
            cur.execute(
                _query("supersede_roll_call"),
                {"roll_call_id": roll_call_id, "old_artifact_ids": older_versions},
            )
        cur.execute(_query("replace_roll_call_party_totals"), {"roll_call_id": roll_call_id})
        for party in parsed.party_totals:
            cur.execute(
                _query("insert_roll_call_party_total"),
                {**party, "roll_call_id": roll_call_id, "source_artifact_id": artifact_id},
            )
        typed: list[dict[str, Any]] = []
        unresolved: list[str] = []
        without_id = 0
        for vote in parsed.votes:
            member_id = vote[member_key]
            if member_id is None:
                without_id += 1
                if missing_id_unresolved:
                    unresolved.append(f"(no {member_key}) {vote['name'] or 'unnamed entry'}")
            elif member_id in people:
                typed.append(
                    {
                        **vote,
                        "roll_call_id": roll_call_id,
                        "person_id": people[member_id],
                        "source_artifact_id": artifact_id,
                    }
                )
            elif member_id not in unresolved:
                unresolved.append(member_id)
        cur.executemany(_query(vote_query), typed)
        cur.execute(
            _query("upsert_roll_call_source_record"),
            {
                "roll_call_id": roll_call_id,
                "source_artifact_id": artifact_id,
                "record": Jsonb(parsed.record),
                "record_sha256": parsed.record_sha256,
                "entry_count": len(parsed.votes),
                "typed_count": len(typed),
                "entries_without_id": without_id,
                "unresolved_bioguide_ids": sorted(unresolved),
            },
        )
    return {
        "roll_call_id": roll_call_id,
        "inserted": row["inserted"],
        "enriched": not row["inserted"] and bool(row["openstates"]),
        "typed": len(typed),
        "unresolved": sorted(unresolved),
        "entries_without_id": without_id,
    }


def link_senate_bills(conn: Any, congresses: list[int]) -> int:
    """Link the Senate roll calls of these Congresses that name a bill core.bill now holds; returns how many."""
    with conn.cursor() as cur:
        cur.execute(_query("link_senate_roll_call_bills"), {"congresses": [str(c) for c in congresses]})
        return cur.rowcount


def count_disagreements(conn: Any, roll_call_ids: list[str]) -> list[dict[str, Any]]:
    """Rolls whose official totals differ from the typed votes stored for them."""
    if not roll_call_ids:
        return []
    with conn.cursor() as cur:
        cur.execute(_query("roll_call_count_disagreements"), {"roll_call_ids": roll_call_ids})
        return [
            {**row, "roll_call_id": str(row["roll_call_id"])} for row in cur.fetchall()
        ]
