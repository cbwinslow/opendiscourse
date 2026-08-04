"""Read-only reconciliation for OpenStates congressional vote coverage."""
from __future__ import annotations

from typing import Any

from .db import connect


def reconcile_openstates_votes(congress: int) -> dict[str, Any]:
    """Compare source vote-event identities with canonical roll-call coverage."""
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
            "SELECT count(*) AS canonical_roll_calls FROM core.roll_call WHERE legislative_session = %s",
            (str(congress),),
        )
        canonical = dict(cur.fetchone())
        cur.execute(
            """SELECT v.identifier, count(*) AS source_events
            FROM openstates_source.opencivicdata_voteevent v
            JOIN openstates_source.opencivicdata_legislativesession s ON s.id = v.legislative_session_id
            WHERE s.identifier = %s GROUP BY v.identifier HAVING count(*) > 1 ORDER BY v.identifier""",
            (str(congress),),
        )
        duplicates = [dict(row) for row in cur.fetchall()]
    return {"congress": congress, "source": source, "canonical": canonical, "duplicate_identifiers": duplicates}
