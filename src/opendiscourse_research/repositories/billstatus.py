"""SQL for the BILLSTATUS Connector: refresh handling on top of ``legislation``."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from .legislation import _query


def superseded_artifact_ids(
    conn: Any, dataset_id: str, artifact_key: str, keep_artifact_id: UUID | str
) -> list[UUID]:
    """Ids of every other version of one logical artifact (empty on a first load)."""
    with conn.cursor() as cur:
        cur.execute(
            _query("superseded_artifact_ids"),
            {
                "dataset_id": dataset_id,
                "artifact_key": artifact_key,
                "keep_artifact_id": keep_artifact_id,
            },
        )
        return [row["artifact_id"] for row in cur.fetchall()]


def supersede_bill_children(
    conn: Any, bill_ids: list[str], old_artifact_ids: list[UUID]
) -> dict[str, int]:
    """Delete older artifact versions' child rows for ``bill_ids``; return the counts.

    The caller passes bills it has just rewritten from the newer version, inside the
    same transaction, so a failure leaves the older rows in place.
    """
    if not bill_ids or not old_artifact_ids:
        return {"actions": 0, "sponsorships": 0, "committees": 0, "subjects": 0}
    with conn.cursor() as cur:
        cur.execute(
            _query("supersede_bill_children"),
            {"bill_ids": bill_ids, "old_artifact_ids": old_artifact_ids},
        )
        row = cur.fetchone()
    assert row is not None
    return dict(row)
