"""Connector for GovInfo BILLSTATUS bulk data: download -> inventory -> ingest (Story 9.5).

One zip per Congress and bill type is fetched from ``govinfo.gov`` into ``DATA_ROOT``,
registered as an immutable artifact (URL, size, checksum, the server's
``Last-Modified``), checked against GovInfo's own directory manifest, and loaded into
``core.bill`` and its child tables. Nothing here reads a machine-specific path: bytes
come from the origin, or from whatever the artifact registry says this machine already
holds and the origin still agrees with.

Reruns are cheap and safe. A HEAD per zip detects a refresh (size or ``Last-Modified``);
an unchanged, origin-verified zip is not downloaded again, and members already loaded
from an artifact version are skipped, so a killed load resumes where it stopped. A
refreshed zip is a new artifact version whose rows replace the older version's for the
same bills. Registry rows that predate this Connector (no recorded origin state) are
re-verified against the origin instead of trusted.
"""

from __future__ import annotations

import time
import zipfile
from collections import Counter, defaultdict
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

from ..artifact_storage import validate_retained
from ..capacity import GiB, RemoteObject, storage_preview
from ..db import connect
from ..providers.govinfo import (
    BILL_TYPES,
    PACE_SECONDS,
    GovInfoBillStatus,
    GovInfoNotFound,
    RemoteZip,
    member_identity,
)
from ..repositories.artifacts import get_current_artifact
from ..repositories.billstatus import (
    loaded_record_members,
    supersede_bill_children,
    superseded_artifact_ids,
)
from ..repositories.legislation import (
    ensure_us_legislative_session,
    parse_billstatus_xml,
    register_artifact,
    save_billstatus_bill,
)
from .base import IngestionRun
from .bulk import ArtifactSpec, artifact_path, download
from .connector import ConnectorContext

SOURCE_ID = "congress.govinfo_billstatus"
LOCK_KEY = f"{SOURCE_ID}:sync"
BATCH_SIZE = 500
# The whole source is about 600 MB; keep a small floor instead of the 100 GiB default.
CAPACITY_RESERVE_BYTES = 10 * GiB

Downloader = Callable[..., Path]


def artifact_key(congress: int, bill_type: str) -> str:
    """Registry key for one zip; ``coverage`` looks zips up by exactly this key."""
    return f"BILLSTATUS-{congress}-{bill_type}.zip"


@dataclass
class _Item:
    """One Congress/bill-type zip as it moves through the stages."""

    remote: RemoteZip
    action: str = "reuse"  # or "download"
    reason: str = ""
    artifact: dict[str, Any] | None = None
    members: list[str] = field(default_factory=list)
    coverage: dict[str, Any] = field(default_factory=dict)
    todo: list[str] = field(default_factory=list)
    older_versions: list[Any] = field(default_factory=list)

    @property
    def key(self) -> str:
        return artifact_key(self.remote.congress, self.remote.bill_type)

    @property
    def label(self) -> str:
        return f"{self.remote.congress} {self.remote.bill_type}"


def _origin_state(remote: RemoteZip) -> dict[str, Any]:
    return {
        "origin": "govinfo",
        "congress": remote.congress,
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


class BillStatusConnector:
    """Ten-stage Connector. Each zip loads in batched transactions and resumes by member."""

    source_id = SOURCE_ID

    def __init__(
        self,
        congresses: Sequence[int] | None = None,
        bill_types: Sequence[str] = BILL_TYPES,
        *,
        govinfo: GovInfoBillStatus | None = None,
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
        self.congresses = tuple(congresses) if congresses else None
        self.bill_types = tuple(dict.fromkeys(bill_types))
        self.batch_size = batch_size
        self.download_only = download_only
        self._govinfo = govinfo or GovInfoBillStatus()
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

    # -- stages -----------------------------------------------------------
    def discover(self, ctx: ConnectorContext) -> ConnectorContext:
        """Ask the origin which Congresses exist and each zip's size and modified time."""
        self._acquire_lock()
        self._run = IngestionRun(
            SOURCE_ID,
            {
                "congresses": list(self.congresses) if self.congresses else "all",
                "bill_types": list(self.bill_types),
                "download_only": self.download_only,
            },
            mode="backfill",
        )
        self._run.__enter__()
        ctx.run_id = str(self._run.run_id)
        published = self._govinfo.congresses()
        wanted = list(self.congresses) if self.congresses else published
        missing = [c for c in wanted if c not in published]
        if missing:
            raise ValueError(
                f"GovInfo publishes BILLSTATUS for Congresses {published[0]}-{published[-1]}; "
                f"not {missing}"
            )
        for congress in sorted(set(wanted)):
            for bill_type in self.bill_types:
                self._report(f"checking origin: {congress} {bill_type}")
                try:
                    self._items.append(_Item(self._govinfo.zip_info(congress, bill_type)))
                except GovInfoNotFound:
                    # Not published (yet), e.g. a type with no bills so far in a new
                    # Congress. That is the origin's state, not a failure: report it.
                    self._not_published.append(artifact_key(congress, bill_type))
        if not self._items:
            raise RuntimeError(
                f"GovInfo publishes none of the requested BILLSTATUS zips ({self._not_published})"
            )
        ctx.extras["congresses"] = sorted({i.remote.congress for i in self._items})
        return ctx

    def select(self, ctx: ConnectorContext) -> ConnectorContext:
        """Download a zip only if it is new, changed at the origin, or not yet origin-verified."""
        for item in self._items:
            item.action, item.reason = self._decide(item)
        ctx.selected_ids = tuple(i.key for i in self._items)
        self._report(
            f"selected {sum(i.action == 'download' for i in self._items)} of "
            f"{len(self._items)} zips to download"
        )
        return ctx

    def plan(self, ctx: ConnectorContext) -> ConnectorContext:
        """Capacity gate on the bytes to fetch; unknown or excessive size stops the run."""
        downloads = [i for i in self._items if i.action == "download"]
        congresses = ctx.extras["congresses"]
        ctx.plan_id = f"{SOURCE_ID}:{congresses[0]}-{congresses[-1]}"
        ctx.artifact_urls = tuple(i.remote.url for i in downloads)
        if downloads:
            # Only DATA_ROOT's filesystem is knowable here (the database may live
            # elsewhere), and only the compressed zips are written to it.
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
        """Download each selected zip from the origin into ``DATA_ROOT`` (resumable)."""
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
                filename=f"{item.remote.congress}/{item.key}",
                metadata={**_origin_state(item.remote), "run_id": ctx.run_id},
            )
            self._discard_stale_partial(spec, item.remote)
            path = self._download(spec, overwrite=True)
            got = Path(path).stat().st_size
            if got != item.remote.size:
                # The next run's size check in _decide sees this and fetches it again.
                raise RuntimeError(
                    f"{item.key}: downloaded {got} bytes but GovInfo reports "
                    f"{item.remote.size}; rerun to fetch it again"
                )
        return ctx

    def evidence(self, ctx: ConnectorContext) -> ConnectorContext:
        """Confirm the registry now holds origin-verified, checksummed bytes for every zip."""
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
        """List each zip's members and compare them with GovInfo's directory manifest."""
        for item in self._items:
            assert item.artifact is not None
            path = Path(item.artifact["local_path"])
            try:
                with zipfile.ZipFile(path) as bundle:
                    item.members = sorted(n for n in bundle.namelist() if n.endswith(".xml"))
            except (zipfile.BadZipFile, OSError) as exc:
                raise ValueError(f"{item.key}: not a readable zip ({exc})") from exc
            checksum = item.artifact["checksum_sha256"]
            prior = (item.artifact["metadata"] or {}).get("coverage") or {}
            if item.action == "reuse" and prior.get("checksum") == checksum:
                item.coverage = prior  # an unchanged zip has an unchanged verdict
                continue
            self._report(f"comparing {item.label} with the official manifest")
            official = self._govinfo.manifest_xml(item.remote.congress, item.remote.bill_type)
            present = set(item.members)
            missing, extra = sorted(official - present), sorted(present - official)
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
        """Work out what is left to load: members with no record row from this artifact version.

        The record row is written last in a bill's transaction, so a member without one is not
        fully loaded; that includes every bill loaded before records existed.
        """
        if self.download_only:
            return ctx
        with connect() as conn:
            for item in self._items:
                assert item.artifact is not None
                artifact_id = item.artifact["artifact_id"]
                done = loaded_record_members(conn, artifact_id)
                item.todo = [m for m in item.members if m not in done]
                item.older_versions = superseded_artifact_ids(conn, artifact_id)
        self._report(f"{sum(len(i.todo) for i in self._items)} bills left to load")
        return ctx

    def validate(self, ctx: ConnectorContext) -> ConnectorContext:
        """Refuse to publish a zip whose members are not the bills its key promises."""
        problems: list[str] = []
        for item in self._items:
            if not item.members:
                problems.append(f"{item.key}: the zip holds no BILLSTATUS XML")
                continue
            wrong = [
                m
                for m in item.members
                if (ident := member_identity(m)) is None
                or ident[:2] != (item.remote.congress, item.remote.bill_type)
            ]
            if wrong:
                problems.append(f"{item.key}: unexpected member(s) {wrong[:3]}")
        if problems:
            raise ValueError("; ".join(problems))
        self._partial = any(i.coverage.get("status") == "partial" for i in self._items)
        self._report("validated")
        return ctx

    def publish(self, ctx: ConnectorContext) -> ConnectorContext:
        """Load each zip's remaining bills in batched transactions, then mark it loaded."""
        totals: dict[str, int] = defaultdict(int)
        per_congress: dict[int, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        zips_left = Counter(i.remote.congress for i in self._items)
        malformed: dict[str, list[str]] = {}
        summaries: list[dict[str, Any]] = []

        def record(congress: int) -> None:
            """Write the Congress's running totals; only a finished, clean Congress is 'succeeded'."""
            if self._run is None:
                return
            slice_ = per_congress[congress]
            unfinished = zips_left[congress] > 0
            partial = (
                unfinished
                or slice_["malformed"]
                or any(
                    i.coverage.get("status") == "partial"
                    for i in self._items
                    if i.remote.congress == congress
                )
            )
            status = "partial" if partial else "succeeded"
            self._run.record_target(
                "core.bill",
                f"congress={congress}",
                inserted=slice_["bills"],
                skipped=slice_["skipped"],
                status=status,
            )
            self._run.record_target(
                "core.bill_action", f"congress={congress}", inserted=slice_["actions"], status=status
            )

        for item in self._items:
            if self.download_only:
                summaries.append(self._summary(item, 0, 0, 0, [], download_only=True))
                continue
            congress = item.remote.congress
            slice_ = per_congress[congress]
            slice_["skipped"] += len(item.members) - len(item.todo)
            here = {"bills": 0, "actions": 0, "superseded": 0}

            def committed(bills: int, actions: int, superseded: int, here=here, congress=congress) -> None:
                for name, value in (("bills", bills), ("actions", actions), ("superseded", superseded)):
                    here[name] += value
                    totals[name] += value
                per_congress[congress]["bills"] += bills
                per_congress[congress]["actions"] += actions
                if self._run is not None:
                    self._run.record_count += bills
                record(congress)

            bad = self._load_item(item, ctx, committed)
            malformed.update({item.key: bad} if bad else {})
            slice_["malformed"] += len(bad)
            zips_left[congress] -= 1
            record(congress)
            summaries.append(
                self._summary(item, here["bills"], here["actions"], here["superseded"], bad)
            )
        self._partial = self._partial or bool(malformed)
        self._finished = True
        self.result = {
            "congresses": ctx.extras["congresses"],
            "zips": len(self._items),
            "downloaded": sum(i.action == "download" for i in self._items),
            "reused": sum(i.action == "reuse" for i in self._items),
            "bytes_downloaded": sum(i.remote.size for i in self._items if i.action == "download"),
            "download_only": self.download_only,
            "bills_loaded": totals["bills"],
            "actions_loaded": totals["actions"],
            "superseded_rows_replaced": totals["superseded"],
            "partial": self._partial,
            "incomplete_zips": [
                {"key": i.key, **{k: i.coverage[k] for k in ("missing", "extra", "missing_examples")}}
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
                self._lock.close()  # a session advisory lock ends with its connection
                self._lock = None
        self._report("checkpointed")
        return ctx

    # -- helpers ----------------------------------------------------------
    def _acquire_lock(self) -> None:
        """One sync at a time: two would race on artifact versions and on the same bills."""
        conn = connect()
        conn.autocommit = True  # never sit idle in a transaction for the length of a sync
        row = conn.execute(
            "SELECT pg_try_advisory_lock(hashtextextended(%s, 0)) AS acquired", (LOCK_KEY,)
        ).fetchone()
        if not row or not row["acquired"]:
            conn.close()
            raise RuntimeError(
                "another sync-billstatus run is in progress (it holds the database lock); "
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
        """A partial download begun before the origin last changed must not be resumed."""
        target = artifact_path(spec)
        partial = target.with_suffix(target.suffix + ".part")
        if not partial.exists():
            return
        try:
            changed = parsedate_to_datetime(remote.last_modified).timestamp()
        except (TypeError, ValueError):
            changed = float("inf")  # unreadable date: do not trust the partial
        if partial.stat().st_mtime < changed:
            partial.unlink()

    def _load_item(
        self,
        item: _Item,
        ctx: ConnectorContext,
        committed: Callable[[int, int, int], None],
    ) -> list[str]:
        """Load one zip's remaining members; return any malformed member names.

        ``committed(bills, actions, superseded_rows)`` is called after every batch commit, so
        the run ledger reflects committed work even if a later batch fails or the run is killed.
        """
        assert item.artifact is not None
        artifact = item.artifact
        malformed: list[str] = []
        people: dict[tuple[str, str], str | None] = {}
        with connect() as conn:
            if item.todo:
                session_id = ensure_us_legislative_session(
                    item.remote.congress,
                    source_artifact_id=str(artifact["artifact_id"]),
                    metadata={"congress": item.remote.congress},
                    conn=conn,
                )
                conn.commit()
                with zipfile.ZipFile(artifact["local_path"]) as bundle:
                    for start in range(0, len(item.todo), self.batch_size):
                        bill_ids: list[str] = []
                        batch_actions = 0
                        for member in item.todo[start : start + self.batch_size]:
                            try:
                                data = parse_billstatus_xml(bundle.read(member), member_name=member)
                            except (ElementTree.ParseError, ValueError) as exc:
                                malformed.append(member)
                                self._problems.append(f"{item.key}:{member}: unreadable ({exc})")
                                continue
                            if problem := self._identity_problem(item, member, data):
                                # Which bill this is can no longer be trusted: write nothing
                                # for it, report it, and carry on with the rest.
                                malformed.append(member)
                                self._problems.append(problem)
                                continue
                            bill_ids.append(
                                save_billstatus_bill(
                                    data,
                                    session_id,
                                    source_artifact_id=str(artifact["artifact_id"]),
                                    source_member=member,
                                    conn=conn,
                                    person_cache=people,
                                )
                            )
                            batch_actions += len(data["actions"])
                        removed = supersede_bill_children(conn, bill_ids, item.older_versions)
                        conn.commit()
                        committed(len(bill_ids), batch_actions, sum(removed.values()))
                        self._report(
                            f"loading {item.label}: {min(start + self.batch_size, len(item.todo))}"
                            f"/{len(item.todo)} bills"
                        )
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
                    },
                    conn=conn,
                )
                conn.commit()
        return malformed

    @staticmethod
    def _identity_problem(item: _Item, member: str, data: dict[str, Any]) -> str | None:
        """Why the XML does not describe the bill its file name promises, else None."""
        try:
            found = (data["congress"], data["bill_type"], int(data["bill_number"]))
        except ValueError:
            found = None
        if found != member_identity(member):
            return f"{item.key}:{member} describes {found}, not the bill its name promises"
        return None

    @staticmethod
    def _summary(
        item: _Item,
        bills: int,
        actions: int,
        superseded: int,
        malformed: list[str],
        download_only: bool = False,
    ) -> dict[str, Any]:
        return {
            "key": item.key,
            "action": item.action,
            "reason": item.reason,
            "members": len(item.members),
            "loaded_now": bills,
            "already_loaded": None if download_only else len(item.members) - len(item.todo),
            "actions_loaded": actions,
            "superseded_rows": superseded,
            "malformed": len(malformed),
            "coverage": item.coverage.get("status"),
        }
