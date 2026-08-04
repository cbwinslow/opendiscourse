"""Canonical people seeding from the approved OpenStates reference snapshot."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from .config import settings
from .ingestion.base import IngestionRun
from .repositories.legislation import (
    get_resume_cursor,
    load_openstates_votes as persist_openstates_votes,
    register_artifact,
    resolve_bill_sponsorship_people,
    save_resume_cursor,
    sync_openstates_federal_organizations,
    sync_openstates_federal_people,
)


def load_openstates_votes(
    congress: int,
    limit: int = 1,
    page_size: int = 25,
    *,
    resume: bool = False,
) -> dict[str, Any]:
    """Load a bounded congressional vote batch in committed keyset pages."""
    if limit < 1 or page_size < 1:
        raise ValueError("limit and page_size must be positive")
    cursor_key = f"openstatesvotes:{congress}"
    parameters = {
        "congress": congress,
        "limit": limit,
        "page_size": page_size,
        "resume": resume,
        "role": "vote_backfill",
    }
    with IngestionRun("openstates.legislation", parameters, mode="backfill") as run:
        assert run.conn is not None
        artifact = register_artifact("openstates.legislation", "openstates_source://opencivicdata_voteevent", "openstates_source.opencivicdata_voteevent", f"federal-votes-{congress}", status="loaded", metadata={"congress": congress}, conn=run.conn)
        counts = {"roll_calls": 0, "member_votes": 0, "unresolved_people": 0}
        checkpoint = get_resume_cursor("openstates.legislation", cursor_key, run.conn)
        cursor = (
            (checkpoint or {}).get("cursor", {}).get("last_ocd_id")
            if resume
            else None
        )
        resumed_from = cursor
        remaining, pages, state = limit, 0, "paused"
        while remaining:
            page = persist_openstates_votes(congress, min(page_size, remaining), str(artifact["artifact_id"]), run.conn, cursor)
            if not page["roll_calls"]:
                state = "complete"
                break
            pages += 1
            cursor = page["last_ocd_id"]
            remaining -= page["roll_calls"]
            for key in counts:
                counts[key] += page[key]
            run.record_count = counts["roll_calls"]
            save_resume_cursor(
                "openstates.legislation",
                cursor_key,
                {"last_ocd_id": cursor},
                str(artifact["artifact_id"]),
                str(run.run_id),
                "running",
                run.conn,
            )
            run.conn.commit()
        save_resume_cursor(
            "openstates.legislation",
            cursor_key,
            {"last_ocd_id": cursor} if cursor else {},
            str(artifact["artifact_id"]),
            str(run.run_id),
            state,
            run.conn,
        )
        if congress >= 119:
            run.mark_partial()
        run.conn.commit()
    return {
        **counts,
        "pages": pages,
        "resumed_from": resumed_from,
        "next_cursor": cursor,
        "checkpoint_state": state,
        "resume_command": f"research-db load-openstates-votes --congress {congress} --limit {limit} --resume",
        "coverage": "partial" if congress >= 119 else "complete",
    }


def load_openstates_federal_people() -> dict[str, Any]:
    """Load the federal OpenStates people baseline without modifying its source snapshot."""
    parameters = {
        "source": "openstates_source.opencivicdata_person",
        "jurisdiction": "ocd-jurisdiction/country:us/government",
        "role": "canonical_baseline",
    }
    with IngestionRun("openstates.legislation", parameters, mode="backfill") as run:
        assert run.conn is not None
        counts = sync_openstates_federal_people(run.conn)
        counts["sponsorship_links_resolved"] = resolve_bill_sponsorship_people(run.conn)
        run.record_count = counts["people"]
        run.conn.commit()

    result = {
        "schema": 1,
        "kind": "openstates_people_load",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        **counts,
        "next": "Enrich people from Congress.gov without replacing OpenStates baseline identities.",
    }
    target = (
        Path(settings.data_root).expanduser().resolve().parent
        / "meta"
        / "load"
        / "openstates-people.json"
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    result["report"] = str(target)
    return result


def load_openstates_federal_organizations() -> dict[str, Any]:
    """Load baseline federal organizations and stable OCD identifiers."""
    with IngestionRun(
        "openstates.legislation",
        {
            "source": "openstates_source.opencivicdata_organization",
            "jurisdiction": "ocd-jurisdiction/country:us/government",
            "role": "canonical_baseline",
        },
        mode="backfill",
    ) as run:
        assert run.conn is not None
        organizations = sync_openstates_federal_organizations(run.conn)
        run.record_count = organizations
        run.conn.commit()
    return {
        "schema": 1,
        "kind": "openstates_organizations_load",
        "organizations": organizations,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
