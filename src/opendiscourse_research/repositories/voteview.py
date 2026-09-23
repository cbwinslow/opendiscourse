"""SQL for Voteview members, roll calls, and parties.

Every statement lives in ``sql/query/voteview/``. A person is linked on ICPSR
only. A roll call is linked to an official vote only when exactly one row
matches, and that vote is never updated. Name notes are written only for a
linked person. The caller owns the transaction.
"""

from __future__ import annotations

from functools import cache
from pathlib import Path
from typing import Any

from psycopg.types.json import Jsonb

from .names import upsert_person_name_sources

_QUERY_ROOT = Path(__file__).resolve().parents[3] / "sql" / "query" / "voteview"
DATASET_ID = "congress.voteview"
NAME_KIND = "voteview"


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


def _deleted(cur: Any, name: str) -> int:
    cur.execute(_query(name))
    return len(cur.fetchall())


def _inserted(cur: Any, name: str, rows: list[dict[str, Any]]) -> int:
    cur.execute(_query(name), {"rows": Jsonb(rows)})
    row = cur.fetchone()
    return int(row["inserted"]) if row else 0


def stored_counts(conn: Any) -> dict[str, int]:
    """Gap and link counts from the rows already stored. Writes nothing."""
    with conn.cursor() as cur:
        cur.execute(_query("summary"))
        row = cur.fetchone()
    return {key: int(value) for key, value in row.items()}


def _name_notes(cur: Any, *, run_id: str, artifact_id: str) -> dict[str, int]:
    """Write a voteview name only for a linked person, and drop notes the file no longer supports."""
    cur.execute(_query("linked_bionames"))
    by_key: dict[tuple[str, str], str] = {}
    for row in cur.fetchall():
        key = (row["person_id"], row["source_vintage"])
        previous = by_key.get(key)
        if previous is not None and previous != row["bioname"]:
            raise ValueError(
                f"person {row['person_id']} Congress {row['source_vintage']} has two Voteview "
                f"names: {previous!r} and {row['bioname']!r}"
            )
        by_key[key] = row["bioname"]
    cur.execute(_query("existing_voteview_names"), {"dataset_id": DATASET_ID})
    existing = {(row["person_id"], row["source_vintage"]): row for row in cur.fetchall()}
    fresh = []
    for (person_id, vintage), full_name in sorted(by_key.items()):
        current = existing.get((person_id, vintage))
        if (
            current
            and current["full_name"] == full_name
            and current["artifact_id"] == artifact_id
            and current["given_name"] is None
            and current["family_name"] is None
        ):
            continue
        fresh.append(
            {
                "person_id": person_id,
                "name_kind": NAME_KIND,
                "full_name": full_name,
                "given_name": None,
                "family_name": None,
                "dataset_id": DATASET_ID,
                "source_vintage": vintage,
                "artifact_id": artifact_id,
                "payload_id": None,
                "run_id": run_id,
            }
        )
    removed = _deleted_kept(cur, by_key)
    written = upsert_person_name_sources(cur, fresh)
    return {
        "names_inserted": written["inserted"],
        "names_updated": written["updated"],
        "names_deleted": removed,
    }


def _deleted_kept(cur: Any, by_key: dict[tuple[str, str], str]) -> int:
    cur.execute(
        _query("delete_stale_voteview_names"),
        {
            "dataset_id": DATASET_ID,
            "kept": Jsonb(
                [{"person_id": person_id, "source_vintage": vintage} for person_id, vintage in by_key]
            ),
        },
    )
    return len(cur.fetchall())


def publish_voteview(
    conn: Any,
    *,
    members: list[dict[str, Any]] | None,
    roll_calls: list[dict[str, Any]] | None,
    parties: list[dict[str, Any]] | None,
    run_id: str,
    members_artifact_id: str | None,
) -> dict[str, int]:
    """Replace derived rows for each file that changed. ``None`` leaves that file's rows alone.

    An empty list is refused: the delete would otherwise remove every row of that file.
    """
    if members is not None and not members:
        raise ValueError("refusing to replace Voteview members with an empty file")
    if roll_calls is not None and not roll_calls:
        raise ValueError("refusing to replace Voteview roll calls with an empty file")
    if parties is not None and not parties:
        raise ValueError("refusing to replace Voteview parties with an empty file")
    counts = {
        "members_inserted": 0,
        "members_deleted": 0,
        "roll_calls_inserted": 0,
        "roll_calls_deleted": 0,
        "parties_inserted": 0,
        "parties_deleted": 0,
        "names_inserted": 0,
        "names_updated": 0,
        "names_deleted": 0,
    }
    cur = conn.cursor()
    if members is not None:
        counts["members_deleted"] = _deleted(cur, "delete_members")
        counts["members_inserted"] = _inserted(cur, "replace_members", members)
        if members_artifact_id is None:
            raise ValueError("member rows need the member file's artifact")
        counts.update(_name_notes(cur, run_id=run_id, artifact_id=members_artifact_id))
    if roll_calls is not None:
        counts["roll_calls_deleted"] = _deleted(cur, "delete_roll_calls")
        counts["roll_calls_inserted"] = _inserted(cur, "replace_roll_calls", roll_calls)
    if parties is not None:
        counts["parties_deleted"] = _deleted(cur, "delete_parties")
        counts["parties_inserted"] = _inserted(cur, "replace_parties", parties)
    return counts
