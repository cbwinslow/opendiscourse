"""Review-only GovInfo bulk backfill planning from validated official listings."""
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from time import monotonic, sleep
from typing import Any
import json

import httpx

from .capacity import RemoteObject, storage_preview
from .config import settings


PACE_SECONDS = 1.0
VALIDATION_REPORT = "validate/billstatus/latest.json"


def _meta_path(*parts: str) -> Path:
    """Return a path below the project's non-raw metadata lake."""
    return Path(settings.data_root).expanduser().resolve().parent / "meta" / Path(*parts)


def _validated_groups(congress: int) -> list[dict[str, Any]]:
    """Require a successful official comparison before planning a missing-file batch."""
    report = _meta_path(VALIDATION_REPORT)
    if not report.is_file():
        raise FileNotFoundError("Run `research-db validate billstatus --official --congress N` first")
    payload = json.loads(report.read_text())
    groups = [item for item in payload.get("official_comparison", []) if item.get("congress") == congress]
    if len(groups) != 8 or any("error" in group for group in groups):
        raise ValueError(f"No complete official BILLSTATUS comparison is available for Congress {congress}")
    return groups


def plan_billstatus_backfill(congress: int = 119, report: Callable[[str], None] | None = None) -> dict[str, Any]:
    """Create an exact, capacity-gated manifest for missing official BILLSTATUS XML files."""
    groups = _validated_groups(congress)
    validation = json.loads(_meta_path(VALIDATION_REPORT).read_text())
    listings = {
        (item["congress"], item["bill_type"]): Path(item["listing"])
        for item in validation["groups"]
    }
    files: list[dict[str, Any]] = []
    last_request = 0.0
    for position, group in enumerate(groups, start=1):
        bill_type = group["bill_type"]
        delay = PACE_SECONDS - (monotonic() - last_request)
        if delay > 0:
            sleep(delay)
        url = f"https://www.govinfo.gov/bulkdata/json/BILLSTATUS/{congress}/{bill_type}"
        response = httpx.get(url, headers={"Accept": "application/json"}, timeout=60)
        last_request = monotonic()
        response.raise_for_status()
        official = {item["name"]: item for item in response.json()["files"] if item.get("name", "").endswith(".xml")}
        # The official-comparison report stores only counts; exact local names
        # remain in the corresponding structural-validation listing artifact.
        local_listing = json.loads(listings[(congress, bill_type)].read_text())
        local = {item["name"] for item in local_listing["files"] if item.get("name", "").endswith(".xml")}
        for name in sorted(set(official) - local):
            item = official[name]
            files.append({"congress": congress, "bill_type": bill_type, "name": name, "url": item["link"], "bytes": item.get("size")})
        if report:
            report(f"Planning missing BILLSTATUS files ({position}/8): {congress} {bill_type}")
    preview = storage_preview(RemoteObject(item["url"], int(item["bytes"]) if item.get("bytes") is not None else None, "govinfo_listing") for item in files)
    result = {
        "schema": 1,
        "kind": "govinfobillstatusplan",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "read_only": True,
        "contract": "billstatus",
        "congress": congress,
        "files": files,
        "storage": preview,
        "next": "Review this manifest and explicitly approve the disabled billstatus contract before any download.",
    }
    output = _meta_path("plan", "govinfo")
    output.mkdir(parents=True, exist_ok=True)
    target = output / f"billstatus-{congress}-missing.json"
    temporary = target.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    temporary.replace(target)
    result["report"] = str(target)
    return result
