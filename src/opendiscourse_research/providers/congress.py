"""Congress/GovInfo catalog adapter built from audited local coverage only."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..config import settings
from ..repositories.catalog import delete_resources_prefix, upsert_resource

CONGRESS_RESOURCES = (
    ("members", "Members", "Congress.gov member records keyed by BioGuide ID."),
    ("bills", "Bills", "Congress.gov bill metadata and source links."),
    ("actions", "Bill actions", "Congress.gov bill action history."),
    ("amendments", "Amendments", "Congress.gov amendment metadata and links."),
    ("committees", "Committees", "Congress.gov committee assignments and bill links."),
    (
        "housevotes",
        "House votes",
        "Congress.gov House roll-call metadata and member positions.",
    ),
)
GOVINFO_COLLECTIONS = ("BILLSTATUS", "BILLS", "BILLSUM")


def _summary_path() -> Path:
    """Return the compact result of the read-only legislative audit."""
    return (
        Path(settings.data_root).expanduser().resolve().parent
        / "meta"
        / "audit"
        / "leg"
        / "summary.json"
    )


def _audit() -> dict[str, Any] | None:
    """Load audit metadata without reopening its potentially large file manifest."""
    path = _summary_path()
    return json.loads(path.read_text()) if path.is_file() else None


def sync() -> dict[str, Any]:
    """Publish audited legislative coverage and official API offerings to the browser."""
    audit = _audit()
    if audit is None:
        return {
            "state": "needs_audit",
            "next": "Run `research-db audit` before browsing legacy legislative coverage.",
        }
    api_resources = 0
    for congress in range(1, 120):
        for resource_type, title, summary in CONGRESS_RESOURCES:
            upsert_resource(
                "congress.legislation",
                f"api:{congress}:{resource_type}",
                resource_type,
                f"{congress}th Congress — {title}",
                summary,
                congress,
                {
                    "source": "Congress.gov API",
                    "congress": congress,
                    "coverage": "official_candidate",
                    "ingest_state": "draft_only",
                },
            )
            api_resources += 1
    coverage: dict[tuple[str, int], dict[str, Any]] = {}
    for root in audit["roots"]:
        if root["dataset_id"] != "govinfo.bulk":
            continue
        for key, files in root.get("coverage", {}).items():
            collection, congress_text = key.split(":", 1)
            congress = int(congress_text)
            entry = coverage.setdefault(
                (collection, congress), {"files": 0, "roots": []}
            )
            entry["files"] += files
            entry["roots"].append(root["id"])
    # Earlier provisional resources used one key per legacy root. They are
    # derived browser metadata only, so removing them cannot affect evidence.
    delete_resources_prefix("govinfo.bulk", "legacy:%")
    bulk_resources = 0
    billstatus_resources = 0
    for congress in range(1, 120):
        for collection in GOVINFO_COLLECTIONS:
            local = coverage.get((collection, congress))
            metadata: dict[str, Any] = {
                "source": "GovInfo bulk",
                "collection": collection,
                "congress": congress,
                "coverage": "official_candidate",
                "ingest_state": "draft_only",
            }
            summary = "Official bulk candidate; resolve the publisher manifest and storage estimate before ingestion."
            if local:
                metadata.update(
                    {
                        "legacy_files": local["files"],
                        "legacy_roots": local["roots"],
                        "provenance": "legacy_cache_unverified",
                        "ingest_state": "verify_required",
                    }
                )
                summary = f"Official bulk candidate; {local['files']} audited legacy files are available for verification first."
            upsert_resource(
                "govinfo.bulk",
                f"govinfo:{collection}:{congress}",
                collection,
                f"{congress}th Congress — GovInfo {collection}",
                summary,
                congress,
                metadata,
            )
            bulk_resources += 1
            if collection == "BILLSTATUS":
                upsert_resource(
                    "congress.govinfo_billstatus",
                    f"govinfo:BILLSTATUS:{congress}",
                    "BILLSTATUS",
                    f"{congress}th Congress — GovInfo BILLSTATUS",
                    summary,
                    congress,
                    metadata,
                )
                billstatus_resources += 1
    return {
        "state": "synced",
        "audit": str(_summary_path()),
        "congress_api_resources": api_resources,
        "govinfo_candidate_resources": bulk_resources,
        "billstatus_candidate_resources": billstatus_resources,
        "legacy_covered_groups": len(coverage),
    }
