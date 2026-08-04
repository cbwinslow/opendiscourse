"""Immutable OpenStates pg_dump manifest and local validation helpers."""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
import subprocess
from typing import Any, Callable

import yaml

from .config import settings


REQUIRED_VOTE_TABLES = {
    "public.opencivicdata_legislativesession",
    "public.opencivicdata_voteevent",
    "public.opencivicdata_personvote",
}
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_TABLE_LINE = re.compile(r"\bTABLE\s+(\S+)\s+(\S+)\b")


def load_snapshot_manifest(path: Path) -> dict[str, Any]:
    """Load and validate a reviewed OpenStates source-snapshot manifest."""
    payload = yaml.safe_load(path.read_text()) or {}
    required = {
        "schema",
        "provider",
        "dataset",
        "artifact_key",
        "remote_url",
        "local_path",
        "period",
        "bytes",
        "checksum_sha256",
        "expected_tables",
    }
    missing = sorted(required - payload.keys())
    if missing:
        raise ValueError(f"snapshot manifest missing: {', '.join(missing)}")
    if payload["schema"] != 1 or payload["provider"] != "openstates":
        raise ValueError("snapshot manifest must identify schema 1 and provider openstates")
    if payload["dataset"] != "openstates.dump":
        raise ValueError("snapshot manifest must target openstates.dump")
    if not isinstance(payload["artifact_key"], str) or not payload["artifact_key"]:
        raise ValueError("snapshot manifest requires an artifact_key")
    if not isinstance(payload["remote_url"], str) or not payload["remote_url"].startswith("https://"):
        raise ValueError("snapshot manifest requires an HTTPS remote_url")
    if not isinstance(payload["local_path"], str) or not Path(payload["local_path"]).is_absolute():
        raise ValueError("snapshot manifest requires an absolute local_path")
    if not isinstance(payload["bytes"], int) or payload["bytes"] < 1:
        raise ValueError("snapshot manifest bytes must be a positive integer")
    if not isinstance(payload["checksum_sha256"], str) or not _SHA256.fullmatch(payload["checksum_sha256"]):
        raise ValueError("snapshot manifest checksum_sha256 must be a lowercase SHA-256")
    expected = payload["expected_tables"]
    if not isinstance(expected, list) or not REQUIRED_VOTE_TABLES.issubset(expected):
        raise ValueError("snapshot manifest must require the OpenStates vote tables")
    return payload


def checksum(path: Path) -> str:
    """Return a streaming SHA-256 checksum without loading a dump into memory."""
    digest = sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_snapshot_manifest(artifact: Path, period: str, remote_url: str) -> Path:
    """Create an immutable reviewed-manifest candidate for a downloaded dump."""
    if not artifact.is_file():
        raise FileNotFoundError(artifact)
    if not re.fullmatch(r"\d{4}-\d{2}", period):
        raise ValueError("period must use YYYY-MM")
    if not remote_url.startswith("https://"):
        raise ValueError("remote_url must use HTTPS")
    artifact_key = f"openstates-public-{period}"
    manifest = {
        "schema": 1,
        "provider": "openstates",
        "dataset": "openstates.dump",
        "artifact_key": artifact_key,
        "remote_url": remote_url,
        "local_path": str(artifact.resolve()),
        "period": period,
        "bytes": artifact.stat().st_size,
        "checksum_sha256": checksum(artifact),
        "source_watermark": None,
        "expected_tables": sorted(REQUIRED_VOTE_TABLES),
        "notes": (
            "Generated from an immutable local artifact. Validation does not authorize "
            "restore, FDW remapping, canonical loading, promotion, or scheduling."
        ),
    }
    target = (
        Path(settings.data_root).expanduser().resolve().parent
        / "meta"
        / "plan"
        / "openstates"
        / f"{artifact_key}.yaml"
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(".yaml.tmp")
    temporary.write_text(yaml.safe_dump(manifest, sort_keys=False))
    temporary.replace(target)
    return target


def archive_tables(path: Path) -> set[str]:
    """List table names in a pg_dump custom archive without restoring it."""
    completed = subprocess.run(
        ["pg_restore", "--list", str(path)],
        check=True,
        capture_output=True,
        text=True,
        timeout=120,
    )
    tables: set[str] = set()
    for line in completed.stdout.splitlines():
        match = _TABLE_LINE.search(line)
        if match:
            tables.add(f"{match.group(1)}.{match.group(2)}")
    return tables


def validate_snapshot_artifact(
    manifest_path: Path,
    *,
    table_lister: Callable[[Path], set[str]] = archive_tables,
) -> dict[str, Any]:
    """Verify a local dump's manifest, checksum, bytes, and required relations."""
    manifest = load_snapshot_manifest(manifest_path)
    artifact = Path(manifest["local_path"])
    if not artifact.is_file():
        raise FileNotFoundError(artifact)
    actual_bytes = artifact.stat().st_size
    if actual_bytes != manifest["bytes"]:
        raise ValueError(
            f"snapshot byte mismatch: expected {manifest['bytes']}, got {actual_bytes}"
        )
    actual_checksum = checksum(artifact)
    if actual_checksum != manifest["checksum_sha256"]:
        raise ValueError("snapshot checksum does not match the reviewed manifest")
    tables = table_lister(artifact)
    missing = sorted(set(manifest["expected_tables"]) - tables)
    if missing:
        raise ValueError(f"snapshot archive is missing required tables: {', '.join(missing)}")
    result = {
        "schema": 1,
        "kind": "openstates_snapshot_validation",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "manifest": str(manifest_path.resolve()),
        "artifact_key": manifest["artifact_key"],
        "local_path": str(artifact.resolve()),
        "bytes": actual_bytes,
        "checksum_sha256": actual_checksum,
        "required_tables": sorted(manifest["expected_tables"]),
        "archive_table_count": len(tables),
        "read_only": True,
        "next": "Review validation evidence before any staged restore or FDW mapping change.",
    }
    target = (
        Path(settings.data_root).expanduser().resolve().parent
        / "meta"
        / "plan"
        / "openstates"
        / f"{manifest['artifact_key']}-validation.json"
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    temporary.replace(target)
    result["report"] = str(target)
    return result
