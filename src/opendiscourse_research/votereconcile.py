"""Read-only reconciliation for OpenStates congressional vote coverage."""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select

from .db import connect, session
from .models.core import roll_call_table


def reconcile_openstates_votes(congress: int) -> dict[str, Any]:
    """Compare source vote-event identities with canonical roll-call coverage."""
    roll_call = roll_call_table()
    with session() as active_session:
        canonical = {
            "canonical_roll_calls": int(
                active_session.execute(
                    select(func.count()).select_from(roll_call).where(
                        roll_call.c.legislative_session == str(congress)
                    )
                ).scalar_one()
            )
        }
    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT count(*) AS source_events, count(DISTINCT v.identifier) AS source_keys
            FROM openstates_source.opencivicdata_voteevent v
            JOIN openstates_source.opencivicdata_legislativesession s ON s.id = v.legislative_session_id
            WHERE s.identifier = %s""",
            (str(congress),),
        )
        source = dict(cur.fetchone())
        cur.execute(
            """SELECT v.identifier, count(*) AS source_events
            FROM openstates_source.opencivicdata_voteevent v
            JOIN openstates_source.opencivicdata_legislativesession s ON s.id = v.legislative_session_id
            WHERE s.identifier = %s GROUP BY v.identifier HAVING count(*) > 1 ORDER BY v.identifier""",
            (str(congress),),
        )
        duplicates = [dict(row) for row in cur.fetchall()]
    return {
        "congress": congress,
        "source": source,
        "canonical": canonical,
        "duplicate_identifiers": duplicates,
    }
