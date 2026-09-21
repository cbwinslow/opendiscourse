"""Connector for GovInfo BILLS bulk text: download -> inventory -> ingest (Story 11.3).

One zip per Congress, session and bill type is fetched from ``govinfo.gov`` into
``DATA_ROOT``, registered as an immutable artifact, checked against GovInfo's own
directory manifest, and loaded as a lossless JSON record per XML member. Existing
``core.bill`` rows are linked by Congress, type and number; an unknown bill is kept
as a record and reported, never created from the text file. Nothing here reads a
machine-specific path.

Reruns are cheap and safe. A HEAD per zip detects a refresh; an unchanged,
origin-verified zip is not downloaded again, and members already recorded from an
artifact version are skipped. A refreshed zip is a new artifact version whose
records replace the older version's for the members it rewrites. When a zip is
unpublished, each XML listed in the type manifest is fetched instead.
"""

from __future__ import annotations

import time
import zipfile
from collections import Counter, defaultdict
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from email.utils import parsedate_to_datetime
from pathlib import Path, PurePosixPath
from typing import Any
from xml.etree import ElementTree

from ..artifact_storage import validate_retained
from ..capacity import GiB, RemoteObject, storage_preview
from ..coverage import FIRST_BILLS_CONGRESS as FIRST_CONGRESS
from ..coverage import LAST_CONGRESS
from ..db import connect
from ..providers.govinfo import (
    BILL_TYPES,
    BILLS_XML_URL,
    PACE_SECONDS,
    GovInfoBills,
    GovInfoNotFound,
    RemoteZip,
    bills_member_identity,
)
from ..repositories.artifacts import get_current_artifact
from ..repositories.bill_text import loaded_members, save_bill_text, supersede_records
from ..repositories.billstatus import superseded_artifact_ids
from ..repositories.legislation import register_artifact
from .base import IngestionRun
from .bill_text_parse import parse_bills_xml
from .bulk import ArtifactSpec, artifact_path, download
from .connector import ConnectorContext

SOURCE_ID = "congress.govinfo_bills"
LOCK_KEY = f"{SOURCE_ID}:sync"
BATCH_SIZE = 200
CAPACITY_RESERVE_BYTES = 10 * GiB
SKIP_NAMES = frozenset({"bill.dtd", "billres.xsl", "res.dtd"})

Downloader = Callable[..., Path]


def artifact_key(congress: int, session: int, bill_type: str) -> str:
    """Registry key for one zip; coverage looks zips up by exactly this key."""
    return f"BILLS-{congress}-{session}-{bill_type}.zip"


def xml_artifact_key(name: str) -> str:
    """Registry key for one fallback XML when the zip is unpublished."""
    return PurePosixPath(name).name


@dataclass
class _Item:
    """One zip (or fallback XML) as it moves through the stages."""

    remote: RemoteZip
    kind: str = "zip"  # or "xml"
    member_name: str | None = None
    action: str = "reuse"
    reason: str = ""
    artifact: dict[str, Any] | None = None
    members: list[str] = field(default_factory=list)
    coverage: dict[str, Any] = field(default_factory=dict)
    todo: list[str] = field(default_factory=list)
    older_versions: list[Any] = field(default_factory=list)
    not_published_members: list[str] = field(default_factory=list)

    @property
    def session(self) -> int:
        assert self.remote.session is not None
        return self.remote.session

    @property
    def key(self) -> str:
        if self.kind == "xml":
            assert self.member_name is not None
            return xml_artifact_key(self.member_name)
        return artifact_key(self.remote.congress, self.session, self.remote.bill_type)

    @property
    def label(self) -> str:
        return f"{self.remote.congress}/{self.session} {self.remote.bill_type}" + (
            f" {self.member_name}" if self.kind == "xml" else ""
        )

    @property
    def filename(self) -> str:
        if self.kind == "xml":
            assert self.member_name is not None
            return f"{self.remote.congress}/{self.session}/{self.remote.bill_type}/{self.member_name}"
        return f"{self.remote.congress}/{self.session}/{self.key}"


def _origin_state(remote: RemoteZip) -> dict[str, Any]:
    return {
        "origin": "govinfo",
        "collection": "BILLS",
        "congress": remote.congress,
        "session": remote.session,
        "bill_type": remote.bill_type,
        "remote_size": remote.size,
        "remote_last_modified": remote.last_modified,
    }


def _matches_origin(metadata: dict[str, Any] | None, remote: RemoteZip) -> bool:
    meta = metadata or {}
    return (
        meta.get("remote_size") == remote.size
        and meta.get("remote_last_modified") == remote.last_modified
    )


class BillTextConnector:
    """Ten-stage Connector. Each zip loads in batched transactions and resumes by member."""

    source_id = SOURCE_ID

    def __init__(
        self,
        congresses: Sequence[int] | None = None,
        bill_types: Sequence[str] = BILL_TYPES,
        sessions: Sequence[int] | None = None,
        *,
        govinfo: GovInfoBills | None = None,
        downloader: Downloader = download,
        batch_size: int = BATCH_SIZE,
        download_only: bool = False,
        report: Callable[[str], None] | None = None,
        sleep: Callable[[float], None] = time.sleep,
        download_pace_seconds: float = PACE_SECONDS,
    ) -> None:
        if batch_size < 1:
            raise ValueError("batch_size must be positive")
        unknown = [t for t in bill_types if t not in BILL_TYPES]
        if unknown:
            raise ValueError(f"unknown bill type(s) {unknown}; expected {list(BILL_TYPES)}")
        too_early = [c for c in (congresses or ()) if c < FIRST_CONGRESS]
        if too_early:
            raise ValueError(
                f"GovInfo's BILLS bulk starts at Congress {FIRST_CONGRESS}; "
                f"Congresses {too_early} are a later story"
            )
        self.congresses = tuple(congresses) if congresses else None
        self.bill_types = tuple(dict.fromkeys(bill_types))
        self.sessions = tuple(sessions) if sessions else None
        self.batch_size = batch_size
        self.download_only = download_only
        self._govinfo = govinfo or GovInfoBills()
        self._download = downloader
        self._report = report or (lambda phase: None)
        self._sleep = sleep
        self._pace = download_pace_seconds
        self._run: IngestionRun | None = None
        self._lock: Any = None
        self._items: list[_Item] = []
        self._finished = False
        self._partial = False
        self._not_published: list[str] = []
        self._problems: list[str] = []
        self.result: dict[str, Any] = {}

    def discover(self, ctx: ConnectorContext) -> ConnectorContext:
        """Ask the origin which Congresses and sessions exist and each zip's origin state."""
        self._acquire_lock()
        self._run = IngestionRun(
            SOURCE_ID,
            {
                "congresses": list(self.congresses) if self.congresses else "all",
                "sessions": list(self.sessions) if self.sessions else "all",
                "bill_types": list(self.bill_types),
                "download_only": self.download_only,
            },
            mode="backfill",
        )
        self._run.__enter__()
        ctx.run_id = str(self._run.run_id)
        published = [c for c in self._govinfo.congresses() if c >= FIRST_CONGRESS]
        wanted = (
            list(self.congresses)
            if self.congresses
            else [c for c in published if c <= LAST_CONGRESS]
        )
        missing = [c for c in wanted if c not in published]
        if missing:
            if not published:
                raise ValueError(
                    f"GovInfo lists no BILLS Congresses from {FIRST_CONGRESS} onward; "
                    f"not {missing}"
                )
            raise ValueError(
                f"GovInfo publishes BILLS for Congresses {published[0]}-{published[-1]}; "
                f"not {missing}"
            )
        for congress in sorted(set(wanted)):
            available = self._govinfo.sessions(congress)
            session_list = list(self.sessions) if self.sessions else available
            unknown_sessions = [s for s in session_list if s not in available]
            if unknown_sessions:
                raise ValueError(
                    f"GovInfo publishes BILLS sessions {available} for Congress {congress}; "
                    f"not {unknown_sessions}"
                )
            for session in session_list:
                for bill_type in self.bill_types:
                    self._report(f"checking origin: {congress}/{session} {bill_type}")
                    self._discover_type(congress, session, bill_type)
        if not self._items:
            raise RuntimeError(
                f"GovInfo publishes none of the requested BILLS zips ({self._not_published})"
            )
        ctx.extras["congresses"] = sorted({i.remote.congress for i in self._items})
        return ctx

    def _discover_type(self, congress: int, session: int, bill_type: str) -> None:
        try:
            self._items.append(_Item(self._govinfo.zip_info(congress, session, bill_type)))
            return
        except GovInfoNotFound:
            pass
        try:
            names = sorted(self._govinfo.manifest_xml(congress, session, bill_type))
        except GovInfoNotFound:
            self._not_published.append(artifact_key(congress, session, bill_type))
            return
        # Zip unpublished: fall back to one request per XML the manifest lists.
        for name in names:
            try:
                remote = self._govinfo.xml_info(congress, session, bill_type, name)
            except GovInfoNotFound:
                self._not_published.append(name)
                continue
            self._items.append(_Item(remote, kind="xml", member_name=name))
        if not any(
            i.remote.congress == congress
            and i.session == session
            and i.remote.bill_type == bill_type
            for i in self._items
        ):
            self._not_published.append(artifact_key(congress, session, bill_type))

    def select(self, ctx: ConnectorContext) -> ConnectorContext:
        """Download a zip (or fallback XML) only if it is new, changed, or not origin-verified."""
        for item in self._items:
            item.action, item.reason = self._decide(item)
        ctx.selected_ids = tuple(i.key for i in self._items)
        self._report(
            f"selected {sum(i.action == 'download' for i in self._items)} of "
            f"{len(self._items)} artifacts to download"
        )
        return ctx

    def plan(self, ctx: ConnectorContext) -> ConnectorContext:
        """Capacity gate on the bytes to fetch; unknown or excessive size stops the run."""
        downloads = [i for i in self._items if i.action == "download"]
        congresses = ctx.extras["congresses"]
        ctx.plan_id = f"{SOURCE_ID}:{congresses[0]}-{congresses[-1]}"
        ctx.artifact_urls = tuple(i.remote.url for i in downloads)
        if downloads:
            preview = storage_preview(
                [RemoteObject(i.remote.url, i.remote.size, "head") for i in downloads],
                stage_multiplier=0.0,
                database_multiplier=0.0,
                reserve_bytes=CAPACITY_RESERVE_BYTES,
            )
            if not preview["approved"]:
                raise RuntimeError(
                    f"capacity gate: {preview['reason']} for {preview['path']} "
                    f"(need {preview['peak_required_bytes']} bytes, "
                    f"{preview['filesystem_free_bytes']} free); free space or move DATA_ROOT"
                )
        self._report(f"planned {len(downloads)} downloads")
        return ctx

    def extract(self, ctx: ConnectorContext) -> ConnectorContext:
        """Download each selected artifact from the origin into ``DATA_ROOT`` (resumable)."""
        downloads = [i for i in self._items if i.action == "download"]
        for position, item in enumerate(downloads):
            if position:
                self._sleep(self._pace)
            self._report(
                f"downloading {item.label} ({position + 1}/{len(downloads)}): {item.reason}"
            )
            spec = ArtifactSpec(
                dataset_id=SOURCE_ID,
                artifact_key=item.key,
                url=item.remote.url,
                filename=item.filename,
                metadata={**_origin_state(item.remote), "run_id": ctx.run_id, "kind": item.kind},
            )
            self._discard_stale_partial(spec, item.remote)
            path = self._download(spec, overwrite=True)
            got = Path(path).stat().st_size
            if got != item.remote.size:
                raise RuntimeError(
                    f"{item.key}: downloaded {got} bytes but GovInfo reports "
                    f"{item.remote.size}; rerun to fetch it again"
                )
        return ctx

    def evidence(self, ctx: ConnectorContext) -> ConnectorContext:
        """Confirm the registry now holds origin-verified, checksummed bytes for every artifact."""
        checksums = []
        for item in self._items:
            row = get_current_artifact(item.key, dataset_id=SOURCE_ID)
            if (
                row is None
                or not row["checksum_sha256"]
                or not _matches_origin(row["metadata"], item.remote)
            ):
                raise RuntimeError(
                    f"{item.key}: the artifact registry does not hold bytes verified against "
                    "the origin; rerun the sync"
                )
            item.artifact = row
            checksums.append(row["checksum_sha256"])
        ctx.checksums = tuple(checksums)
        self._report("inventoried artifacts")
        return ctx

    def stage(self, ctx: ConnectorContext) -> ConnectorContext:
        """List each zip's XML members (or the single fallback file) and compare with the manifest."""
        for item in self._items:
            assert item.artifact is not None
            if item.kind == "xml":
                item.members = [item.key]
                item.coverage = {
                    "checksum": item.artifact["checksum_sha256"],
                    "official_xml": 1,
                    "archive_xml": 1,
                    "missing": 0,
                    "extra": 0,
                    "status": "complete",
                }
                continue
            path = Path(item.artifact["local_path"])
            try:
                with zipfile.ZipFile(path) as bundle:
                    item.members = sorted(
                        n
                        for n in bundle.namelist()
                        if n.endswith(".xml") and PurePosixPath(n).name.lower() not in SKIP_NAMES
                    )
            except (zipfile.BadZipFile, OSError) as exc:
                raise ValueError(f"{item.key}: not a readable zip ({exc})") from exc
            checksum = item.artifact["checksum_sha256"]
            prior = (item.artifact["metadata"] or {}).get("coverage") or {}
            if item.action == "reuse" and prior.get("checksum") == checksum:
                item.coverage = prior
                item.not_published_members = list(prior.get("not_published") or [])
                continue
            self._report(f"comparing {item.label} with the official manifest")
            official = self._govinfo.manifest_xml(item.remote.congress, item.session, item.remote.bill_type)
            present = {PurePosixPath(m).name for m in item.members}
            missing, extra = sorted(official - present), sorted(present - official)
            # We downloaded this zip: XML the archive lacks is incomplete, not a 404.
            item.not_published_members = []
            item.coverage = {
                "checksum": checksum,
                "official_xml": len(official),
                "archive_xml": len(present),
                "missing": len(missing),
                "extra": len(extra),
                "missing_examples": missing[:5],
                "extra_examples": extra[:5],
                "status": "complete" if not missing and not extra else "partial",
            }
        return ctx

    def normalize(self, ctx: ConnectorContext) -> ConnectorContext:
        """Work out what is left to load: members with no record row from this artifact version."""
        if self.download_only:
            return ctx
        with connect() as conn:
            for item in self._items:
                assert item.artifact is not None
                artifact_id = item.artifact["artifact_id"]
                done = loaded_members(conn, artifact_id)
                item.todo = [m for m in item.members if m not in done and PurePosixPath(m).name not in done]
                item.older_versions = superseded_artifact_ids(conn, artifact_id)
        self._report(f"{sum(len(i.todo) for i in self._items)} versions left to load")
        return ctx

    def validate(self, ctx: ConnectorContext) -> ConnectorContext:
        """Refuse to publish a zip whose members are not the versions its key promises."""
        problems: list[str] = []
        for item in self._items:
            if not item.members:
                problems.append(f"{item.key}: the zip holds no BILLS XML")
                continue
            expected = (item.remote.congress, item.remote.bill_type)
            wrong = [
                m
                for m in item.members
                if (ident := bills_member_identity(m)) is None or ident[:2] != expected
            ]
            if wrong:
                problems.append(f"{item.key}: unexpected member(s) {wrong[:3]}")
        if problems:
            raise ValueError("; ".join(problems))
        self._partial = any(i.coverage.get("status") == "partial" for i in self._items)
        self._report("validated")
        return ctx

    def publish(self, ctx: ConnectorContext) -> ConnectorContext:
        """Load each artifact's remaining members in batched transactions, then mark it loaded."""
        totals: dict[str, int] = defaultdict(int)
        per_congress: dict[int, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        zips_left = Counter(i.remote.congress for i in self._items)
        malformed: dict[str, list[str]] = {}
        unknown_bills: list[str] = []
        summaries: list[dict[str, Any]] = []

        def record(congress: int) -> None:
            if self._run is None:
                return
            slice_ = per_congress[congress]
            unfinished = zips_left[congress] > 0
            partial = unfinished or slice_["malformed"] or slice_["unknown"] or self._partial
            status = "partial" if partial else "succeeded"
            self._run.record_target(
                "core.bill_text_source_record",
                f"congress={congress}",
                inserted=slice_["versions"],
                skipped=slice_["skipped"],
                status=status,
            )

        for item in self._items:
            if self.download_only:
                summaries.append(self._summary(item, 0, 0, [], [], download_only=True))
                continue
            congress = item.remote.congress
            slice_ = per_congress[congress]
            slice_["skipped"] += len(item.members) - len(item.todo)
            here = {"versions": 0, "superseded": 0, "unknown": 0}

            def committed(
                versions: int, superseded: int, unknown: int, here=here, congress=congress
            ) -> None:
                here["versions"] += versions
                here["superseded"] += superseded
                here["unknown"] += unknown
                totals["versions"] += versions
                totals["superseded"] += superseded
                totals["unknown"] += unknown
                per_congress[congress]["versions"] += versions
                per_congress[congress]["unknown"] += unknown
                if self._run is not None:
                    self._run.record_count += versions
                record(congress)

            bad, unknown = self._load_item(item, ctx, committed)
            malformed.update({item.key: bad} if bad else {})
            unknown_bills.extend(unknown)
            slice_["malformed"] += len(bad)
            zips_left[congress] -= 1
            record(congress)
            summaries.append(
                self._summary(item, here["versions"], here["superseded"], bad, unknown)
            )
        self._partial = self._partial or bool(malformed) or bool(unknown_bills)
        self._finished = True
        self.result = {
            "congresses": ctx.extras["congresses"],
            "zips": sum(1 for i in self._items if i.kind == "zip"),
            "xml_fallbacks": sum(1 for i in self._items if i.kind == "xml"),
            "downloaded": sum(i.action == "download" for i in self._items),
            "reused": sum(i.action == "reuse" for i in self._items),
            "bytes_downloaded": sum(i.remote.size for i in self._items if i.action == "download"),
            "download_only": self.download_only,
            "versions_loaded": totals["versions"],
            "superseded_rows_replaced": totals["superseded"],
            "unknown_bills": unknown_bills[:50],
            "unknown_bill_count": len(unknown_bills),
            "partial": self._partial,
            "incomplete_zips": [
                {"key": i.key, **{k: i.coverage[k] for k in ("missing", "extra", "missing_examples") if k in i.coverage}}
                for i in self._items
                if i.coverage.get("status") == "partial"
            ],
            "malformed_members": malformed,
            "problems": self._problems[:20],
            "not_published": self._not_published,
            "items": summaries,
        }
        self._report("published")
        return ctx

    def checkpoint(self, ctx: ConnectorContext) -> ConnectorContext:
        """Close the run ledger exactly once; partial coverage is recorded, not hidden."""
        failure: BaseException | None = None
        if self._run is not None and (ctx.error or not self._finished):
            failure = RuntimeError(ctx.error or "interrupted before publish finished")
        try:
            if failure is None and self._partial and self._run is not None:
                self._run.mark_partial()
        finally:
            if self._run is not None:
                self._run.__exit__(type(failure) if failure else None, failure, None)
                self._run = None
            if self._lock is not None:
                self._lock.close()
                self._lock = None
        self._report("checkpointed")
        return ctx

    def _acquire_lock(self) -> None:
        conn = connect()
        conn.autocommit = True
        row = conn.execute(
            "SELECT pg_try_advisory_lock(hashtextextended(%s, 0)) AS acquired", (LOCK_KEY,)
        ).fetchone()
        if not row or not row["acquired"]:
            conn.close()
            raise RuntimeError(
                "another sync-bill-text run is in progress (it holds the database lock); "
                "wait for it to finish, then rerun"
            )
        self._lock = conn

    def _decide(self, item: _Item) -> tuple[str, str]:
        row = get_current_artifact(item.key, dataset_id=SOURCE_ID)
        if row is None or not row["checksum_sha256"]:
            return "download", "not downloaded yet"
        try:
            validate_retained(row["local_path"], row["checksum_sha256"])
        except (ValueError, OSError):
            return "download", "retained file missing or damaged"
        meta = row["metadata"] or {}
        if "remote_size" not in meta:
            return "download", "not yet verified against the origin"
        if not _matches_origin(meta, item.remote):
            return "download", "changed at the origin"
        if Path(row["local_path"]).stat().st_size != item.remote.size:
            return "download", "retained size differs from the origin"
        return "reuse", "unchanged at the origin"

    @staticmethod
    def _discard_stale_partial(spec: ArtifactSpec, remote: RemoteZip) -> None:
        target = artifact_path(spec)
        partial = target.with_suffix(target.suffix + ".part")
        if not partial.exists():
            return
        try:
            changed = parsedate_to_datetime(remote.last_modified).timestamp()
        except (TypeError, ValueError):
            changed = float("inf")
        if partial.stat().st_mtime < changed:
            partial.unlink()

    def _load_item(
        self,
        item: _Item,
        ctx: ConnectorContext,
        committed: Callable[[int, int, int], None],
    ) -> tuple[list[str], list[str]]:
        """Load one artifact's remaining members; return malformed names and unknown bills."""
        assert item.artifact is not None
        artifact = item.artifact
        malformed: list[str] = []
        unknown: list[str] = []
        path = Path(artifact["local_path"])
        with connect() as conn:
            bundle: zipfile.ZipFile | None = None
            try:
                if item.todo and item.kind != "xml":
                    bundle = zipfile.ZipFile(path)
                if item.todo:
                    for start in range(0, len(item.todo), self.batch_size):
                        batch = item.todo[start : start + self.batch_size]
                        loaded_members_now: list[str] = []
                        batch_unknown = 0
                        for member in batch:
                            try:
                                if item.kind == "xml":
                                    xml_bytes = path.read_bytes()
                                else:
                                    assert bundle is not None
                                    xml_bytes = bundle.read(member)
                                parsed = parse_bills_xml(xml_bytes, PurePosixPath(member).name)
                            except (ElementTree.ParseError, ValueError, KeyError, OSError) as exc:
                                malformed.append(member)
                                self._problems.append(f"{item.key}:{member}: unreadable ({exc})")
                                continue
                            if problem := self._identity_problem(item, member, parsed):
                                malformed.append(member)
                                self._problems.append(problem)
                                continue
                            saved = save_bill_text(
                                parsed,
                                session=item.session,
                                source_artifact_id=str(artifact["artifact_id"]),
                                source_member=PurePosixPath(member).name,
                                canonical_url=BILLS_XML_URL.format(
                                    congress=item.remote.congress,
                                    session=item.session,
                                    bill_type=item.remote.bill_type,
                                    name=PurePosixPath(member).name,
                                ),
                                xml_bytes=xml_bytes,
                                conn=conn,
                            )
                            loaded_members_now.append(PurePosixPath(member).name)
                            if saved["unknown"]:
                                batch_unknown += 1
                                unknown.append(
                                    f"{parsed.congress} {parsed.bill_type} {parsed.bill_number} "
                                    f"{parsed.version_code}"
                                )
                        removed = supersede_records(conn, loaded_members_now, item.older_versions)
                        conn.commit()
                        committed(len(loaded_members_now), removed, batch_unknown)
                        self._report(
                            f"loading {item.label}: {min(start + self.batch_size, len(item.todo))}"
                            f"/{len(item.todo)} versions"
                        )
            finally:
                if bundle is not None:
                    bundle.close()
            if not malformed and (
                artifact["status"] != "loaded"
                or (artifact["metadata"] or {}).get("coverage") != item.coverage
            ):
                register_artifact(
                    SOURCE_ID,
                    item.remote.url,
                    artifact["local_path"],
                    item.key,
                    status="loaded",
                    checksum_sha256=artifact["checksum_sha256"],
                    bytes_downloaded=item.remote.size,
                    metadata={
                        "coverage": item.coverage,
                        "loaded_members": len(item.members),
                        "run_id": ctx.run_id,
                        "kind": item.kind,
                    },
                    conn=conn,
                )
                conn.commit()
        return malformed, unknown

    @staticmethod
    def _identity_problem(item: _Item, member: str, parsed: Any) -> str | None:
        found = (parsed.congress, parsed.bill_type, int(parsed.bill_number), parsed.version_code)
        named = bills_member_identity(member)
        if found != named:
            return f"{item.key}:{member} describes {found}, not the version its name promises"
        if named is not None and named[:2] != (item.remote.congress, item.remote.bill_type):
            return f"{item.key}:{member} does not belong in this zip"
        return None

    @staticmethod
    def _summary(
        item: _Item,
        versions: int,
        superseded: int,
        malformed: list[str],
        unknown: list[str],
        download_only: bool = False,
    ) -> dict[str, Any]:
        return {
            "key": item.key,
            "kind": item.kind,
            "action": item.action,
            "reason": item.reason,
            "members": len(item.members),
            "loaded_now": versions,
            "already_loaded": None if download_only else len(item.members) - len(item.todo),
            "superseded_rows": superseded,
            "malformed": len(malformed),
            "unknown_bills": len(unknown),
            "coverage": item.coverage.get("status"),
            "not_published": len(item.not_published_members),
        }
