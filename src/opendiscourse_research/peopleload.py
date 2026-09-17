"""Canonical people seeding from the approved OpenStates reference snapshot."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .config import settings
from .db import connect
from .ingestion.base import IngestionRun
from .repositories.legislation import (
    get_resume_cursor,
    promote_openstates_federal,
    record_vote_identity_exceptions,
    register_artifact,
    resolve_bill_sponsorship_people,
    save_resume_cursor,
    sync_openstates_federal_organizations,
    sync_openstates_federal_people,
)
from .repositories.legislation import (
    load_openstates_votes as persist_openstates_votes,
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
    with (
        IngestionRun("openstates.legislation", parameters, mode="backfill") as run,
        connect() as conn,
    ):
        artifact = register_artifact(
            "openstates.legislation",
            "openstates_source://opencivicdata_voteevent",
            "openstates_source.opencivicdata_voteevent",
            f"federal-votes-{congress}",
            status="loaded",
            metadata={"congress": congress},
            conn=conn,
        )
        counts = {"roll_calls": 0, "member_votes": 0, "unresolved_people": 0}
        checkpoint = get_resume_cursor("openstates.legislation", cursor_key, conn)
        cursor = (
            (checkpoint or {}).get("cursor", {}).get("last_ocd_id") if resume else None
        )
        resumed_from = cursor
        remaining, pages, state = limit, 0, "paused"
        while remaining:
            page = persist_openstates_votes(
                congress,
                min(page_size, remaining),
                str(artifact["artifact_id"]),
                conn,
                cursor,
            )
            if not page["roll_calls"]:
                state = "complete"
                break
            pages += 1
            cursor = page["last_ocd_id"]
            remaining -= page["roll_calls"]
            for key in counts:
                counts[key] += page[key]
            record_vote_identity_exceptions(
                congress,
                str(artifact["artifact_id"]),
                str(run.run_id),
                page.get("unresolved_voter_ids", []),
                conn,
            )
            run.record_count = counts["roll_calls"]
            save_resume_cursor(
                "openstates.legislation",
                cursor_key,
                {"last_ocd_id": cursor},
                str(artifact["artifact_id"]),
                str(run.run_id),
                "running",
                conn,
            )
            conn.commit()
        save_resume_cursor(
            "openstates.legislation",
            cursor_key,
            {"last_ocd_id": cursor} if cursor else {},
            str(artifact["artifact_id"]),
            str(run.run_id),
            state,
            conn,
        )
        if congress >= 119:
            run.mark_partial()
        conn.commit()
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
    with (
        IngestionRun("openstates.legislation", parameters, mode="backfill") as run,
        connect() as conn,
    ):
        counts = sync_openstates_federal_people(conn)
        counts["sponsorship_links_resolved"] = resolve_bill_sponsorship_people(conn)
        run.record_count = counts["people"]
        conn.commit()

    result = {
        "schema": 1,
        "kind": "openstates_people_load",
        "generated_at": datetime.now(UTC).isoformat(),
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
    with (
        IngestionRun(
            "openstates.legislation",
            {
                "source": "openstates_source.opencivicdata_organization",
                "jurisdiction": "ocd-jurisdiction/country:us/government",
                "role": "canonical_baseline",
            },
            mode="backfill",
        ) as run,
        connect() as conn,
    ):
        organizations = sync_openstates_federal_organizations(conn)
        run.record_count = organizations
        conn.commit()
    return {
        "schema": 1,
        "kind": "openstates_organizations_load",
        "organizations": organizations,
        "generated_at": datetime.now(UTC).isoformat(),
    }


def find_latest_openstates_manifest() -> Path | None:
    """Discover the newest reviewed OpenStates snapshot manifest if one exists."""
    plan_dir = (
        Path(settings.data_root).expanduser().resolve().parent
        / "meta"
        / "plan"
        / "openstates"
    )
    if not plan_dir.is_dir():
        return None
    candidates = sorted(plan_dir.glob("openstates-public-*.yaml"))
    return candidates[-1] if candidates else None


def load_openstates_federal_promote(
    manifest_path: Path | str | None = None,
) -> dict[str, Any]:
    """Promote federal OpenStates sessions and occupancy into owned core tables."""
    parameters = {
        "source": "openstates_source",
        "jurisdiction": "ocd-jurisdiction/country:us/government",
        "role": "federal_promote",
    }
    target_manifest = Path(manifest_path) if manifest_path else find_latest_openstates_manifest()
    manifest: dict[str, Any] | None = None
    if target_manifest and target_manifest.is_file():
        try:
            from .openstatessnapshot import load_snapshot_manifest

            manifest = load_snapshot_manifest(target_manifest)
        except (ValueError, KeyError, OSError):
            manifest = None

    with (
        IngestionRun("openstates.legislation", parameters, mode="backfill") as run,
        connect() as conn,
    ):
        if manifest:
            artifact = register_artifact(
                manifest["dataset"],
                manifest["remote_url"],
                manifest["local_path"],
                manifest["artifact_key"],
                status="loaded",
                checksum_sha256=manifest["checksum_sha256"],
                bytes_downloaded=manifest["bytes"],
                metadata={
                    "jurisdiction": parameters["jurisdiction"],
                    "period": manifest["period"],
                    "manifest": str(target_manifest.resolve()) if target_manifest else None,
                    "role": "federal_promote",
                },
                conn=conn,
            )
        else:
            artifact = register_artifact(
                "openstates.dump",
                "openstates_source://dump-snapshot",
                "openstates_source.opencivicdata",
                "openstates-dump-snapshot",
                status="loaded",
                metadata={
                    "jurisdiction": parameters["jurisdiction"],
                    "role": "snapshot_fdw_promote",
                },
                conn=conn,
            )
        counts = promote_openstates_federal(
            str(artifact["artifact_id"]),
            str(run.run_id),
            conn,
        )
        run.record_count = counts.get("memberships", 0) + counts.get("sessions", 0)
        conn.commit()
    return {
        "schema": 1,
        "kind": "openstates_federal_promote",
        "generated_at": datetime.now(UTC).isoformat(),
        "artifact_id": str(artifact["artifact_id"]),
        "artifact_key": artifact.get("artifact_key"),
        **counts,
    }
