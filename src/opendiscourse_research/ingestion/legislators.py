"""Connector for ``unitedstates/congress-legislators``: the BioGuide crosswalk.

Reads the two legislator YAML files from the ``vendor/`` checkout, retains
verified copies as immutable artifacts, and promotes identifiers into
``core.person_identifier`` keyed on BioGuide only (Story 3.1). Terms,
committees and social media are out of scope.
"""

from __future__ import annotations

import hashlib
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

from ..artifact_storage import retain_artifact_bytes, retained_path
from ..config import settings
from ..db import connect
from ..repositories.legislation import register_artifact
from ..repositories.people import promote_legislators
from .base import IngestionRun
from .connector import ConnectorContext

SOURCE_ID = "congress.legislators"
UPSTREAM = "https://raw.githubusercontent.com/unitedstates/congress-legislators"
UPSTREAM_REPO = "https://github.com/unitedstates/congress-legislators"
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
        if not isinstance(record, dict):
            raise ValueError(f"legislator #{index} is not a mapping")
        ids = record.get("id") or {}
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


def _normalize_remote(url: str) -> str:
    """Reduce ssh/https/.git spellings of a GitHub remote to one comparable form."""
    url = url.strip().removesuffix("/").removesuffix(".git")
    return url.replace("git@github.com:", "https://github.com/").lower()


def verify_checkout(vendor: Path, expected_origin: str | None) -> str:
    """Return HEAD only if the on-disk bytes are exactly what upstream published.

    The recorded permalink is only truthful when the checkout came from the
    expected remote, HEAD exists on a remote branch, and each file's bytes equal
    the committed blob (``status`` alone misses assume-unchanged files).
    """
    commit = _git(vendor, "rev-parse", "HEAD")
    if expected_origin is not None:
        origin = _git(vendor, "remote", "get-url", "origin")
        if _normalize_remote(origin) != _normalize_remote(expected_origin):
            raise RuntimeError(
                f"{vendor} origin is {origin!r}, expected {expected_origin!r}; the "
                "recorded URL would not describe these bytes. Rerun "
                "scripts/bootstrap_upstream.sh."
            )
        if not _git(vendor, "branch", "-r", "--contains", commit):
            raise RuntimeError(
                f"{vendor} HEAD {commit[:12]} is not on any remote branch (a local "
                "commit?). Rerun scripts/bootstrap_upstream.sh."
            )
    for name in FILES:
        on_disk = _git(vendor, "hash-object", "--no-filters", "--", name)
        committed = _git(vendor, "rev-parse", f"HEAD:{name}")
        if on_disk != committed:
            raise RuntimeError(
                f"{name} differs from upstream commit {commit[:12]}; the recorded URL "
                "would not describe these bytes. Restore it with git checkout or "
                "rerun scripts/bootstrap_upstream.sh."
            )
    return commit


class LegislatorsConnector:
    """Ten-stage Connector; publishes one transaction so a failure changes nothing."""

    source_id = SOURCE_ID

    def __init__(
        self,
        vendor_dir: Path = VENDOR_DIR,
        retain_dir: Path | None = None,
        report: Callable[[str], None] | None = None,
        expected_origin: str | None = UPSTREAM_REPO,
    ) -> None:
        self.vendor_dir = vendor_dir
        self.expected_origin = expected_origin
        # Absolute, like the other loaders: artifact.local_path is evidence and must
        # not depend on the working directory of whoever runs the load.
        self.retain_dir = (
            retain_dir or Path(settings.data_root).expanduser() / "congress" / "legislators"
        ).resolve()
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
        self._commit = verify_checkout(self.vendor_dir, self.expected_origin)
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
        """Read each file once; the hash and the parsed content are the same bytes."""
        for name in FILES:
            content = (self.vendor_dir / name).read_bytes()
            self._content[name] = content
            self._checksums[name] = hashlib.sha256(content).hexdigest()
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
            (
                p.bioguide,
                p.full_name,
                p.given_name,
                p.family_name,
                ns,
                ext,
                self._artifacts[name],
                ctx.run_id,
            )
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
            self._run.record_target(
                "core.person",
                "all",
                inserted=counts["people_created"],
                skipped=counts["legislators"] - counts["people_created"],
            )
            self._run.record_target(
                "core.person_identifier",
                "all",
                inserted=counts["identifiers_created"],
                skipped=counts["identifiers_already_present"],
                status="partial" if counts["conflicts"] else "succeeded",
            )
        self._report("published")
        return ctx

    def checkpoint(self, ctx: ConnectorContext) -> ConnectorContext:
        """Write the review report, then close the run ledger exactly once.

        The run counts as failed unless ``publish`` finished, whatever the cause:
        the error text can be empty and ``KeyboardInterrupt`` is not an Exception.
        """
        failure: BaseException | None = None
        if self._run is not None and (ctx.error or not self.result):
            failure = RuntimeError(ctx.error or "interrupted before publish finished")
        try:
            needs_review = bool(self.result) and bool(
                self.result["conflicts"] or self._shared
            )
            if failure is None and needs_review:
                self._write_review_report(ctx)
                if self._run is not None:
                    self._run.mark_partial()
        except OSError as exc:
            failure = exc
            raise
        finally:
            if self._run is not None:
                self._run.__exit__(
                    type(failure) if failure else None, failure, None
                )
                self._run = None
        self._report("checkpointed")
        return ctx

    def _write_review_report(self, ctx: ConnectorContext) -> None:
        """One file per run so an earlier run's review items are never overwritten."""
        target = (
            Path(settings.data_root).expanduser().resolve().parent
            / "meta"
            / "exceptions"
            / f"legislator-identifiers-{ctx.run_id}.json"
        )
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(
                {
                    "generated_at": datetime.now(UTC).isoformat(),
                    "run_id": ctx.run_id,
                    "upstream_commit": self._commit,
                    "conflicts": self.result["conflicts"],
                    "shared_upstream_identifiers": self._shared,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n"
        )
        self.result["report"] = str(target)
