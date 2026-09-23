"""SQL for the current committee-membership snapshot.

Every statement lives in ``sql/query/committees/``. People are linked on BioGuide
only. A second load of the same bytes does not rewrite a row.
"""

from __future__ import annotations

from functools import cache
from pathlib import Path
from typing import Any

from psycopg.types.json import Jsonb

from .names import upsert_person_name_sources

_QUERY_ROOT = Path(__file__).resolve().parents[3] / "sql" / "query" / "committees"
DATASET_ID = "congress.committee_membership"
ROSTER = "roster"


@cache
def _query(name: str) -> str:
    """Read a named, version-controlled query (once per process)."""
    return (_QUERY_ROOT / f"{name}.sql").read_text()


def try_sync_lock(conn: Any, key: str) -> bool:
    """Take the session-level advisory lock ``key``; False when another connection holds it."""
    with conn.cursor() as cur:
        cur.execute(_query("try_sync_lock"), {"key": key})
        row = cur.fetchone()
    return bool(row and row["acquired"])


def _changed(cur: Any, name: str, params: dict[str, Any]) -> dict[str, int]:
    cur.execute(_query(name), params)
    rows = cur.fetchall()
    if rows and "inserted" in rows[0]:
        inserted = sum(1 for row in rows if row["inserted"])
        return {"inserted": inserted, "updated": len(rows) - inserted, "deleted": 0}
    return {"inserted": 0, "updated": 0, "deleted": len(rows)}


def publish_committee_membership(
    conn: Any,
    *,
    committees: list[dict[str, Any]],
    assignments: list[dict[str, Any]],
    source_records: list[dict[str, Any]],
    run_id: str,
    vintage: str,
    membership_artifact_id: str,
) -> dict[str, Any]:
    """Upsert one snapshot and drop rows the files no longer contain.

    The caller owns the transaction. Roster assertions are written only for a
    member whose BioGuide already matches a person, and only when the printed
    name or its evidence changed. An empty committee list is refused: the
    delete would otherwise remove every committee.
    """
    if not committees or not source_records:
        raise ValueError("refusing to publish an empty committee snapshot")
    cur = conn.cursor()
    committee_counts = _changed(cur, "upsert_committees", {"rows": Jsonb(committees)})
    removed_committees = _changed(
        cur, "delete_absent_committees", {"keys": [row["thomas_key"] for row in committees]}
    )
    assignment_counts = _changed(cur, "upsert_assignments", {"rows": Jsonb(assignments)})
    removed_assignments = _changed(
        cur,
        "delete_absent_assignments",
        {"rows": Jsonb([{"thomas_key": row["thomas_key"], "bioguide": row["bioguide"]} for row in assignments])},
    )
    record_counts = _changed(cur, "upsert_source_records", {"rows": Jsonb(source_records)})
    removed_records = _changed(
        cur,
        "delete_absent_source_records",
        {
            "rows": Jsonb(
                [
                    {
                        "source_file": row["source_file"],
                        "thomas_key": row["thomas_key"],
                        "bioguide": row["bioguide"],
                    }
                    for row in source_records
                ]
            )
        },
    )
    cur.execute(_query("linked_members"))
    by_person: dict[str, str] = {}
    for row in cur.fetchall():
        previous = by_person.setdefault(row["person_id"], row["stated_name"])
        if previous != row["stated_name"]:
            raise ValueError(
                f"BioGuide linked to person {row['person_id']} has two printed roster names: "
                f"{previous!r} and {row['stated_name']!r}"
            )
    cur.execute(_query("unknown_bioguides"))
    unknown = [row["bioguide"] for row in cur.fetchall()]
    removed_roster = _changed(
        cur,
        "delete_stale_roster",
        {
            "dataset_id": DATASET_ID,
            "vintage": vintage,
            "person_ids": Jsonb(sorted(by_person)),
        },
    )
    cur.execute(
        _query("roster_assertions"),
        {"dataset_id": DATASET_ID, "vintage": vintage},
    )
    existing = {row["person_id"]: row for row in cur.fetchall()}
    fresh = []
    for person_id, full_name in sorted(by_person.items()):
        current = existing.get(person_id)
        if (
            current
            and current["full_name"] == full_name
            and current["artifact_id"] == membership_artifact_id
            and current["given_name"] is None
            and current["family_name"] is None
        ):
            continue
        fresh.append(
            {
                "person_id": person_id,
                "name_kind": ROSTER,
                "full_name": full_name,
                "given_name": None,
                "family_name": None,
                "dataset_id": DATASET_ID,
                "source_vintage": vintage,
                "artifact_id": membership_artifact_id,
                "payload_id": None,
                "run_id": run_id,
            }
        )
    roster = upsert_person_name_sources(cur, fresh)
    return {
        "committees": len(committees),
        "assignments": len(assignments),
        "source_records": len(source_records),
        "committees_inserted": committee_counts["inserted"],
        "committees_updated": committee_counts["updated"],
        "committees_deleted": removed_committees["deleted"],
        "assignments_inserted": assignment_counts["inserted"],
        "assignments_updated": assignment_counts["updated"],
        "assignments_deleted": removed_assignments["deleted"],
        "source_records_inserted": record_counts["inserted"],
        "source_records_updated": record_counts["updated"],
        "source_records_deleted": removed_records["deleted"],
        "roster_inserted": roster["inserted"],
        "roster_updated": roster["updated"],
        "roster_deleted": removed_roster["deleted"],
        "unknown_bioguide_ids": unknown,
    }
