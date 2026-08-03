"""Repository queries for deterministic federal legislative reconciliation."""
from __future__ import annotations

from pathlib import Path

from ..db import connect


_QUERY_ROOT = Path(__file__).resolve().parents[3] / "sql" / "query" / "legislation"


def bill_keys(congress: int, bill_type: str) -> set[str]:
    """Return OpenStates-compatible bill numbers for one Congress and bill type."""
    query = (_QUERY_ROOT / "bill_keys.sql").read_text()
    with connect() as conn, conn.cursor() as cur:
        cur.execute(query, {"congress": str(congress), "bill_type": bill_type.lower()})
        return {row["bill_number"] for row in cur.fetchall()}
