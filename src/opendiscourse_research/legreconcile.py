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
from .legvalidate import BILLSTATUS_ROOT, LISTING
from .repositories.legislation import bill_keys


def _output() -> Path:
    """Return the metadata-only reconciliation report directory."""
    return Path(settings.data_root).expanduser().resolve().parent / "meta" / "reconcile" / "billstatus"


def _complete_groups(congress: int) -> list[dict[str, Any]]:
    """Require official validation evidence before a cache is used as an input."""
    report = Path(settings.data_root).expanduser().resolve().parent / "meta" / "validate" / "billstatus" / "latest.json"
    if not report.is_file():
        raise FileNotFoundError("Run `research-db validate billstatus --official --all` before reconciliation")
    payload = json.loads(report.read_text())
    official = {
        item["bill_type"]: item
        for item in payload.get("official_comparison", [])
        if item.get("congress") == congress and item.get("matches_official") is True
    }
    groups: list[dict[str, Any]] = []
    for listing in sorted(BILLSTATUS_ROOT.rglob(f"BILLSTATUS_{congress}_*_listing.json")):
        match = LISTING.search(listing.name)
        if match is None:
            continue
        bill_type = match.group(2)
        if bill_type not in official:
            continue
        archive = listing.with_name(f"BILLSTATUS-{congress}-{bill_type}.zip")
        if archive.is_file():
            groups.append({"bill_type": bill_type, "archive": archive, "official": official[bill_type]})
    if not groups:
        raise ValueError(f"No officially complete local BILLSTATUS groups are available for Congress {congress}")
    return groups


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
    groups = _complete_groups(congress)
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
