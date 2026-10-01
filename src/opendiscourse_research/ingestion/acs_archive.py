"""Complete ACS PUMS and AHS archive discovery and selection.

This module deliberately keeps discovery separate from transfer.  Census directory
indexes are parsed into a reviewed manifest first, so capacity approval can fail
closed before a national archive is downloaded.
"""

from __future__ import annotations

import csv
import io
import json
import zipfile
from collections.abc import Callable, Iterable, Iterator
from dataclasses import asdict, dataclass
from datetime import date
from hashlib import sha256
from pathlib import Path
from typing import Any
from uuid import UUID

import yaml
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert

from ..capacity import RemoteObject, storage_preview
from ..db import session
from ..models.catalog import DatasetField, artifact_table
from ..models.core import (
    housing_archive_release_table,
    housing_microdata_projection_table,
)
from ..models.ingest import run_table, run_target_table
from ..models.stage import stage_acs_pums_record, stage_ahs_record
from ..providers.census import (
    ArchiveIndex,
    discover_archive_index,
    official_housing_archive_indexes,
    verified_acs_archive_fallback,
)
from ..repositories.artifacts import require_current_artifact
from .base import IngestionRun
from .bulk import (
    ArtifactSpec,
    discard_partial,
    download_retrying,
    retryable_download_error,
)
from .connector import ConnectorContext

ACS_1_YEAR = tuple(year for year in range(2005, 2025) if year != 2020)
ACS_5_YEAR = tuple(range(2009, 2025))


@dataclass(frozen=True)
class ArchiveArtifact:
    """One publisher artifact, including its release and representation identity."""

    artifact_key: str
    url: str
    bytes: int | None
    product: str
    period: str
    component: str
    kind: str
    version: str = "current"
    selected: bool = True


@dataclass(frozen=True)
class MemberReconciliation:
    """Counts for one immutable artifact CSV member in one connector attempt."""

    member: str
    parsed: int
    inserted: int
    existing: int
    rejected: int = 0

    def reconciled(self) -> bool:
        return self.parsed == self.inserted + self.existing + self.rejected


class MemberStagingError(ValueError):
    """A malformed source member whose stable name can be recorded in the ledger."""

    def __init__(self, member: str, message: str) -> None:
        super().__init__(message)
        self.member = member


@dataclass(frozen=True)
class ArchiveResume:
    """Validated, immutable evidence needed to replace an interrupted archive run."""

    predecessor_run_id: UUID
    manifest: dict[str, Any]
    artifacts: tuple[ArchiveArtifact, ...]
    completed_members: dict[str, tuple[MemberReconciliation, ...]]
    evidence: dict[str, tuple[Any, str]]


def publisher_gaps() -> list[dict[str, str]]:
    """Return known official absences rather than silently omitting them."""
    return [
        {"product": "acs_pums_1", "period": "2020", "reason": "no standard ACS 1-year release"},
        {"product": "acs_pums", "period": "2000-2004", "reason": "ACS PUMS not published"},
        {"product": "ahs", "period": "2000", "reason": "no public-use release"},
    ]


def _text(item: dict[str, Any], key: str) -> str:
    value = item.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"official archive entry is missing {key}")
    return value.strip()


def manifest_from_index(entries: Iterable[dict[str, Any]]) -> list[ArchiveArtifact]:
    """Validate publisher-index entries and choose one current AHS representation.

    Input is intentionally a small provider boundary: adapters turn HTML/JSON
    directory listings into these dictionaries, while the rest of the archive is
    independent of their markup.  AHS flat and superseded files remain evidence
    candidates but cannot become a second published component.
    """
    parsed: list[ArchiveArtifact] = []
    seen: set[str] = set()
    ahs_current: set[tuple[str, str]] = set()
    for item in entries:
        product = _text(item, "product")
        period = _text(item, "period")
        component = _text(item, "component")
        kind = _text(item, "kind")
        url = _text(item, "url")
        size = item.get("bytes")
        if not isinstance(size, int) or size < 0:
            raise ValueError(f"official archive entry {url} has unknown byte size")
        version = str(item.get("version") or "current")
        representation = str(item.get("representation") or "relational")
        selected = bool(item.get("selected", True))
        if product == "ahs" and kind == "data":
            key = (period, component)
            if version != "current" or representation != "relational":
                selected = False
            if selected:
                if representation != "relational" or version != "current":
                    raise ValueError("AHS publication must select the current relational representation")
                if key in ahs_current:
                    raise ValueError(f"duplicate AHS observations for {period}/{component}")
                ahs_current.add(key)
        # A release can legitimately publish several documentation files.  The
        # URL-derived suffix makes each immutable publisher object distinct while
        # retaining a stable logical key across resumable attempts.
        artifact_key = (
            f"{product}:{period}:{component}:{kind}:{version}:"
            f"{sha256(url.encode()).hexdigest()[:12]}"
        )
        if artifact_key in seen:
            raise ValueError(f"duplicate official archive artifact {artifact_key}")
        seen.add(artifact_key)
        parsed.append(ArchiveArtifact(artifact_key, url, size, product, period, component, kind, version, selected))
    return sorted(parsed, key=lambda artifact: artifact.artifact_key)


def capacity_manifest(artifacts: Iterable[ArchiveArtifact]) -> dict[str, Any]:
    """Create the exact, fail-closed capacity report for selected artifacts."""
    selected = [artifact for artifact in artifacts if artifact.selected]
    preview = storage_preview(
        [RemoteObject(artifact.url, artifact.bytes, "official-index") for artifact in selected],
        stage_multiplier=1.0,
        database_multiplier=1.5,
    )
    return {**preview, "artifacts": [asdict(artifact) for artifact in selected], "gaps": publisher_gaps()}


def _saved_manifest_artifacts(manifest: Any) -> tuple[ArchiveArtifact, ...]:
    """Rebuild only the operator-approved artifact selection saved on a run."""
    if not isinstance(manifest, dict) or manifest.get("approved") is not True:
        raise ValueError("resume target lacks an approved saved manifest")
    saved_artifacts = manifest.get("artifacts")
    if not isinstance(saved_artifacts, list) or not saved_artifacts:
        raise ValueError("resume target lacks a usable saved manifest artifact list")
    try:
        artifacts = tuple(ArchiveArtifact(**item) for item in saved_artifacts)
    except (TypeError, ValueError) as exc:
        raise ValueError("resume target has a malformed saved manifest") from exc
    keys = [artifact.artifact_key for artifact in artifacts]
    if len(keys) != len(set(keys)) or not all(artifact.selected for artifact in artifacts):
        raise ValueError("resume target has an invalid saved manifest selection")
    rebuilt = tuple(manifest_from_index(saved_artifacts))
    if artifacts != rebuilt:
        raise ValueError("resume target saved manifest does not match archive selection rules")
    return rebuilt


def _checkpoint_members(
    checkpoint: Any, artifacts: tuple[ArchiveArtifact, ...], selected: Any
) -> dict[str, tuple[MemberReconciliation, ...]]:
    """Validate completed source members without inferring progress from totals."""
    expected_selected = [artifact.artifact_key for artifact in artifacts]
    if not isinstance(selected, list) or selected != expected_selected:
        raise ValueError("resume target saved selection does not match its manifest")
    if not isinstance(checkpoint, dict) or checkpoint.get("selected") != expected_selected:
        raise ValueError("resume target lacks a checkpoint for its saved selection")
    raw_members = checkpoint.get("members")
    if not isinstance(raw_members, dict):
        raise ValueError("resume target checkpoint has malformed members")
    data_artifacts = {artifact.artifact_key for artifact in artifacts if artifact.kind == "data"}
    completed: dict[str, tuple[MemberReconciliation, ...]] = {}
    for artifact_key, rows in raw_members.items():
        if artifact_key not in data_artifacts:
            raise ValueError("resume target checkpoint names a member outside its saved manifest")
        if not isinstance(rows, list):
            raise ValueError("resume target checkpoint has malformed member counts")
        parsed_rows: list[MemberReconciliation] = []
        names: set[str] = set()
        for row in rows:
            if not isinstance(row, dict):
                raise ValueError("resume target checkpoint has malformed member counts")
            try:
                item = MemberReconciliation(**row)
            except TypeError as exc:
                raise ValueError("resume target checkpoint has malformed member counts") from exc
            member_path = Path(item.member)
            if (
                not item.member
                or member_path.is_absolute()
                or ".." in member_path.parts
                or item.member in names
                or any(not isinstance(count, int) or count < 0 for count in (
                    item.parsed, item.inserted, item.existing, item.rejected
                ))
                or item.parsed == 0
                or item.rejected
                or not item.reconciled()
            ):
                raise ValueError("resume target checkpoint has an unreconciled completed member")
            names.add(item.member)
            parsed_rows.append(item)
        completed[artifact_key] = tuple(parsed_rows)
    return completed


def load_archive_resume(run_id: UUID) -> ArchiveResume:
    """Load a failed archive run only when its ledger proves safe member reuse."""
    runs, targets, artifacts = run_table(), run_target_table(), artifact_table()
    with session() as active_session:
        prior = active_session.execute(select(runs).where(runs.c.run_id == run_id)).mappings().first()
        if prior is None:
            raise ValueError(f"resume target {run_id} does not exist")
        if prior["dataset_id"] != ACSArchiveConnector.source_id:
            raise ValueError("resume target belongs to a different dataset")
        if prior["status"] not in {"failed", "partial"}:
            raise ValueError("resume target must be a failed or partial archive run")
        parameters = prior["parameters"]
        if not isinstance(parameters, dict):
            raise ValueError("resume target has malformed parameters")
        manifest = parameters.get("manifest")
        selected_artifacts = _saved_manifest_artifacts(manifest)
        completed = _checkpoint_members(
            parameters.get("checkpoint"), selected_artifacts, parameters.get("selected")
        )
        current_evidence: dict[str, tuple[Any, str]] = {}
        for artifact in selected_artifacts:
            current = require_current_artifact(
                artifact.artifact_key,
                label="ACS housing archive",
                dataset_id=ACSArchiveConnector.source_id,
            )
            checksum = current["checksum_sha256"]
            if not isinstance(checksum, str) or not checksum:
                raise ValueError("resume target current artifact lacks immutable checksum evidence")
            current_evidence[artifact.artifact_key] = (current["artifact_id"], checksum)
        target_rows = list(
            active_session.execute(
                select(targets).where(targets.c.run_id == run_id)
            ).mappings()
        )
        replacement_completed: dict[str, tuple[MemberReconciliation, ...]] = {}
        for artifact in selected_artifacts:
            expected_target = (
                "stage.acs_pums_record" if artifact.product.startswith("acs_pums")
                else "stage.ahs_record"
            )
            stage_table = (
                stage_acs_pums_record if artifact.product.startswith("acs_pums") else stage_ahs_record
            )
            replacement_rows: list[MemberReconciliation] = []
            for item in completed.get(artifact.artifact_key, ()):
                suffix = f";member={item.member}"
                matches: list[tuple[dict[str, Any], dict[str, Any]]] = []
                for row in target_rows:
                    coverage_key = row["coverage_key"]
                    if (
                        row["target"] != expected_target
                        or not coverage_key.startswith("artifact=")
                        or not coverage_key.endswith(suffix)
                    ):
                        continue
                    old_id = coverage_key.removeprefix("artifact=").removesuffix(suffix)
                    old_evidence = active_session.execute(
                        select(
                            artifacts.c.artifact_id,
                            artifacts.c.artifact_key,
                            artifacts.c.checksum_sha256,
                        ).where(artifacts.c.artifact_id == old_id)
                    ).mappings().first()
                    if old_evidence is not None and old_evidence["artifact_key"] == artifact.artifact_key:
                        matches.append((dict(row), dict(old_evidence)))
                if len(matches) != 1 or matches[0][0]["status"] != "succeeded":
                    raise ValueError("resume target checkpoint is not backed by a completed member ledger row")
                recorded, old_evidence = matches[0]
                if tuple(recorded[key] for key in (
                    "rows_parsed", "rows_inserted", "rows_existing", "rows_rejected"
                )) != (item.parsed, item.inserted, item.existing, item.rejected):
                    raise ValueError("resume target checkpoint does not match its member ledger row")
                if (
                    not old_evidence["checksum_sha256"]
                ):
                    raise ValueError("resume target completed member lacks immutable artifact evidence")
                current_id, current_checksum = current_evidence[artifact.artifact_key]
                if (
                    current_id != old_evidence["artifact_id"]
                    or current_checksum != old_evidence["checksum_sha256"]
                ):
                    raise ValueError("resume target completed member does not match the current immutable artifact")
                staged_count = active_session.execute(
                    select(func.count()).select_from(stage_table).where(
                        stage_table.c.artifact_id == current_id,
                        stage_table.c.source_member == item.member,
                    )
                ).scalar_one()
                if staged_count != item.parsed:
                    raise ValueError("resume target completed member no longer matches retained stage rows")
                replacement_rows.append(MemberReconciliation(item.member, item.parsed, 0, item.parsed))
            if replacement_rows:
                replacement_completed[artifact.artifact_key] = tuple(replacement_rows)
    return ArchiveResume(run_id, manifest, selected_artifacts, replacement_completed, current_evidence)


class ACSArchiveConnector:
    """Ten-stage manifest connector; transfer waits for explicit capacity approval."""

    source_id = "census.acs_housing_archive"

    def __init__(
        self, entries: Iterable[dict[str, Any]], *, transfer_approved: bool = False,
        completed_members: dict[str, tuple[MemberReconciliation, ...]] | None = None,
    ) -> None:
        self.entries = list(entries)
        self.transfer_approved = transfer_approved
        self.artifacts: list[ArchiveArtifact] = []
        self.manifest: dict[str, Any] = {}
        self.completed_members = completed_members or {}
        self.resume_evidence: dict[str, tuple[Any, str]] = {}
        self.resume_mode = False

    @classmethod
    def from_official_indexes(
        cls, indexes: Iterable[ArchiveIndex], *, transfer_approved: bool = False
    ) -> ACSArchiveConnector:
        """Discover only publisher-listed files from explicitly scoped indexes."""
        entries = [entry for index in indexes for entry in discover_archive_index(index)]
        return cls(entries, transfer_approved=transfer_approved)

    @classmethod
    def from_saved_resume(cls, resume: ArchiveResume) -> ACSArchiveConnector:
        """Construct a replacement run from saved approval, never fresh discovery."""
        connector = cls((), transfer_approved=True, completed_members=resume.completed_members)
        connector.artifacts = list(resume.artifacts)
        connector.manifest = resume.manifest
        connector.resume_evidence = resume.evidence
        connector.resume_mode = True
        return connector

    def discover(self, ctx: ConnectorContext) -> ConnectorContext:
        if not self.resume_mode:
            self.artifacts = manifest_from_index(self.entries)
        ctx.extras["gaps"] = self.manifest.get("gaps", publisher_gaps())
        return ctx

    def select(self, ctx: ConnectorContext) -> ConnectorContext:
        ctx.selected_ids = tuple(a.artifact_key for a in self.artifacts if a.selected)
        return ctx

    def plan(self, ctx: ConnectorContext) -> ConnectorContext:
        if not self.resume_mode:
            self.manifest = capacity_manifest(self.artifacts)
        if not self.manifest["approved"]:
            raise RuntimeError(f"capacity gate: {self.manifest['reason']}")
        ctx.plan_id = self.source_id
        ctx.artifact_urls = tuple(a.url for a in self.artifacts if a.selected)
        run = ctx.extras.get("ingestion_run")
        if isinstance(run, IngestionRun):
            run.update_parameters(manifest=self.manifest, selected=list(ctx.selected_ids))
        return ctx

    def extract(self, ctx: ConnectorContext) -> ConnectorContext:
        """Retain selected bytes only after an operator approved this manifest."""
        if not self.transfer_approved:
            raise RuntimeError(
                "archive manifest is capacity-approved but not transfer-approved; "
                "review it and construct the connector with transfer_approved=True"
            )
        if self.resume_mode:
            # Evidence resolves the current usable artifact below.  A resume must
            # never turn a checkpoint into a fresh transfer.
            return ctx
        paths: dict[str, str] = {}
        for artifact in self.artifacts:
            if not artifact.selected:
                continue
            filename = Path(artifact.url).name
            primary = ArtifactSpec(
                dataset_id=self.source_id,
                artifact_key=artifact.artifact_key,
                url=artifact.url,
                filename=f"{artifact.period}/{filename}",
                metadata={
                    "product": artifact.product,
                    "period": artifact.period,
                    "component": artifact.component,
                    "kind": artifact.kind,
                    "version": artifact.version,
                    "logical_url": artifact.url,
                },
                expected_bytes=artifact.bytes,
                allowed_hosts=("www2.census.gov",),
            )
            try:
                paths[artifact.artifact_key] = str(download_retrying(primary))
            except Exception as error:
                if not retryable_download_error(error):
                    raise
                alternate = verified_acs_archive_fallback(artifact.url, artifact.bytes)
                if alternate is None:
                    raise RuntimeError(
                        f"{artifact.url} failed after bounded retries and has no verified Census fallback"
                    ) from error
                discard_partial(primary)
                paths[artifact.artifact_key] = str(
                    download_retrying(
                        ArtifactSpec(
                            dataset_id=self.source_id,
                            artifact_key=artifact.artifact_key,
                            url=alternate,
                            filename=f"{artifact.period}/{filename}",
                            metadata={
                                **(primary.metadata or {}),
                                "fallback_from": artifact.url,
                                "fallback_error": str(error),
                                "fallback_verified_bytes": artifact.bytes,
                            },
                            expected_bytes=artifact.bytes,
                            allowed_hosts=("www2.census.gov",),
                        )
                    )
                )
        ctx.extras["paths"] = paths
        return ctx

    def evidence(self, ctx: ConnectorContext) -> ConnectorContext:
        """Resolve retained bytes through the current-artifact provenance boundary."""
        evidence = {
            artifact.artifact_key: require_current_artifact(
                artifact.artifact_key, label="ACS housing archive", dataset_id=self.source_id
            )
            for artifact in self.artifacts
            if artifact.selected
        }
        if self.resume_mode:
            for artifact_key, row in evidence.items():
                expected = self.resume_evidence.get(artifact_key)
                if expected is None or (row["artifact_id"], row["checksum_sha256"]) != expected:
                    raise ValueError("current immutable artifact changed after resume validation")
        ctx.extras["evidence"] = evidence
        ctx.checksums = tuple(
            str(row["checksum_sha256"]) for row in evidence.values() if row["checksum_sha256"]
        )
        return ctx

    def stage(self, ctx: ConnectorContext) -> ConnectorContext:
        """Stage source-shaped CSV rows with artifact/member/ordinal lineage."""
        counts: dict[str, int] = {}
        member_counts: dict[str, list[dict[str, Any]]] = {}
        ctx.extras["stage_counts"] = counts
        ctx.extras["member_counts"] = member_counts
        for artifact in self.artifacts:
            if not artifact.selected or artifact.kind != "data":
                continue
            evidence = ctx.extras["evidence"][artifact.artifact_key]
            completed: list[MemberReconciliation] = []

            def record(
                item: MemberReconciliation,
                artifact: ArchiveArtifact = artifact,
                evidence: dict[str, Any] = evidence,
                completed: list[MemberReconciliation] = completed,
            ) -> None:
                completed.append(item)
                member_counts[artifact.artifact_key] = [asdict(member) for member in completed]
                counts[artifact.artifact_key] = sum(member.parsed for member in completed)
                self._record_member(ctx, artifact, evidence["artifact_id"], item)
                self._persist_member_checkpoint(ctx)

            for item in self.completed_members.get(artifact.artifact_key, ()):
                record(item)

            try:
                reconciliations = stage_artifact_members(
                    artifact,
                    Path(evidence["local_path"]),
                    evidence["artifact_id"],
                    on_member=record,
                    completed_members=self.completed_members.get(artifact.artifact_key, ()),
                )
            except Exception as exc:
                self._record_member_failure(
                    ctx, artifact, evidence, getattr(exc, "member", "<unreadable>")
                )
                self._persist_member_checkpoint(ctx)
                raise
            if not reconciliations:
                self._record_member_failure(ctx, artifact, evidence, "<unreadable>")
                self._persist_member_checkpoint(ctx)
                raise ValueError(f"selected archive data has no CSV members: {artifact.artifact_key}")
        return ctx

    @staticmethod
    def _coverage_key(artifact_id: Any, member: str) -> str:
        return f"artifact={artifact_id};member={member}"

    def _record_member(
        self, ctx: ConnectorContext, artifact: ArchiveArtifact, artifact_id: Any,
        item: MemberReconciliation,
    ) -> None:
        run = ctx.extras.get("ingestion_run")
        if not isinstance(run, IngestionRun):
            return
        target = "stage.acs_pums_record" if artifact.product.startswith("acs_pums") else "stage.ahs_record"
        run.record_target(
            target, self._coverage_key(artifact_id, item.member),
            inserted=item.inserted, parsed=item.parsed, existing=item.existing,
            rejected=item.rejected,
            status="succeeded" if item.parsed and item.reconciled() and not item.rejected else "failed",
        )

    def _record_member_failure(
        self, ctx: ConnectorContext, artifact: ArchiveArtifact, evidence: dict[str, Any], member: str
    ) -> None:
        """Leave a failed artifact slice, retaining its known source-member name."""
        run = ctx.extras.get("ingestion_run")
        if isinstance(run, IngestionRun):
            target = "stage.acs_pums_record" if artifact.product.startswith("acs_pums") else "stage.ahs_record"
            run.record_target(target, self._coverage_key(evidence["artifact_id"], member), status="failed")

    @staticmethod
    def _persist_member_checkpoint(ctx: ConnectorContext) -> None:
        """Persist each committed member before another source member can begin."""
        ctx.cursor["selected"] = list(ctx.selected_ids)
        ctx.cursor["staged"] = ctx.extras.get("stage_counts", {})
        ctx.cursor["members"] = ctx.extras.get("member_counts", {})
        run = ctx.extras.get("ingestion_run")
        if isinstance(run, IngestionRun):
            run.checkpoint(ctx.cursor)

    def normalize(self, ctx: ConnectorContext) -> ConnectorContext:
        """Keep the raw stage faithful; reviewed field mappings are a later projection."""
        return ctx

    def validate(self, ctx: ConnectorContext) -> ConnectorContext:
        """Reject a selected data file which produced no source rows."""
        empty = [key for key, count in ctx.extras.get("stage_counts", {}).items() if count == 0]
        if empty:
            raise ValueError(f"selected archive data produced no staged rows: {', '.join(empty)}")
        unreconciled = [
            f"{artifact_key}/{item['member']}"
            for artifact_key, members in ctx.extras.get("member_counts", {}).items()
            for item in members
            if item["parsed"] != item["inserted"] + item["existing"] + item["rejected"]
            or item["rejected"]
        ]
        if unreconciled:
            raise ValueError("archive members did not reconcile: " + ", ".join(unreconciled))
        return ctx

    def publish(self, ctx: ConnectorContext) -> ConnectorContext:
        """Publish provenance-linked data releases and their current-run projection."""
        release = housing_archive_release_table
        data_artifact_ids: set[Any] = set()
        with session() as active_session:
            for artifact in self.artifacts:
                if not artifact.selected or artifact.kind != "data":
                    continue
                evidence = ctx.extras["evidence"][artifact.artifact_key]
                data_artifact_ids.add(evidence["artifact_id"])
                statement = insert(release).values(
                    dataset_id=self.source_id,
                    product=artifact.product,
                    period=artifact.period,
                    component=artifact.component,
                    status="standard",
                    source_artifact_id=evidence["artifact_id"],
                    metadata={"kind": artifact.kind, "version": artifact.version},
                )
                active_session.execute(statement.on_conflict_do_nothing())
        ctx.extras["projected_rows"] = publish_policy_projection(data_artifact_ids)
        return ctx

    def checkpoint(self, ctx: ConnectorContext) -> ConnectorContext:
        """Leave an actionable in-memory resume cursor for a caller to persist."""
        ctx.cursor["selected"] = list(ctx.selected_ids)
        ctx.cursor["staged"] = ctx.extras.get("stage_counts", {})
        ctx.cursor["members"] = ctx.extras.get("member_counts", {})
        return ctx


def _csv_members(path: Path) -> Iterator[tuple[str, Iterator[dict[str, str]]]]:
    """Yield CSV members from a retained CSV or ZIP without mutating its bytes."""
    if path.suffix.lower() == ".zip":
        with zipfile.ZipFile(path) as archive:
            for name in archive.namelist():
                if name.lower().endswith(".csv"):
                    member_path = Path(name)
                    if member_path.is_absolute() or ".." in member_path.parts:
                        raise MemberStagingError(name, f"unsafe ZIP CSV member: {name}")
                    with archive.open(name) as raw:
                        yield name, _checked_reader(name, raw)
    elif path.suffix.lower() == ".csv":
        with path.open(encoding="latin-1", newline="") as raw:
            yield path.name, _checked_reader(path.name, raw)
    else:
        raise ValueError(f"selected archive data is not CSV or ZIP: {path.name}")


def _checked_reader(member: str, raw: Any) -> csv.DictReader:
    """Reject ambiguous headers before a row can lose its original field identity."""
    reader = csv.DictReader(raw if isinstance(raw, io.TextIOBase) else io.TextIOWrapper(raw, encoding="latin-1"))
    header = reader.fieldnames
    if not header or any(not field or not field.strip() for field in header):
        raise MemberStagingError(member, f"CSV member has an empty header: {member}")
    if len(set(header)) != len(header):
        raise MemberStagingError(member, f"CSV member has duplicate headers: {member}")
    return reader


def _pums_record_type(member: str) -> str:
    """Identify a PUMS person or housing member across legacy CSV names."""
    name = Path(member).name.casefold()
    if name.startswith(("csv_p", "psam_p", "pums_p")):
        return "person"
    if name.startswith(("csv_h", "psam_h", "pums_h")):
        return "housing"
    if name.startswith("ss") and len(name) > 4 and name[2:4].isdigit():
        if name[4] == "p":
            return "person"
        if name[4] == "h":
            return "housing"
    raise ValueError(f"unrecognised PUMS CSV member type: {member}")


def stage_artifact(artifact: ArchiveArtifact, path: Path, artifact_id: Any) -> int:
    """Idempotently stage a retained PUMS or AHS CSV artifact."""
    return sum(item.parsed for item in stage_artifact_members(artifact, path, artifact_id))


def stage_artifact_members(
    artifact: ArchiveArtifact, path: Path, artifact_id: Any,
    *, on_member: Callable[[MemberReconciliation], None] | None = None,
    completed_members: Iterable[MemberReconciliation] = (),
) -> list[MemberReconciliation]:
    """Stage unfinished CSV members while retaining validated completed counts."""
    table = stage_acs_pums_record if artifact.product.startswith("acs_pums") else stage_ahs_record
    completed = list(completed_members)
    completed_by_name = {item.member: item for item in completed}
    if len(completed_by_name) != len(completed):
        raise ValueError("completed archive member checkpoint has duplicate names")
    reconciliations: list[MemberReconciliation] = list(completed)
    seen: set[str] = set()
    for member, rows in _csv_members(path):
        seen.add(member)
        if member in completed_by_name:
            continue
        # Commit each member independently so an interruption has a durable,
        # resumable slice rather than an all-or-nothing artifact transaction.
        try:
            with session() as active_session:
                parsed = inserted_count = existing = 0
                for ordinal, row in enumerate(rows, start=1):
                    if None in row or any(value is None for value in row.values()):
                        raise MemberStagingError(member, f"malformed CSV row in {member} at ordinal {ordinal}")
                    values: dict[str, Any] = {
                        "artifact_id": artifact_id,
                        "source_member": member,
                        "source_ordinal": ordinal,
                        "raw": row,
                    }
                    if table is stage_acs_pums_record:
                        try:
                            record_type = _pums_record_type(member)
                        except ValueError as exc:
                            raise MemberStagingError(member, str(exc)) from exc
                        values.update(
                            product=artifact.product,
                            period=artifact.period,
                            record_type=record_type,
                            puma=row.get("PUMA") or row.get("PUMA20"),
                        )
                    else:
                        values.update(
                            release_year=int(artifact.period), component=artifact.component,
                            table_name=Path(member).stem,
                        )
                    statement = insert(table).values(**values)
                    result = active_session.execute(
                        statement.on_conflict_do_nothing().returning(table.c.artifact_id)
                    )
                    parsed += 1
                    if result.scalar_one_or_none() is not None:
                        inserted_count += 1
                    else:
                        existing += 1
                reconciliation = MemberReconciliation(member, parsed, inserted_count, existing)
        except MemberStagingError:
            raise
        except Exception as exc:
            raise MemberStagingError(member, str(exc)) from exc
        reconciliations.append(reconciliation)
        if on_member is not None:
            on_member(reconciliation)
    missing = set(completed_by_name) - seen
    if missing:
        member = min(missing)
        raise MemberStagingError(member, f"completed archive member is absent from current artifact: {member}")
    return reconciliations


def _number(value: str | None, kind: type[int | float]) -> int | float | None:
    """Convert a published Census scalar without inventing a value for a blank."""
    if value in (None, "", "N", "NA"):
        return None
    try:
        return kind(value)
    except ValueError:
        return None


def _first(row: dict[str, str], *names: str) -> str | None:
    """Use the documented variable spelling present in this release."""
    return next((row[name] for name in names if row.get(name) not in (None, "")), None)


def publish_policy_projection(artifact_ids: set[Any] | None = None) -> int:
    """Idempotently project approved policy fields from retained staged records.

    It intentionally reads stage rather than a live download.  A new approved
    field can therefore be added here and re-published from immutable evidence.
    """
    projection = housing_microdata_projection_table
    total = 0
    with session() as active_session:
        for table, default_component in (
            (stage_acs_pums_record, "pums"),
            (stage_ahs_record, None),
        ):
            statement = select(table)
            if artifact_ids is not None:
                statement = statement.where(table.c.artifact_id.in_(artifact_ids))
            for staged in active_session.execute(statement).mappings():
                raw = dict(staged["raw"])
                is_pums = table is stage_acs_pums_record
                values: dict[str, Any] = {
                    "artifact_id": staged["artifact_id"],
                    "source_member": staged["source_member"],
                    "source_ordinal": staged["source_ordinal"],
                    "product": staged["product"] if is_pums else "ahs",
                    "period": staged["period"] if is_pums else str(staged["release_year"]),
                    "component": default_component if is_pums else staged["component"],
                    "record_type": staged["record_type"] if is_pums else "unit",
                    "puma": staged.get("puma"),
                    "weight": _number(_first(raw, "PWGTP", "WGTP", "WEIGHT"), float),
                    "age": _number(_first(raw, "AGEP", "AGE"), int),
                    "sex": _first(raw, "SEX"),
                    "race": _first(raw, "RAC1P", "RACE"),
                    "ethnicity": _first(raw, "HISP", "HISPAN"),
                    "income": _number(_first(raw, "PINCP", "HINCP", "INCOME"), float),
                    "poverty_ratio": _number(_first(raw, "POVPIP", "POVERTY"), float),
                    "education": _first(raw, "SCHL", "EDUC"),
                    "employment_status": _first(raw, "ESR", "EMPLOYMENT"),
                    "tenure": _first(raw, "TEN", "TENURE"),
                    "rent": _number(_first(raw, "RNTP", "RENT"), float),
                    "gross_rent": _number(_first(raw, "GRNTP", "GROSS_RENT"), float),
                    "property_value": _number(_first(raw, "VALP", "VALUE"), float),
                    "year_built": _number(_first(raw, "YBL", "YEAR_BUILT"), int),
                }
                statement = insert(projection).values(**values)
                active_session.execute(statement.on_conflict_do_nothing())
                total += 1
    return total


def catalog_field_definitions(
    rows: Iterable[dict[str, str]], *, period: str, artifact_id: Any
) -> int:
    """Persist official dictionary rows with the evidence that defined them.

    Dictionary adapters supply their parsed rows (CSV, spreadsheet, or a
    publisher-specific codebook parser).  The fixed catalog contract means an
    unrecognised row is rejected rather than becoming an undocumented field.
    """
    try:
        valid_from = date.fromisoformat(f"{int(period[:4])}-01-01")
    except (TypeError, ValueError) as exc:
        raise ValueError(f"field dictionary period must begin with a year: {period!r}") from exc
    table = DatasetField.__table__
    count = 0
    with session() as active_session:
        for row in rows:
            field_id = _first(row, "field_id", "variable", "Variable", "NAME")
            label = _first(row, "label", "Label", "description", "Description")
            if field_id is None or label is None:
                raise ValueError("official field definition is missing variable or definition")
            statement = insert(table).values(
                dataset_id="census.acs_housing_archive",
                field_id=field_id,
                valid_from=valid_from,
                label=label,
                data_type=_first(row, "data_type", "type", "Type"),
                description=label,
                metadata={
                    "source_artifact_id": str(artifact_id),
                    "value_labels": row.get("value_labels", ""),
                    "period": period,
                },
            )
            active_session.execute(
                statement.on_conflict_do_update(
                    index_elements=(table.c.dataset_id, table.c.field_id, table.c.valid_from),
                    set_={
                        "label": statement.excluded.label,
                        "data_type": statement.excluded.data_type,
                        "description": statement.excluded.description,
                        "metadata": statement.excluded["metadata"],
                    },
                )
            )
            count += 1
    return count


def resume_archive_run(run_id: UUID) -> ConnectorContext:
    """Replace one interrupted archive run using only its saved approved evidence."""
    resume = load_archive_resume(run_id)
    connector = ACSArchiveConnector.from_saved_resume(resume)
    run = IngestionRun(
        connector.source_id,
        {"resumed_from_run_id": str(resume.predecessor_run_id)},
    )
    from .connector import run_connector

    return run_connector(connector, run=run)


def main(argv: list[str] | None = None) -> int:
    """Run the standalone, approval-gated archive refresh command."""
    import argparse

    parser = argparse.ArgumentParser(description="Refresh the approved ACS PUMS/AHS archive")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--indexes", type=Path, help="Reviewed YAML list of official index identities")
    source.add_argument("--all-official-indexes", action="store_true", help="Discover every approved PUMS/AHS release directory")
    source.add_argument("--resume-run", type=UUID, help="Replace one failed or partial archive run")
    parser.add_argument("--approve-transfer", action="store_true", help="Confirm review of the exact capacity manifest")
    args = parser.parse_args(argv)
    if args.resume_run is not None:
        if not args.approve_transfer:
            raise ValueError("resuming an archive run requires a fresh --approve-transfer")
        context = resume_archive_run(args.resume_run)
        print({"resumed_from_run_id": str(args.resume_run), "staged": context.extras.get("stage_counts", {})})
        return 0
    if args.all_official_indexes:
        indexes = official_housing_archive_indexes()
    else:
        payload = yaml.safe_load(args.indexes.read_text()) or {}
        entries = payload.get("indexes", payload)
        if not isinstance(entries, list):
            raise ValueError("index manifest must contain an indexes list")
        indexes = [ArchiveIndex(**entry) for entry in entries]
    connector = ACSArchiveConnector.from_official_indexes(
        indexes, transfer_approved=args.approve_transfer
    )
    if not args.approve_transfer:
        context = ConnectorContext(source_id=connector.source_id)
        context = connector.discover(context)
        context = connector.select(context)
        connector.plan(context)
        print(json.dumps(connector.manifest, indent=2, sort_keys=True))
        return 0

    from .connector import run_connector

    run = IngestionRun(connector.source_id, {})
    context = run_connector(connector, run=run)
    print({"selected": len(context.selected_ids), "staged": context.extras.get("stage_counts", {})})
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised as an operational command
    raise SystemExit(main())
