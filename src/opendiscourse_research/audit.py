"""Read-only legacy-lake inventory for Congressional and GovInfo artifacts."""
from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Callable
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any
import json
import os
import re

from .config import settings


ROOTS: dict[str, tuple[str, str, str]] = {
    "congcache": (
        "/mnt/storage/data-lake/government/epstein/raw-files/congress",
        "congress.legislation",
        "legacy_cache_unverified",
    ),
    "conghist": (
        "/mnt/storage/data-lake/government/epstein/raw-files/congress_historical",
        "congress.legislation",
        "legacy_cache_unverified",
    ),
    "govcache": (
        "/mnt/storage/data-lake/government/epstein/raw-files/govinfo",
        "govinfo.bulk",
        "legacy_cache_unverified",
    ),
    "govbulk": (
        "/mnt/storage/data-lake/government/epstein/raw-files/govinfo_bulk",
        "govinfo.bulk",
        "legacy_cache_unverified",
    ),
    "congdata": (
        "/mnt/storage/data-lake/government/congress/congress-data",
        "congress.legislation",
        "legacy_cache_unverified",
    ),
    "congled": (
        "/mnt/storage/data-lake/government/ledgers/congress",
        "congress.legislation",
        "legacy_ledger_unverified",
    ),
    "govled": (
        "/mnt/storage/data-lake/government/ledgers/govinfo",
        "govinfo.bulk",
        "legacy_ledger_unverified",
    ),
}


def _checksum(path: Path) -> str:
    """Return a streaming SHA-256 checksum without loading the file in memory."""
    digest = sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _congress(path: Path) -> int | None:
    """Infer a Congress number only from an unambiguous path component."""
    parts = path.parts
    for index, part in enumerate(parts):
        match = re.fullmatch(r"congress_(\d{1,3})", part.lower())
        if match:
            return int(match.group(1))
        if part.lower() in {"congress-data", "billstatus", "billsum", "bills"} and index + 1 < len(parts):
            candidate = parts[index + 1]
            pattern = r"\d{1,3}" if part.lower() == "congress-data" else r"\d{3}"
            if re.fullmatch(pattern, candidate):
                return int(candidate)
    return None


def _collection(path: Path, dataset_id: str) -> str | None:
    """Infer the GovInfo collection family from known, non-authoritative paths."""
    if dataset_id != "govinfo.bulk":
        return None
    parts = {part.lower() for part in path.parts}
    for collection in ("billstatus", "billsum", "bills"):
        if collection in parts:
            return collection.upper()
    return None


def _files(root: Path) -> list[Path]:
    """Collect regular files without following links outside the requested root."""
    found: list[Path] = []
    for directory, _children, names in os.walk(root, followlinks=False):
        base = Path(directory)
        for name in names:
            candidate = base / name
            if candidate.is_file() and not candidate.is_symlink():
                found.append(candidate)
    return found


def _report_path() -> Path:
    """Return the non-raw metadata location for the stable latest audit report."""
    return Path(settings.data_root).expanduser().resolve().parent / "meta" / "audit" / "leg"


def audit_leg(hash_files: bool = False, report: Callable[[str], None] | None = None) -> dict[str, Any]:
    """Inventory known legislative legacy roots without copying, parsing, or registering files."""
    generated_at = datetime.now(timezone.utc).isoformat()
    entries: list[dict[str, Any]] = []
    roots: list[dict[str, Any]] = []
    all_files: list[tuple[str, Path, str, str]] = []
    for root_id, (raw_path, dataset_id, provenance) in ROOTS.items():
        root = Path(raw_path)
        files = _files(root) if root.is_dir() else []
        roots.append({
            "id": root_id,
            "path": str(root),
            "dataset_id": dataset_id,
            "provenance": provenance,
            "exists": root.is_dir(),
            "files": len(files),
        })
        all_files.extend((root_id, path, dataset_id, provenance) for path in files)

    total = len(all_files)
    by_root: dict[str, Counter[str]] = defaultdict(Counter)
    by_congress: dict[str, Counter[int]] = defaultdict(Counter)
    by_collection: dict[str, Counter[str]] = defaultdict(Counter)
    by_coverage: dict[str, Counter[str]] = defaultdict(Counter)
    for position, (root_id, path, dataset_id, provenance) in enumerate(all_files, start=1):
        stat = path.stat()
        suffix = path.suffix.lower().lstrip(".") or "none"
        congress = _congress(path)
        collection = _collection(path, dataset_id)
        entry = {
            "root_id": root_id,
            "dataset_id": dataset_id,
            "provenance": provenance,
            "path": str(path),
            "bytes": stat.st_size,
            "modified_at": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
            "format": suffix,
            "congress": congress,
            "collection": collection,
        }
        if hash_files:
            entry["checksum_sha256"] = _checksum(path)
        entries.append(entry)
        by_root[root_id]["files"] += 1
        by_root[root_id]["bytes"] += stat.st_size
        by_root[root_id][f"format:{suffix}"] += 1
        if congress is not None:
            by_congress[root_id][congress] += 1
        if collection:
            by_collection[root_id][collection] += 1
            if congress is not None:
                by_coverage[root_id][f"{collection}:{congress}"] += 1
        if report:
            report(f"Auditing legislative artifacts ({position}/{total}): {root_id}")

    for root in roots:
        root_id = root["id"]
        summary = by_root[root_id]
        root["bytes"] = summary["bytes"]
        root["formats"] = {key.removeprefix("format:"): value for key, value in summary.items() if key.startswith("format:")}
        root["congresses"] = dict(sorted(by_congress[root_id].items()))
        root["collections"] = dict(sorted(by_collection[root_id].items()))
        root["coverage"] = dict(sorted(by_coverage[root_id].items()))
    result = {
        "schema": 1,
        "kind": "legacyaudit",
        "generated_at": generated_at,
        "hashes": hash_files,
        "read_only": True,
        "roots": roots,
        "files": entries,
        "summary": {
            "files": total,
            "bytes": sum(entry["bytes"] for entry in entries),
            "formats": dict(sorted(Counter(entry["format"] for entry in entries).items())),
            "congresses": dict(sorted(Counter(entry["congress"] for entry in entries if entry["congress"] is not None).items())),
            "collections": dict(sorted(Counter(entry["collection"] for entry in entries if entry["collection"]).items())),
        },
    }
    output = _report_path()
    output.mkdir(parents=True, exist_ok=True)
    latest = output / "latest.json"
    temporary = latest.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    temporary.replace(latest)
    summary_path = output / "summary.json"
    summary = {key: result[key] for key in ("schema", "kind", "generated_at", "hashes", "read_only", "roots", "summary")}
    summary_temp = summary_path.with_suffix(".json.tmp")
    summary_temp.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    summary_temp.replace(summary_path)
    result["report"] = str(latest)
    result["summary_report"] = str(summary_path)
    return result
