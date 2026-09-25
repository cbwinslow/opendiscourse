"""SQL for the BILLSTATUS Connector: refresh handling on top of ``legislation``."""

from __future__ import annotations

from functools import cache
from pathlib import Path
from typing import Any
from uuid import UUID

# The keys ``supersede_bill_children`` reports, one per table it clears.
SUPERSEDED_TABLES = (
    "actions",
    "sponsorships",
    "committees",
    "subjects",
    "records",
    "summaries",
    "laws",
    "related_bills",
    "amendments",
    "cbo_cost_estimates",
)

_QUERY_ROOT = Path(__file__).resolve().parents[3] / "sql" / "query" / "legislation"


@cache
def _query(name: str) -> str:
    """Read a named, version-controlled query template (once per process)."""
    return (_QUERY_ROOT / f"{name}.sql").read_text()


def superseded_artifact_ids(conn: Any, artifact_id: UUID | str) -> list[UUID]:
    """Ids of the versions of this artifact's logical file that are older than it.

    Only older versions: a newer one (committed by another process) is never superseded by
    loading this one. Empty on a first load.
    """
    with conn.cursor() as cur:
        cur.execute(_query("superseded_artifact_ids"), {"artifact_id": artifact_id})
        return [row["artifact_id"] for row in cur.fetchall()]


def loaded_record_members(conn: Any, artifact_id: UUID | str) -> set[str]:
    """Members of this artifact version that are fully loaded (they have a record row).

    The record row is written last, in the batch's own transaction, so its presence means the
    bill and every child row from that member are committed. Bills loaded before the record
    existed have none and are loaded once more, which the upserts make idempotent.
    """
    with conn.cursor() as cur:
        cur.execute(_query("loaded_record_members"), {"artifact_id": artifact_id})
        return {row["source_member"] for row in cur.fetchall()}


def supersede_bill_children(
    conn: Any, bill_ids: list[str], old_artifact_ids: list[UUID]
) -> dict[str, int]:
    """Delete older artifact versions' child rows for ``bill_ids``; return the counts.

    The caller passes bills it has just rewritten from the newer version, inside the
    same transaction, so a failure leaves the older rows in place.
    """
    if not bill_ids or not old_artifact_ids:
        return dict.fromkeys(SUPERSEDED_TABLES, 0)
    with conn.cursor() as cur:
        cur.execute(
            _query("supersede_bill_children"),
            {"bill_ids": bill_ids, "old_artifact_ids": old_artifact_ids},
        )
        row = cur.fetchone()
    assert row is not None
    return dict(row)
