from __future__ import annotations

from ..config import settings
from ..repositories.legislation import (
    resolve_bill_sponsorship_people,
    upsert_congress_person,
)
from .base import IngestionRun, client, json_response


def _upsert_bill(cur, bill: dict, payload_id: str) -> None:
    """Store the stable bill identity from either detail or collection responses."""
    congress = str(bill["congress"])
    bill_type = bill["type"].lower()
    bill_number = str(bill["number"])
    latest = bill.get("latestAction") or {}
    cur.execute(
        """INSERT INTO core.bill (jurisdiction, legislative_session, bill_type, bill_number, title, introduced_date, latest_action_date, latest_action, metadata)
           VALUES ('us', %s, %s, %s, %s, %s, %s, %s, %s)
           ON CONFLICT (jurisdiction, legislative_session, bill_type, bill_number) DO UPDATE SET
             title = EXCLUDED.title, introduced_date = COALESCE(EXCLUDED.introduced_date, core.bill.introduced_date),
             latest_action_date = EXCLUDED.latest_action_date, latest_action = EXCLUDED.latest_action,
             metadata = core.bill.metadata || EXCLUDED.metadata
           RETURNING bill_id""",
        (
            congress,
            bill_type,
            bill_number,
            bill.get("title"),
            bill.get("introducedDate"),
            latest.get("actionDate"),
            latest.get("text"),
            '{"source":"congress.gov"}',
        ),
    )


def ingest_bill(congress: int, bill_type: str, bill_number: int) -> int:
    if not settings.congress_api_key:
        raise ValueError("CONGRESS_API_KEY is required for Congress.gov ingestion")
    path = f"https://api.congress.gov/v3/bill/{congress}/{bill_type}/{bill_number}"
    with (
        client() as http,
        IngestionRun(
            "congress.legislation",
            {"congress": congress, "bill_type": bill_type, "bill_number": bill_number},
        ) as run,
    ):
        response = http.get(
            path, params={"api_key": settings.congress_api_key, "format": "json"}
        )
        payload = json_response(response)
        payload_id = run.store_payload(response, payload)
        bill = payload["bill"]
        with run.conn.cursor() as cur:
            _upsert_bill(cur, bill, payload_id)
            run.record_count = 1
        run.conn.commit()
        return run.record_count


def ingest_member(bioguide_id: str) -> int:
    """Fetch one primary Congress.gov member record and resolve linked sponsors."""
    if not settings.congress_api_key:
        raise ValueError("CONGRESS_API_KEY is required for Congress.gov ingestion")
    url = f"https://api.congress.gov/v3/member/{bioguide_id}"
    with (
        client() as http,
        IngestionRun(
            "congress.legislation", {"bioguide_id": bioguide_id}, mode="backfill"
        ) as run,
    ):
        response = http.get(
            url, params={"api_key": settings.congress_api_key, "format": "json"}
        )
        payload = json_response(response)
        run.store_payload(response, payload)
        member = payload["member"]
        upsert_congress_person(member, run.conn)
        run.record_count = resolve_bill_sponsorship_people(run.conn)
        run.conn.commit()
        return run.record_count


def ingest_bills(
    congress: int, max_records: int = 250, *, offset: int = 0, mode: str = "backfill"
) -> int:
    """Ingest bounded Congress.gov bill collection pages.

    This endpoint is deliberately bounded so historical loading remains an
    explicit operator decision. Re-running the command is safe because the
    natural Congress/type/number key is upserted.
    """
    if not settings.congress_api_key:
        raise ValueError("CONGRESS_API_KEY is required for Congress.gov ingestion")
    if max_records < 1 or offset < 0:
        raise ValueError("max_records must be positive and offset cannot be negative")
    url = f"https://api.congress.gov/v3/bill/{congress}"
    with (
        client() as http,
        IngestionRun(
            "congress.legislation",
            {"congress": congress, "max_records": max_records},
            mode=mode,
        ) as run,
    ):
        while run.record_count < max_records:
            limit = min(250, max_records - run.record_count)
            response = http.get(
                url,
                params={
                    "api_key": settings.congress_api_key,
                    "format": "json",
                    "limit": limit,
                    "offset": offset,
                    "sort": "updateDate+desc",
                },
            )
            payload = json_response(response)
            payload_id = run.store_payload(response, payload)
            bills = payload.get("bills", [])
            if not bills:
                break
            with run.conn.cursor() as cur:
                for bill in bills:
                    _upsert_bill(cur, bill, payload_id)
                    run.record_count += 1
            run.conn.commit()
            offset += len(bills)
            if len(bills) < limit:
                break
        return run.record_count
