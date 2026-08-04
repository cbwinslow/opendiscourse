"""Approved, resumable GovInfo BILLSTATUS missing-file backfill."""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
import json
from time import monotonic, sleep
from typing import Any
import zipfile

import httpx

from .contracts import get_contract
from .govplan import _meta_path
from .legvalidate import BILLSTATUS_ROOT, PACE_SECONDS, _validate_xml


def pending_archive_files(listing: dict[str, Any], members: set[str]) -> list[dict[str, Any]]:
    """Return listed XML members absent from a local BILLSTATUS ZIP archive."""
    pending: list[dict[str, Any]] = []
    for item in listing.get("files", []):
        name = item.get("name")
        if not isinstance(name, str) or not name.endswith(".xml") or name in members:
            continue
        if not isinstance(item.get("link"), str):
            raise ValueError(f"Listed XML member has no download URL: {name}")
        pending.append(item)
    return pending


def backfill_billstatus_missing(congress: int = 119, report: Callable[[str], None] | None = None) -> dict[str, Any]:
    """Append approved missing XML members, including ZIP/listing repair gaps."""
    contract = get_contract("billstatus")
    if not contract.get("enabled") or contract.get("approval") != "approved_missing_file_backfill":
        raise ValueError("119th BILLSTATUS backfill contract is not approved")
    manifest_path = _meta_path("plan", "govinfo") / f"billstatus-{congress}-missing.json"
    manifest = json.loads(manifest_path.read_text())
    if manifest.get("congress") != congress or not manifest.get("storage", {}).get("approved"):
        raise ValueError("Approved manifest and capacity preview are required")
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in manifest["files"]:
        groups[item["bill_type"]].append(item)
    downloaded = skipped = repaired = 0
    last_request = 0.0
    for position, (bill_type, files) in enumerate(sorted(groups.items()), start=1):
        listing_path = next(BILLSTATUS_ROOT.rglob(f"BILLSTATUS_{congress}_{bill_type}_listing.json"), None)
        if listing_path is None:
            raise FileNotFoundError(f"Missing local listing for {congress} {bill_type}")
        archive_path = listing_path.with_name(f"BILLSTATUS-{congress}-{bill_type}.zip")
        listing = json.loads(listing_path.read_text())
        known = {item["name"] for item in listing["files"]}
        with zipfile.ZipFile(archive_path, "a", compression=zipfile.ZIP_DEFLATED) as archive, httpx.Client(timeout=60, follow_redirects=True) as client:
            members = set(archive.namelist())
            pending = {item["name"]: item for item in files}
            for item in pending_archive_files(listing, members):
                pending[item["name"]] = item
            for item in pending.values():
                name = item["name"]
                url = item.get("url") or item.get("link")
                if not isinstance(url, str):
                    raise ValueError(f"Missing download URL for {name}")
                if name in members:
                    skipped += 1
                    if name not in known:
                        listing["files"].append({"name": name, "link": item["url"], "size": item.get("bytes")})
                        known.add(name)
                    continue
                delay = PACE_SECONDS - (monotonic() - last_request)
                if delay > 0:
                    sleep(delay)
                response = client.get(url)
                last_request = monotonic()
                response.raise_for_status()
                content = response.content
                if item.get("bytes") is not None and len(content) != int(item["bytes"]):
                    raise ValueError(f"Size mismatch for {name}: expected {item['bytes']}, got {len(content)}")
                if _validate_xml(content, congress, bill_type) is None:
                    raise ValueError(f"Invalid official XML identity for {name}")
                archive.writestr(name, content)
                if name not in known:
                    listing["files"].append({"name": name, "link": url, "size": item.get("bytes")})
                    known.add(name)
                else:
                    repaired += 1
                downloaded += 1
                if report:
                    report(f"Backfilling BILLSTATUS ({position}/{len(groups)}): {bill_type}; {downloaded}/{len(manifest['files'])} files")
        temporary = listing_path.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(listing, indent=2, sort_keys=True) + "\n")
        temporary.replace(listing_path)
    return {"congress": congress, "manifest": str(manifest_path), "downloaded": downloaded, "skipped": skipped, "repaired": repaired, "groups": len(groups)}
