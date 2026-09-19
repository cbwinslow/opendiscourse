"""Connector for ``unitedstates/congress-legislators``: the BioGuide crosswalk.

Reads the two legislator YAML files from the ``vendor/`` checkout, retains
verified copies as immutable artifacts, and promotes identifiers into
``core.person_identifier`` keyed on BioGuide only (Story 3.1). Terms,
committees and social media are out of scope.
"""

from __future__ import annotations

import json
import re
import subprocess
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

import yaml

from ..artifact_storage import file_checksum, retain_artifact_bytes, retained_path
from ..config import settings
from ..db import connect
from ..repositories.legislation import register_artifact
from ..repositories.people import promote_legislators
from .base import IngestionRun
from .connector import ConnectorContext

SOURCE_ID = "congress.legislators"
UPSTREAM = "https://raw.githubusercontent.com/unitedstates/congress-legislators"
FILES = ("legislators-current.yaml", "legislators-historical.yaml")
BIOGUIDE = re.compile(r"^[A-Z]\d{6}$")
VENDOR_DIR = Path(__file__).resolve().parents[3] / "vendor" / "congress-legislators"

_Loader = getattr(yaml, "CSafeLoader", yaml.SafeLoader)


@dataclass(frozen=True)
class Legislator:
    """One legislator's identity as asserted by a source file."""

    bioguide: str
    full_name: str
    given_name: str | None
    family_name: str | None
    identifiers: tuple[tuple[str, str], ...]


def parse_legislators(content: bytes | str) -> list[Legislator]:
    """Parse one upstream YAML file. Identifier namespaces are the upstream keys."""
    records = yaml.load(content, Loader=_Loader)
    if not isinstance(records, list):
        raise ValueError("legislator file must be a YAML list")
    people: list[Legislator] = []
    for index, record in enumerate(records):
        ids = (record or {}).get("id") or {}
        bioguide = str(ids.get("bioguide") or "").strip()
        if not bioguide:
            raise ValueError(f"legislator #{index} has no bioguide id")
        name = record.get("name") or {}
        given, family = name.get("first"), name.get("last")
        full = name.get("official_full") or " ".join(p for p in (given, family) if p)
        pairs: list[tuple[str, str]] = []
        for namespace, value in ids.items():
            for item in value if isinstance(value, list) else [value]:
                if item is not None and str(item).strip():
                    pairs.append((str(namespace), str(item).strip()))
        people.append(
            Legislator(bioguide, full or bioguide, given, family, tuple(pairs))
        )
    return people


def validate_legislators(people_by_file: dict[str, list[Legislator]]) -> None:
    """Fail closed on structure that would corrupt identity, before any write."""
    seen: dict[str, str] = {}
    for name, people in people_by_file.items():
        if not people:
            raise ValueError(f"{name} contains no legislators; refusing to load")
        for person in people:
            if not BIOGUIDE.match(person.bioguide):
                raise ValueError(f"{name}: malformed BioGuide id {person.bioguide!r}")
            if person.bioguide in seen:
                first = seen[person.bioguide]
                where = f"{name}" if first == name else f"both {first} and {name}"
                raise ValueError(f"BioGuide id {person.bioguide} is repeated in {where}")
            seen[person.bioguide] = name


def dedupe_identifiers(
    people: list[Legislator],
) -> tuple[list[Legislator], list[dict[str, Any]]]:
    """Drop non-BioGuide ids that upstream gives to two legislators; report them."""
    owners: dict[tuple[str, str], set[str]] = defaultdict(set)
    for person in people:
        for pair in person.identifiers:
            owners[pair].add(person.bioguide)
    shared = {pair for pair, who in owners.items() if len(who) > 1}
    report = [
        {"namespace": ns, "external_id": ext, "bioguide_ids": sorted(owners[(ns, ext)])}
        for ns, ext in sorted(shared)
    ]
    kept = [
        Legislator(
            p.bioguide,
            p.full_name,
            p.given_name,
            p.family_name,
            tuple(pair for pair in dict.fromkeys(p.identifiers) if pair not in shared),
        )
        for p in people
    ]
    return kept, report


def _git(vendor: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(vendor), *args], capture_output=True, text=True, check=False
    )
    if result.returncode:
        raise RuntimeError(
            f"{vendor} is not a usable git checkout ({result.stderr.strip()}). "
            "Run scripts/bootstrap_upstream.sh."
        )
    return result.stdout.strip()


class LegislatorsConnector:
    """Ten-stage Connector; publishes one transaction so a failure changes nothing."""

    source_id = SOURCE_ID

    def __init__(
        self,
        vendor_dir: Path = VENDOR_DIR,
        retain_dir: Path | None = None,
        report: Callable[[str], None] | None = None,
    ) -> None:
        self.vendor_dir = vendor_dir
        self.retain_dir = retain_dir or (Path(settings.data_root).expanduser() / "congress" / "legislators")
        self._report = report or (lambda phase: None)
        self._run: IngestionRun | None = None
        self._commit = ""
        self._content: dict[str, bytes] = {}
        self._checksums: dict[str, str] = {}
        self._artifacts: dict[str, UUID] = {}
        self._people: dict[str, list[Legislator]] = {}
        self._shared: list[dict[str, Any]] = []
        self.result: dict[str, Any] = {}

    # -- stages -----------------------------------------------------------
    def discover(self, ctx: ConnectorContext) -> ConnectorContext:
        """Locate the checkout and pin the exact upstream commit."""
        missing = [n for n in FILES if not (self.vendor_dir / n).is_file()]
        if missing:
            raise FileNotFoundError(
                f"{', '.join(missing)} not found in {self.vendor_dir}. "
                "Run scripts/bootstrap_upstream.sh."
            )
        self._commit = _git(self.vendor_dir, "rev-parse", "HEAD")
        for name in FILES:
            if _git(self.vendor_dir, "status", "--porcelain", "--", name):
                raise RuntimeError(
                    f"{name} differs from upstream commit {self._commit[:12]}; the "
                    "recorded URL would not describe these bytes. Restore it with "
                    "git checkout or rerun scripts/bootstrap_upstream.sh."
                )
        self._run = IngestionRun(
            SOURCE_ID, {"commit": self._commit, "files": list(FILES)}, mode="backfill"
        )
        self._run.__enter__()
        ctx.run_id = str(self._run.run_id)
        self._report("discovered upstream checkout")
        return ctx

    def select(self, ctx: ConnectorContext) -> ConnectorContext:
        """Both files: current members and everyone since 1789."""
        ctx.selected_ids = FILES
        self._report("selected files")
        return ctx

    def plan(self, ctx: ConnectorContext) -> ConnectorContext:
        """Sizes are known; retained copies are small so no capacity waiver is needed."""
        ctx.plan_id = f"{SOURCE_ID}@{self._commit[:12]}"
        ctx.artifact_urls = tuple(f"{UPSTREAM}/{self._commit}/{n}" for n in FILES)
        self._report("planned load")
        return ctx

    def extract(self, ctx: ConnectorContext) -> ConnectorContext:
        """Read the bytes once and hash them."""
        for name in FILES:
            path = self.vendor_dir / name
            self._checksums[name] = file_checksum(path)
            self._content[name] = path.read_bytes()
        ctx.checksums = tuple(self._checksums[n] for n in FILES)
        self._report("read files")
        return ctx

    def evidence(self, ctx: ConnectorContext) -> ConnectorContext:
        """Retain checksum-addressed copies and register artifact versions."""
        with connect() as conn:
            for name, url in zip(FILES, ctx.artifact_urls, strict=True):
                checksum = self._checksums[name]
                source = self.vendor_dir / name
                retained = retain_artifact_bytes(
                    source,
                    checksum,
                    destination=retained_path(self.retain_dir / name, checksum),
                )
                artifact = register_artifact(
                    SOURCE_ID,
                    url,
                    str(retained),
                    f"congress-legislators/{Path(name).stem}",
                    status="downloaded",
                    checksum_sha256=checksum,
                    bytes_downloaded=len(self._content[name]),
                    content_type="application/yaml",
                    metadata={"upstream_commit": self._commit, "file": name},
                    conn=conn,
                )
                self._artifacts[name] = artifact["artifact_id"]
            conn.commit()
        self._report("retained evidence")
        return ctx

    def stage(self, ctx: ConnectorContext) -> ConnectorContext:
        """Parse into typed rows; the temp load table is created at publish."""
        self._people = {n: parse_legislators(self._content[n]) for n in FILES}
        self._report("parsed legislators")
        return ctx

    def normalize(self, ctx: ConnectorContext) -> ConnectorContext:
        """Drop identifiers that upstream itself assigns to two people."""
        everyone = [p for name in FILES for p in self._people[name]]
        kept, self._shared = dedupe_identifiers(everyone)
        by_bioguide = {p.bioguide: p for p in kept}
        self._people = {
            n: [by_bioguide[p.bioguide] for p in self._people[n]] for n in FILES
        }
        self._report("normalized identifiers")
        return ctx

    def validate(self, ctx: ConnectorContext) -> ConnectorContext:
        """Refuse to publish malformed identity data."""
        validate_legislators(self._people)
        self._report("validated")
        return ctx

    def publish(self, ctx: ConnectorContext) -> ConnectorContext:
        """One transaction: new people, new identifiers, conflict report."""
        rows = (
            (p.bioguide, p.full_name, p.given_name, p.family_name, ns, ext, self._artifacts[name])
            for name in FILES
            for p in self._people[name]
            for ns, ext in p.identifiers
        )
        with connect() as conn:
            counts = promote_legislators(conn, rows)
            conn.commit()
            for name, url in zip(FILES, ctx.artifact_urls, strict=True):
                register_artifact(
                    SOURCE_ID,
                    url,
                    str(retained_path(self.retain_dir / name, self._checksums[name])),
                    f"congress-legislators/{Path(name).stem}",
                    status="loaded",
                    checksum_sha256=self._checksums[name],
                    bytes_downloaded=len(self._content[name]),
                    content_type="application/yaml",
                    metadata={"upstream_commit": self._commit, "file": name},
                    conn=conn,
                )
            conn.commit()
        self.result = {
            **counts,
            "upstream_commit": self._commit,
            "shared_upstream_identifiers": self._shared,
        }
        if self._run is not None:
            self._run.record_count = counts["legislators"]
        self._report("published")
        return ctx

    def checkpoint(self, ctx: ConnectorContext) -> ConnectorContext:
        """Close the run ledger; write the review report when anything needs review."""
        if self._run is not None:
            error = RuntimeError(ctx.error) if ctx.error else None
            self._run.__exit__(type(error) if error else None, error, None)
            self._run = None
        if self.result and (self.result["conflicts"] or self._shared):
            target = (
                Path(settings.data_root).expanduser().resolve().parent
                / "meta"
                / "exceptions"
                / "legislator-identifiers.json"
            )
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(
                json.dumps(
                    {
                        "generated_at": datetime.now(UTC).isoformat(),
                        "run_id": ctx.run_id,
                        "conflicts": self.result["conflicts"],
                        "shared_upstream_identifiers": self._shared,
                    },
                    indent=2,
                    sort_keys=True,
                )
                + "\n"
            )
            self.result["report"] = str(target)
        self._report("checkpointed")
        return ctx
