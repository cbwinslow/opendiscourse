"""SQL for roll-call votes read from official chamber files (Story 11.1).

Every statement lives in ``sql/query/votes/``. A roll call is written in the caller's transaction:
the roll-call row (matched to an existing OpenStates one by ``us-<year>-lower-<number>``, else
inserted), its totals by party, one ``fact.member_vote`` per member the file names *and* the
warehouse knows by BioGuide id, and last the whole record. Members are never found by name.
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


@cache
def _query(name: str) -> str:
    """Read a named, version-controlled query template (once per process)."""
    return (_QUERY_ROOT / f"{name}.sql").read_text()


def house_external_id(year: int, number: int) -> str:
    """The key OpenStates uses for a House roll call, so an official file finds its existing row."""
    return f"us-{year}-lower-{number}"


def bioguide_people(conn: Any) -> dict[str, str]:
    """BioGuide id -> person id, for every person the warehouse holds."""
    with conn.cursor() as cur:
        cur.execute(_query("bioguide_people"))
        return {row["bioguide_id"]: str(row["person_id"]) for row in cur.fetchall()}


def house_organization_id(conn: Any) -> str | None:
    """The House's organization id when the warehouse has seeded it, else None."""
    with conn.cursor() as cur:
        cur.execute(_query("find_house_organization"), {"ocd_id": HOUSE_OCD_ORGANIZATION})
        row = cur.fetchone()
    return str(row["organization_id"]) if row else None


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
    """Write one parsed roll call and its record in the caller's transaction.

    Returns ``roll_call_id``, ``inserted`` (a new row) or ``enriched`` (an OpenStates row that
    gained official fields), the typed vote count, ``unresolved`` BioGuide ids the warehouse does
    not know, and ``entries_without_id`` (entries with no ``name-id``, kept only in the record).
    """
    roll = parsed.roll
    params = {
        **roll,
        "external_id": house_external_id(year, roll["roll_number"]),
        "roll_year": year,
        "metadata": Jsonb({"source": "house_clerk"}),
        "organization_id": organization_id,
        "legislative_session_id": session_id,
        "source_artifact_id": artifact_id,
    }
    with conn.cursor() as cur:
        cur.execute(_query("upsert_house_roll_call"), params)
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
            bioguide = vote["bioguide_id"]
            if bioguide is None:
                without_id += 1
            elif bioguide in people:
                typed.append(
                    {
                        **vote,
                        "roll_call_id": roll_call_id,
                        "person_id": people[bioguide],
                        "source_artifact_id": artifact_id,
                    }
                )
            elif bioguide not in unresolved:
                unresolved.append(bioguide)
        cur.executemany(_query("upsert_official_member_vote"), typed)
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


def count_disagreements(conn: Any, roll_call_ids: list[str]) -> list[dict[str, Any]]:
    """Rolls whose official totals differ from the typed votes stored for them."""
    if not roll_call_ids:
        return []
    with conn.cursor() as cur:
        cur.execute(_query("roll_call_count_disagreements"), {"roll_call_ids": roll_call_ids})
        return [
            {**row, "roll_call_id": str(row["roll_call_id"])} for row in cur.fetchall()
        ]
