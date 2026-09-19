"""Read-only loaded-side counts for the Congress coverage comparator."""

from __future__ import annotations

from typing import Any

from sqlalchemy import text

from ..db import session

JURISDICTION = "us"

_BILLS = """
SELECT legislative_session AS congress, lower(bill_type) AS bill_type, count(*) AS n
FROM core.bill WHERE jurisdiction = :j AND legislative_session ~ '^[0-9]+$'
GROUP BY 1, 2
"""
_ACTIONS = """
SELECT b.legislative_session AS congress, count(*) AS n
FROM core.bill_action a JOIN core.bill b USING (bill_id)
WHERE b.jurisdiction = :j AND b.legislative_session ~ '^[0-9]+$'
GROUP BY 1
"""
_ROLL_CALLS = """
SELECT r.legislative_session AS congress, lower(r.chamber) AS chamber,
       count(*) AS roll_calls,
       count(*) FILTER (WHERE NOT EXISTS
           (SELECT 1 FROM fact.member_vote v WHERE v.roll_call_id = r.roll_call_id))
           AS without_votes
FROM core.roll_call r
WHERE r.jurisdiction = :j AND r.legislative_session ~ '^[0-9]+$'
GROUP BY 1, 2
"""
_MEMBER_VOTES = """
SELECT r.legislative_session AS congress, lower(r.chamber) AS chamber, count(*) AS n
FROM fact.member_vote v JOIN core.roll_call r USING (roll_call_id)
WHERE r.jurisdiction = :j AND r.legislative_session ~ '^[0-9]+$'
GROUP BY 1, 2
"""
_MEMBERSHIPS = """
WITH congresses AS (
  SELECT legislative_session_id, identifier AS congress,
         CASE WHEN identifier ~ '^[0-9]+$' THEN identifier::int END AS n
  FROM core.legislative_session
  WHERE classification = 'congress'
)
-- A session-scoped membership counts for its Congress ...
SELECT c.congress AS congress, i.external_id AS bioguide
FROM core.membership m
JOIN congresses c USING (legislative_session_id)
JOIN core.person_identifier i ON i.person_id = m.person_id AND i.namespace = 'bioguide'
WHERE c.n IS NOT NULL
GROUP BY 1, 2
UNION
-- ... and a term (one row, no session) counts for every Congress it overlaps: the same rule
-- ``expected_members`` applies to the legislators YAML. Congress N starts on Jan 3 of 1789 + 2(N-1).
SELECT c.congress, i.external_id
FROM core.membership m
JOIN core.person_identifier i ON i.person_id = m.person_id AND i.namespace = 'bioguide'
JOIN congresses c
  ON c.n IS NOT NULL
 AND m.start_date < make_date(1789 + 2 * c.n, 1, 3)
 AND coalesce(m.end_date, 'infinity'::date) > make_date(1789 + 2 * (c.n - 1), 1, 3)
WHERE m.legislative_session_id IS NULL AND m.start_date IS NOT NULL
GROUP BY 1, 2
"""


def loaded_counts() -> dict[str, Any]:
    """Return everything the comparator needs from the warehouse in one read."""
    params = {"j": JURISDICTION}
    with session() as active:

        def rows(sql: str) -> list[Any]:
            return list(active.execute(text(sql), params).mappings())

        bills: dict[int, dict[str, int]] = {}
        for row in rows(_BILLS):
            bills.setdefault(int(row["congress"]), {})[row["bill_type"]] = row["n"]
        actions = {int(r["congress"]): r["n"] for r in rows(_ACTIONS)}
        roll_calls: dict[int, dict[str, dict[str, int]]] = {}
        for row in rows(_ROLL_CALLS):
            roll_calls.setdefault(int(row["congress"]), {})[row["chamber"]] = {
                "roll_calls": row["roll_calls"],
                "without_votes": row["without_votes"],
            }
        for row in rows(_MEMBER_VOTES):
            chamber = roll_calls.setdefault(int(row["congress"]), {}).setdefault(
                row["chamber"], {"roll_calls": 0, "without_votes": 0}
            )
            chamber["member_votes"] = row["n"]
        members: dict[int, set[str]] = {}
        for row in rows(_MEMBERSHIPS):
            members.setdefault(int(row["congress"]), set()).add(row["bioguide"])
        bioguide_ids = {
            r[0]
            for r in active.execute(
                text(
                    "SELECT external_id FROM core.person_identifier WHERE namespace = 'bioguide'"
                )
            )
        }
        unattributed, total = active.execute(
            text(
                "SELECT count(*) FILTER (WHERE code_version IS NULL), count(*) FROM ingest.run"
            )
        ).one()
        fec_estimate = active.execute(
            text("SELECT reltuples::bigint FROM pg_class WHERE oid = to_regclass('stage.fec_row')")
        ).scalar()
    return {
        "bills": bills,
        "actions": actions,
        "roll_calls": roll_calls,
        "memberships": members,
        "bioguide_ids": bioguide_ids,
        "runs_unattributed": unattributed,
        "runs_total": total,
        "fec_stage_rows_estimate": fec_estimate,
    }
