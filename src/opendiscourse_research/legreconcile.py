"""Read-only reconciliation evidence for validated GovInfo BILLSTATUS archives."""
from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any
from xml.etree import ElementTree
import zipfile

from .config import settings
from .legarchive import billstatus_groups
from .repositories.legislation import bill_keys


def _output() -> Path:
    """Return the metadata-only reconciliation report directory."""
    return Path(settings.data_root).expanduser().resolve().parent / "meta" / "reconcile" / "billstatus"


def _bill_details(content: bytes) -> dict[str, Any] | None:
    """Extract only stable reconciliation fields from one BILLSTATUS XML member."""
    root = ElementTree.fromstring(content)
    bill = root.find("bill")
    if bill is None:
        return None
    congress, bill_type, number = bill.findtext("congress"), bill.findtext("type"), bill.findtext("number")
    if not congress or not bill_type or not number:
        return None
    sponsors = [
        item.findtext("bioguideId")
        for item in bill.findall("./sponsors/item")
        if item.findtext("bioguideId")
    ]
    return {
        "congress": int(congress),
        "bill_type": bill_type.lower(),
        "bill_number": number,
        "sponsors": sponsors,
        "actions": len(bill.findall("./actions/item")),
        "committees": len(bill.findall("./committees/item")),
        "subjects": len(bill.findall("./subjects/legislativeSubjects/item")),
        "documents": len(bill.findall("./textVersions/item")),
    }


def reconcile_billstatus(
    congress: int, limit: int | None = None, report: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    """Compare one complete BILLSTATUS cache to canonical bill keys without mutations."""
    if limit is not None and limit < 1:
        raise ValueError("limit must be positive")
    groups = billstatus_groups(congress)
    summary: Counter[str] = Counter()
    by_type: list[dict[str, Any]] = []
    malformed: list[str] = []
    processed = 0
    for group_index, group in enumerate(groups, start=1):
        bill_type = group["bill_type"]
        canonical = bill_keys(congress, bill_type)
        metrics: Counter[str] = Counter()
        with zipfile.ZipFile(group["archive"]) as archive:
            members = [member for member in archive.namelist() if member.endswith(".xml")]
            for member in members:
                if limit is not None and processed >= limit:
                    break
                try:
                    item = _bill_details(archive.read(member))
                except (OSError, ElementTree.ParseError, zipfile.BadZipFile) as exc:
                    malformed.append(f"{group['archive']}:{member}: {exc}")
                    continue
                if item is None or item["congress"] != congress or item["bill_type"] != bill_type:
                    malformed.append(f"{group['archive']}:{member}: invalid bill identity")
                    continue
                processed += 1
                metrics["xml_bills"] += 1
                metrics["canonical_bill_match"] += int(item["bill_number"] in canonical)
                metrics["canonical_bill_missing"] += int(item["bill_number"] not in canonical)
                metrics["sponsors"] += len(item["sponsors"])
                metrics["actions"] += item["actions"]
                metrics["committees"] += item["committees"]
                metrics["subjects"] += item["subjects"]
                metrics["documents"] += item["documents"]
        summary.update(metrics)
        by_type.append({
            "bill_type": bill_type,
            "archive": str(group["archive"]),
            "official_xml": group["official"]["official_xml"],
            "canonical_bills_available": len(canonical),
            **dict(metrics),
        })
        if report:
            report(f"Reconciling BILLSTATUS ({group_index}/{len(groups)}): {congress} {bill_type}; {processed} XML bills inspected")
        if limit is not None and processed >= limit:
            break
    result = {
        "schema": 1,
        "kind": "billstatusreconcile",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "read_only": True,
        "congress": congress,
        "limit": limit,
        "summary": dict(summary),
        "groups": by_type,
        "malformed": malformed,
        "next": "Review bill-key coverage before registering artifacts or loading BILLSTATUS relationships.",
    }
    target = _output() / f"{congress}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    temporary.replace(target)
    result["report"] = str(target)
    return result
