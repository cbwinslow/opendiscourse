"""Loader for validated local GovInfo BILLSTATUS archives using repositories."""
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any
import zipfile

from .config import settings
from .legarchive import billstatus_groups
from .repositories.legislation import (
    ensure_us_legislative_session,
    parse_billstatus_xml,
    register_artifact,
    save_billstatus_bill,
)


def _output_path() -> Path:
    """Return the metadata load report directory."""
    return Path(settings.data_root).expanduser().resolve().parent / "meta" / "load" / "billstatus"


def load_billstatus(
    congress: int,
    *,
    limit: int | None = None,
    allow_partial: bool = False,
    report: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    """Stream and load validated local BILLSTATUS archives into Postgres legislation tables."""
    if limit is not None and limit < 1:
        raise ValueError("limit must be positive")

    groups = billstatus_groups(congress, allow_partial=allow_partial)

    is_partial = any(g.get("coverage") == "partial" for g in groups) or congress >= 119
    coverage = "partial" if is_partial else "complete"

    total_processed = 0
    by_type: list[dict[str, Any]] = []

    for group_index, group in enumerate(groups, start=1):
        if limit is not None and total_processed >= limit:
            break

        bill_type = group["bill_type"]
        archive_path = Path(group["archive"])

        hasher = hashlib.sha256()
        with archive_path.open("rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        checksum = hasher.hexdigest()
        file_size = archive_path.stat().st_size

        artifact = register_artifact(
            dataset_id="congress.govinfo_billstatus",
            remote_url=f"https://www.govinfo.gov/bulkdata/BILLSTATUS/{congress}/{bill_type}/BILLSTATUS-{congress}-{bill_type}.zip",
            local_path=str(archive_path.resolve()),
            artifact_key=f"BILLSTATUS-{congress}-{bill_type}.zip",
            status="loaded",
            checksum_sha256=checksum,
            bytes_downloaded=file_size,
            metadata={
                "congress": congress,
                "bill_type": bill_type,
                "coverage": group.get("coverage", "complete"),
            },
        )
        artifact_id = str(artifact["artifact_id"]) if artifact and "artifact_id" in artifact else None

        session_id = ensure_us_legislative_session(
            congress=congress,
            source_artifact_id=artifact_id,
            metadata={
                "congress": congress,
                "coverage": group.get("coverage", "complete"),
                "bill_type": bill_type,
            },
        )

        group_processed = 0
        with zipfile.ZipFile(archive_path) as archive:
            members = [member for member in archive.namelist() if member.endswith(".xml")]
            for member in members:
                if limit is not None and total_processed >= limit:
                    break
                content = archive.read(member)
                bill_data = parse_billstatus_xml(content, member_name=member)
                save_billstatus_bill(
                    bill_data=bill_data,
                    legislative_session_id=session_id,
                    source_artifact_id=artifact_id,
                    source_member=member,
                )
                total_processed += 1
                group_processed += 1
                if report:
                    report(
                        f"Loading BILLSTATUS ({group_index}/{len(groups)}): "
                        f"{congress} {bill_type}; {total_processed} bills saved"
                    )

        by_type.append({
            "bill_type": bill_type,
            "archive": str(archive_path),
            "coverage": group.get("coverage", "complete"),
            "processed": group_processed,
        })

    result = {
        "schema": 1,
        "kind": "billstatusload",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "congress": congress,
        "coverage": coverage,
        "allow_partial": allow_partial,
        "limit": limit,
        "processed": total_processed,
        "groups": by_type,
        "next": "Verify loaded bills using database queries.",
    }

    target = _output_path() / f"{congress}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    temp_target = target.with_suffix(".json.tmp")
    temp_target.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    temp_target.replace(target)
    result["report"] = str(target)

    return result
