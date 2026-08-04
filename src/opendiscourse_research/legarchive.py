"""Validated local legislative archive discovery shared by source adapters."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .config import settings
from .legvalidate import BILLSTATUS_ROOT, LISTING


def billstatus_groups(congress: int, *, allow_partial: bool = False) -> list[dict[str, Any]]:
    """Return validated local BILLSTATUS archives, enforcing the coverage gate."""
    report = Path(settings.data_root).expanduser().resolve().parent / "meta" / "validate" / "billstatus" / "latest.json"
    if not report.is_file():
        raise FileNotFoundError("Run `research-db validate billstatus --official --all` before loading")
    payload = json.loads(report.read_text())
    comparisons = {
        item["bill_type"]: item
        for item in payload.get("official_comparison", [])
        if item.get("congress") == congress
    }
    if not comparisons:
        raise ValueError(f"No official BILLSTATUS validation is available for Congress {congress}")
    incomplete = [
        kind
        for kind, item in comparisons.items()
        if item.get("archive_matches_official") is not True
    ]
    if incomplete and not allow_partial:
        raise ValueError(
            f"Congress {congress} cache is partial ({', '.join(sorted(incomplete))}); pass --allow-partial to proceed"
        )
    groups: list[dict[str, Any]] = []
    for listing in sorted(BILLSTATUS_ROOT.rglob(f"BILLSTATUS_{congress}_*_listing.json")):
        match = LISTING.search(listing.name)
        if match is None or match.group(2) not in comparisons:
            continue
        bill_type = match.group(2)
        archive = listing.with_name(f"BILLSTATUS-{congress}-{bill_type}.zip")
        if archive.is_file():
            groups.append({
                "bill_type": bill_type,
                "archive": archive,
                "coverage": "complete" if comparisons[bill_type].get("matches_official") else "partial",
                "official": comparisons[bill_type],
            })
    if not groups:
        raise ValueError(f"No local BILLSTATUS archives are available for Congress {congress}")
    return groups
