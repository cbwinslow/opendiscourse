"""Read-only structural validation for legacy GovInfo BILLSTATUS artifacts."""
from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from xml.etree import ElementTree
import json
import re
from time import monotonic, sleep
import zipfile

import httpx

from .config import settings


BILLSTATUS_ROOT = Path("/mnt/storage/data-lake/government/epstein/raw-files/govinfo_bulk/billstatus")
LISTING = re.compile(r"BILLSTATUS_(\d+)_(hconres|hjres|hr|hres|s|sconres|sjres|sres)_listing\.json$")
PACE_SECONDS = 1.0


def _output() -> Path:
    """Return the metadata-only validation-report location."""
    return Path(settings.data_root).expanduser().resolve().parent / "meta" / "validate" / "billstatus"


def _validate_xml(content: bytes, congress: int, bill_type: str) -> dict[str, Any] | None:
    """Parse one XML member and confirm its native deterministic bill identity."""
    root = ElementTree.fromstring(content)
    bill = root.find("bill")
    if bill is None:
        return None
    found_congress = bill.findtext("congress")
    found_type = bill.findtext("type")
    number = bill.findtext("number")
    if found_congress != str(congress) or (found_type or "").lower() != bill_type or not number:
        return None
    return {"congress": congress, "bill_type": bill_type, "bill_number": number}


def _official_compare(groups: list[dict[str, Any]], congress: int, report: Callable[[str], None] | None) -> list[dict[str, Any]]:
    """Compare one Congress's cached listings to paced official GovInfo directory JSON."""
    compared: list[dict[str, Any]] = []
    last_request = 0.0
    for position, group in enumerate((item for item in groups if item["congress"] == congress), start=1):
        delay = PACE_SECONDS - (monotonic() - last_request)
        if delay > 0:
            sleep(delay)
        bill_type = group["bill_type"]
        url = f"https://www.govinfo.gov/bulkdata/json/BILLSTATUS/{congress}/{bill_type}"
        try:
            response = httpx.get(url, headers={"Accept": "application/json"}, timeout=60)
            last_request = monotonic()
            response.raise_for_status()
            official = {item["name"] for item in response.json()["files"] if item.get("name", "").endswith(".xml")}
            local = {item["name"] for item in json.loads(Path(group["listing"]).read_text())["files"] if item.get("name", "").endswith(".xml")}
            compared.append({
                "congress": congress, "bill_type": bill_type, "url": url,
                "official_xml": len(official), "local_listing_xml": len(local),
                "matches_official": local == official,
                "missing_from_local_listing": len(official - local),
                "extra_in_local_listing": len(local - official),
            })
        except (httpx.HTTPError, OSError, ValueError, KeyError, TypeError) as exc:
            compared.append({"congress": congress, "bill_type": bill_type, "url": url, "error": str(exc)})
        if report:
            report(f"Comparing official BILLSTATUS listings ({position}/8): {congress} {bill_type}")
    return compared


def validate_billstatus(
    sample: int = 2, official_congresses: tuple[int, ...] = (), report: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    """Validate every local listing/ZIP pair and sample XML identities without mutation."""
    if sample < 1:
        raise ValueError("sample must be positive")
    listings = sorted(path for path in BILLSTATUS_ROOT.rglob("*_listing.json") if LISTING.search(path.name))
    groups: list[dict[str, Any]] = []
    identities: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    for index, listing in enumerate(listings, start=1):
        match = LISTING.search(listing.name)
        assert match is not None
        congress, bill_type = int(match.group(1)), match.group(2)
        try:
            payload = json.loads(listing.read_text())
            expected = {item["name"] for item in payload["files"] if item.get("name", "").endswith(".xml")}
        except (OSError, ValueError, KeyError, TypeError) as exc:
            errors.append({"path": str(listing), "error": f"listing: {exc}"})
            continue
        archive = listing.with_name(f"BILLSTATUS-{congress}-{bill_type}.zip")
        result: dict[str, Any] = {
            "congress": congress,
            "bill_type": bill_type,
            "listing": str(listing),
            "listed_xml": len(expected),
            "archive": str(archive),
            "archive_exists": archive.is_file(),
        }
        if not archive.is_file():
            errors.append({"path": str(archive), "error": "archive missing"})
            groups.append(result)
            continue
        try:
            with zipfile.ZipFile(archive) as bundle:
                members = [name for name in bundle.namelist() if name.endswith(".xml")]
                result["archive_xml"] = len(members)
                result["listing_matches_archive"] = expected == set(members)
                for member in members[:sample]:
                    identity = _validate_xml(bundle.read(member), congress, bill_type)
                    if identity is None:
                        errors.append({"path": f"{archive}:{member}", "error": "invalid or mismatched bill identity"})
                    else:
                        identities.append(identity)
        except (OSError, zipfile.BadZipFile, ElementTree.ParseError) as exc:
            errors.append({"path": str(archive), "error": str(exc)})
        groups.append(result)
        if report:
            report(f"Validating BILLSTATUS groups ({index}/{len(listings)}): {congress} {bill_type}")
    mismatch = [group for group in groups if group.get("listing_matches_archive") is False]
    result = {
        "schema": 1,
        "kind": "billstatusvalidate",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "read_only": True,
        "sample_per_group": sample,
        "groups": groups,
        "sample_identities": identities,
        "summary": {
            "groups": len(groups),
            "listed_xml": sum(group["listed_xml"] for group in groups),
            "archive_xml": sum(group.get("archive_xml", 0) for group in groups),
            "sample_identities": len(identities),
            "mismatched_groups": len(mismatch),
            "errors": len(errors),
            "by_congress": dict(sorted(Counter(group["congress"] for group in groups).items())),
        },
        "errors": errors,
    }
    if official_congresses:
        result["official_comparison"] = [
            comparison
            for congress in official_congresses
            for comparison in _official_compare(groups, congress, report)
        ]
        archive_by_key = {
            (group["congress"], group["bill_type"]): group
            for group in groups
        }
        for comparison in result["official_comparison"]:
            archive = archive_by_key.get((comparison["congress"], comparison["bill_type"]), {})
            comparison["archive_matches_official"] = (
                comparison.get("matches_official") is True
                and archive.get("listing_matches_archive") is True
            )
    output = _output()
    output.mkdir(parents=True, exist_ok=True)
    target = output / "latest.json"
    temporary = target.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    temporary.replace(target)
    result["report"] = str(target)
    return result
