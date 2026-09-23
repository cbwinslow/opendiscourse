"""Connector for current committee membership from congress-legislators.

Downloads three pinned YAML files over HTTP into ``DATA_ROOT``, keeps them as
evidence, and loads every committee body plus the current member snapshot.
A subcommittee's identity is the membership-file key: the parent thomas id
plus the short code (``SSAF`` + ``13``). Short codes such as ``01`` repeat
across parents and are not unique. People link only on BioGuide. This loader
does not read ``vendor/`` and does not scrape Clerk HTML.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx
import yaml

from ..artifact_storage import retain_artifact_bytes, retained_path
from ..capacity import GiB, RemoteObject, storage_preview
from ..config import settings
from ..db import connect
from ..repositories.committees import publish_committee_membership, try_sync_lock
from ..repositories.legislation import register_artifact
from .base import IngestionRun
from .connector import ConnectorContext

SOURCE_ID = "congress.committee_membership"
LOCK_KEY = f"{SOURCE_ID}:sync"
UPSTREAM = "https://raw.githubusercontent.com/unitedstates/congress-legislators"
# Pinned so a rerun fetches the same bytes until this constant changes.
COMMIT = "8a3c7e6987f890b32e56058f7ddbdf380860b4a3"
COMMIT_DATE = "2026-09-03"
CURRENT = "committees-current.yaml"
HISTORICAL = "committees-historical.yaml"
MEMBERSHIP = "committee-membership-current.yaml"
FILES = (CURRENT, HISTORICAL, MEMBERSHIP)
CHAMBERS = frozenset({"house", "senate", "joint"})
MEMBER_CHAMBERS = frozenset({"house", "senate"})
PARTIES = frozenset({"majority", "minority"})
CAPACITY_RESERVE_BYTES = GiB
_OPTIONAL = (
    "url",
    "minority_url",
    "house_committee_id",
    "senate_committee_id",
    "address",
    "phone",
    "rss_url",
    "minority_rss_url",
    "jurisdiction",
    "jurisdiction_source",
    "wikipedia",
    "youtube_id",
)

_Loader = getattr(yaml, "CSafeLoader", yaml.SafeLoader)


@dataclass
class Body:
    """One committee or subcommittee as one file states it."""

    source_file: str
    thomas_key: str
    parent_thomas_key: str | None
    kind: str
    chamber: str
    name: str
    fields: dict[str, str | None]
    congresses: list[int]
    former_names: dict[str, str]
    record: dict[str, Any]


@dataclass
class Member:
    """One current assignment. ``person_id`` is filled at publish, not from the file."""

    thomas_key: str
    bioguide: str
    party: str
    rank: int
    title: str | None
    stated_name: str
    chamber: str | None
    record: dict[str, Any]


@dataclass
class SourceRow:
    """One whole file row: a body (blank bioguide) or one member."""

    source_file: str
    thomas_key: str
    bioguide: str
    record: dict[str, Any]


@dataclass
class Snapshot:
    """The three files, validated, before any database write."""

    committees: list[dict[str, Any]]
    members: list[Member]
    source_rows: list[SourceRow]
    preferred_file: dict[str, str] = field(default_factory=dict)


def file_url(name: str, *, origin: str = UPSTREAM, commit: str = COMMIT) -> str:
    """Permalink of one upstream file at the pinned commit."""
    return f"{origin.rstrip('/')}/{commit}/{name}"


def _json_ready(value: Any, where: str) -> Any:
    """YAML values as JSON. Mapping keys become strings (JSON has no integer keys)."""
    if isinstance(value, dict):
        return {str(key): _json_ready(item, where) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_ready(item, where) for item in value]
    if value is None or isinstance(value, (str, float, bool)) or type(value) is int:
        return value
    raise ValueError(f"{where} has an unsupported value ({type(value).__name__})")


def _load_yaml(name: str, content: bytes) -> Any:
    try:
        return yaml.load(content, Loader=_Loader)
    except yaml.YAMLError as exc:
        raise ValueError(f"{name} is not valid YAML") from exc


def _text(record: Mapping[str, Any], key: str, where: str, *, required: bool) -> str | None:
    if key not in record or record[key] is None:
        if required:
            raise ValueError(f"{where} is missing {key}")
        return None
    value = record[key]
    if not isinstance(value, str) or (required and not value.strip()):
        raise ValueError(f"{where} {key} must be text")
    return value.strip() if key in {"thomas_id", "bioguide"} else value


def _congresses(raw: Any, where: str) -> list[int]:
    if raw is None:
        return []
    if not isinstance(raw, list) or any(type(item) is not int for item in raw):
        raise ValueError(f"{where} congresses must be a list of integers")
    return list(raw)


def _former_names(raw: Any, where: str) -> dict[str, str]:
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ValueError(f"{where} names must be a mapping of Congress to name")
    names: dict[str, str] = {}
    for key, name in raw.items():
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"{where} former name for Congress {key} must be text")
        names[str(key)] = name
    return names


def _optional_fields(record: Mapping[str, Any], where: str) -> dict[str, str | None]:
    return {key: _text(record, key, where, required=False) for key in _OPTIONAL}


def _bodies(name: str, document: Any) -> list[Body]:
    """Flatten a committee file. A subcommittee key is parent code plus short code."""
    if not isinstance(document, list) or not document:
        raise ValueError(f"{name} must be a non-empty list of committees")
    bodies: list[Body] = []
    seen: set[str] = set()
    for index, committee in enumerate(document):
        where = f"{name} committee #{index + 1}"
        if not isinstance(committee, dict):
            raise ValueError(f"{where} is not a mapping")
        parent = _text(committee, "thomas_id", where, required=True)
        assert parent is not None
        chamber = _text(committee, "type", where, required=True)
        if chamber not in CHAMBERS:
            raise ValueError(f"{where} type must be house, senate, or joint")
        label = _text(committee, "name", where, required=True)
        assert label is not None and chamber is not None
        subs = committee.get("subcommittees")
        if subs is None:
            subs = []
        if not isinstance(subs, list):
            raise ValueError(f"{where} subcommittees must be a list")
        _add_body(
            bodies,
            seen,
            Body(
                source_file=name,
                thomas_key=parent,
                parent_thomas_key=None,
                kind="committee",
                chamber=chamber,
                name=label,
                fields=_optional_fields(committee, where),
                congresses=_congresses(committee.get("congresses"), where),
                former_names=_former_names(committee.get("names"), where),
                record=_json_ready(committee, where),
            ),
        )
        for sub_index, sub in enumerate(subs):
            sub_where = f"{where} subcommittee #{sub_index + 1}"
            if not isinstance(sub, dict):
                raise ValueError(f"{sub_where} is not a mapping")
            short = _text(sub, "thomas_id", sub_where, required=True)
            assert short is not None
            sub_name = _text(sub, "name", sub_where, required=True)
            assert sub_name is not None
            # The membership file writes SSAF13, not the short code 13.
            full = f"{parent}{short}"
            _add_body(
                bodies,
                seen,
                Body(
                    source_file=name,
                    thomas_key=full,
                    parent_thomas_key=parent,
                    kind="subcommittee",
                    chamber=chamber,
                    name=sub_name,
                    fields=_optional_fields(sub, sub_where),
                    congresses=_congresses(sub.get("congresses"), sub_where),
                    former_names=_former_names(sub.get("names"), sub_where),
                    record=_json_ready(sub, sub_where),
                ),
            )
    return bodies


def _add_body(bodies: list[Body], seen: set[str], body: Body) -> None:
    if body.thomas_key in seen:
        raise ValueError(f"{body.source_file} repeats committee key {body.thomas_key}")
    seen.add(body.thomas_key)
    bodies.append(body)


def _members(document: Any, current_keys: set[str]) -> list[Member]:
    if not isinstance(document, dict) or not document:
        raise ValueError(f"{MEMBERSHIP} must be a non-empty mapping of committee key to members")
    members: list[Member] = []
    for key, rows in document.items():
        thomas_key = str(key)
        where = f"{MEMBERSHIP} {thomas_key}"
        if thomas_key not in current_keys:
            raise ValueError(f"{where} is not a committee in {CURRENT}")
        if not isinstance(rows, list):
            raise ValueError(f"{where} members must be a list")
        seen: set[str] = set()
        for index, row in enumerate(rows):
            member_where = f"{where} member #{index + 1}"
            if not isinstance(row, dict):
                raise ValueError(f"{member_where} is not a mapping")
            bioguide = _text(row, "bioguide", member_where, required=True)
            stated = _text(row, "name", member_where, required=True)
            party = _text(row, "party", member_where, required=True)
            assert bioguide is not None and stated is not None and party is not None
            if party not in PARTIES:
                raise ValueError(f"{member_where} party must be majority or minority")
            if type(row.get("rank")) is not int:
                raise ValueError(f"{member_where} rank must be an integer")
            if bioguide in seen:
                raise ValueError(f"{where} lists BioGuide {bioguide} twice")
            seen.add(bioguide)
            chamber = _text(row, "chamber", member_where, required=False)
            if chamber is not None and chamber not in MEMBER_CHAMBERS:
                raise ValueError(f"{member_where} chamber must be house or senate")
            title = _text(row, "title", member_where, required=False)
            members.append(
                Member(
                    thomas_key=thomas_key,
                    bioguide=bioguide,
                    party=party,
                    rank=row["rank"],
                    title=title,
                    stated_name=stated,
                    chamber=chamber,
                    record=_json_ready(row, member_where),
                )
            )
    return members


def _merge(current: Body | None, historical: Body | None) -> dict[str, Any]:
    """One committee. The current file wins identity and description.

    The historical file can disagree (the Helsinki Commission is ``joint`` now and
    ``senate`` in the historical file). That older wording stays in the historical
    source record. Historical congresses and former names still attach.
    """
    base = current or historical
    assert base is not None
    fields = dict(base.fields)
    return {
        "thomas_key": base.thomas_key,
        "parent_thomas_key": base.parent_thomas_key,
        "kind": base.kind,
        "chamber": base.chamber,
        "name": base.name,
        **fields,
        "congresses": historical.congresses if historical is not None else [],
        "former_names": historical.former_names if historical is not None else {},
        "preferred_file": CURRENT if current is not None else HISTORICAL,
        "has_history": historical is not None and current is not None,
    }


def parse_committee_files(contents: Mapping[str, bytes]) -> Snapshot:
    """Validate the three files. Raises before the caller writes anything."""
    missing = [name for name in FILES if name not in contents]
    if missing:
        raise ValueError(f"missing committee file(s): {', '.join(missing)}")
    documents = {name: _load_yaml(name, contents[name]) for name in FILES}
    current = _bodies(CURRENT, documents[CURRENT])
    historical = _bodies(HISTORICAL, documents[HISTORICAL])
    current_by = {body.thomas_key: body for body in current}
    historical_by = {body.thomas_key: body for body in historical}
    overlap = set(current_by) & set(historical_by)
    for key in overlap:
        _merge(current_by[key], historical_by[key])
    committees = [
        _merge(current_by.get(key), historical_by.get(key))
        for key in sorted(set(current_by) | set(historical_by))
    ]
    members = _members(documents[MEMBERSHIP], set(current_by))
    names_by_bioguide: dict[str, str] = {}
    for member in members:
        previous = names_by_bioguide.setdefault(member.bioguide, member.stated_name)
        if previous != member.stated_name:
            raise ValueError(
                f"BioGuide {member.bioguide} has two printed names in {MEMBERSHIP}: "
                f"{previous!r} and {member.stated_name!r}"
            )
    source_rows = [
        SourceRow(body.source_file, body.thomas_key, "", body.record)
        for body in (*current, *historical)
    ]
    source_rows.extend(
        SourceRow(MEMBERSHIP, member.thomas_key, member.bioguide, member.record)
        for member in members
    )
    return Snapshot(
        committees=committees,
        members=members,
        source_rows=source_rows,
        preferred_file={row["thomas_key"]: row["preferred_file"] for row in committees},
    )


class CommitteeMembershipConnector:
    """Ten-stage Connector. Publish is one transaction; a bad file writes nothing."""

    source_id = SOURCE_ID

    def __init__(
        self,
        *,
        origin: str = UPSTREAM,
        commit: str = COMMIT,
        vintage: str = COMMIT_DATE,
        http: httpx.Client | None = None,
        report: Callable[[str], None] | None = None,
    ) -> None:
        self._origin = origin
        self._commit = commit
        self._vintage = vintage
        self._http = http
        self._owns_http = http is None
        self._report = report or (lambda phase: None)
        self._run: IngestionRun | None = None
        self._lock: Any = None
        self._sizes: dict[str, int] = {}
        self._content: dict[str, bytes] = {}
        self._checksums: dict[str, str] = {}
        self._artifacts: dict[str, str] = {}
        self._snapshot: Snapshot | None = None
        self._finished = False
        self.result: dict[str, Any] = {}

    def discover(self, ctx: ConnectorContext) -> ConnectorContext:
        """Pin the commit and learn each file's size. A missing file stops before any download."""
        self._acquire_lock()
        self._run = IngestionRun(
            SOURCE_ID,
            {"commit": self._commit, "files": list(FILES), "vintage": self._vintage},
            mode="backfill",
        )
        self._run.__enter__()
        ctx.run_id = str(self._run.run_id)
        for name in FILES:
            url = file_url(name, origin=self._origin, commit=self._commit)
            self._report(f"checking origin: {name}")
            self._sizes[name] = self._size(url, name)
        return ctx

    def select(self, ctx: ConnectorContext) -> ConnectorContext:
        """All three files. There is no smaller slice."""
        ctx.selected_ids = FILES
        self._report("selected files")
        return ctx

    def plan(self, ctx: ConnectorContext) -> ConnectorContext:
        """Capacity gate. An unknown size refuses the run."""
        ctx.plan_id = f"{SOURCE_ID}@{self._commit[:12]}"
        ctx.artifact_urls = tuple(file_url(name, origin=self._origin, commit=self._commit) for name in FILES)
        preview = storage_preview(
            [RemoteObject(url, self._sizes[name], "head") for name, url in zip(FILES, ctx.artifact_urls, strict=True)],
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
        self._report("planned download")
        return ctx

    def extract(self, ctx: ConnectorContext) -> ConnectorContext:
        """Download, then refuse a bad file before any evidence or promotion."""
        for name, url in zip(FILES, ctx.artifact_urls, strict=True):
            self._report(f"downloading {name}")
            body = self._download(url, name, self._sizes[name])
            self._content[name] = body
            self._checksums[name] = hashlib.sha256(body).hexdigest()
        self._snapshot = parse_committee_files(self._content)
        ctx.checksums = tuple(self._checksums[name] for name in FILES)
        self._report("validated files")
        return ctx

    def evidence(self, ctx: ConnectorContext) -> ConnectorContext:
        """Retain the verified bytes. A new checksum is a new artifact version; the old file stays."""
        root = Path(settings.data_root).expanduser().resolve() / "congress" / "committee_membership"
        root.mkdir(parents=True, exist_ok=True)
        with connect() as conn:
            for name, url in zip(FILES, ctx.artifact_urls, strict=True):
                checksum = self._checksums[name]
                destination = retained_path(root / name, checksum)
                # Same directory as the retained file so the publish can be a hard link.
                staging = root / f".{name}.{checksum}.incoming"
                staging.write_bytes(self._content[name])
                retained = retain_artifact_bytes(
                    staging, checksum, destination=destination, move=True
                )
                artifact = register_artifact(
                    SOURCE_ID,
                    url,
                    str(retained),
                    name,
                    status="downloaded",
                    checksum_sha256=checksum,
                    bytes_downloaded=len(self._content[name]),
                    content_type="application/yaml",
                    metadata={"upstream_commit": self._commit, "file": name},
                    conn=conn,
                )
                self._artifacts[name] = str(artifact["artifact_id"])
            conn.commit()
        self._report("retained evidence")
        return ctx

    def stage(self, ctx: ConnectorContext) -> ConnectorContext:
        """The parsed snapshot is already the stage. Nothing is written here."""
        if self._snapshot is None:
            raise RuntimeError("committee files were not parsed")
        self._report("staged snapshot")
        return ctx

    def normalize(self, ctx: ConnectorContext) -> ConnectorContext:
        """Keys are already the membership-file ids. Party words stay majority and minority."""
        self._report("normalized keys")
        return ctx

    def validate(self, ctx: ConnectorContext) -> ConnectorContext:
        """Parse again from the retained bytes so a damaged read cannot publish."""
        self._snapshot = parse_committee_files(self._content)
        self._report("validated")
        return ctx

    def publish(self, ctx: ConnectorContext) -> ConnectorContext:
        """One transaction: committees, the assignment snapshot, source rows, and roster names."""
        snapshot = self._snapshot
        if snapshot is None or ctx.run_id is None:
            raise RuntimeError("committee snapshot is not ready to publish")
        committees = []
        for row in snapshot.committees:
            preferred = row["preferred_file"]
            committees.append(
                {
                    "thomas_key": row["thomas_key"],
                    "parent_thomas_key": row["parent_thomas_key"],
                    "kind": row["kind"],
                    "chamber": row["chamber"],
                    "name": row["name"],
                    **{key: row[key] for key in _OPTIONAL},
                    "congresses": row["congresses"],
                    "former_names": row["former_names"],
                    "source_artifact_id": self._artifacts[preferred],
                    "history_artifact_id": self._artifacts[HISTORICAL] if row["has_history"] else None,
                    "run_id": ctx.run_id,
                }
            )
        membership_artifact = self._artifacts[MEMBERSHIP]
        assignments = [
            {
                "thomas_key": member.thomas_key,
                "bioguide": member.bioguide,
                "party": member.party,
                "rank": member.rank,
                "title": member.title,
                "stated_name": member.stated_name,
                "chamber": member.chamber,
                "source_artifact_id": membership_artifact,
                "run_id": ctx.run_id,
            }
            for member in snapshot.members
        ]
        source_records = [
            {
                "source_file": row.source_file,
                "thomas_key": row.thomas_key,
                "bioguide": row.bioguide,
                "record": row.record,
                "source_artifact_id": self._artifacts[row.source_file],
                "run_id": ctx.run_id,
            }
            for row in snapshot.source_rows
        ]
        with connect() as conn:
            counts = publish_committee_membership(
                conn,
                committees=committees,
                assignments=assignments,
                source_records=source_records,
                run_id=ctx.run_id,
                vintage=self._vintage,
                membership_artifact_id=membership_artifact,
            )
            for name, url in zip(FILES, ctx.artifact_urls, strict=True):
                register_artifact(
                    SOURCE_ID,
                    url,
                    str(
                        retained_path(
                            Path(settings.data_root).expanduser().resolve()
                            / "congress"
                            / "committee_membership"
                            / name,
                            self._checksums[name],
                        )
                    ),
                    name,
                    status="loaded",
                    checksum_sha256=self._checksums[name],
                    bytes_downloaded=len(self._content[name]),
                    content_type="application/yaml",
                    metadata={"upstream_commit": self._commit, "file": name},
                    conn=conn,
                )
            conn.commit()
        unknown = counts["unknown_bioguide_ids"]
        self.result = {
            **counts,
            "commit": self._commit,
            "vintage": self._vintage,
            "partial": bool(unknown),
        }
        if self._run is not None:
            self._run.record_count = counts["committees"] + counts["assignments"]
            self._run.record_target(
                "core.committee",
                "current",
                inserted=counts["committees_inserted"],
                updated=counts["committees_updated"],
                skipped=counts["committees"] - counts["committees_inserted"] - counts["committees_updated"],
            )
            self._run.record_target(
                "core.committee_assignment",
                "current",
                inserted=counts["assignments_inserted"],
                updated=counts["assignments_updated"],
                skipped=counts["assignments"]
                - counts["assignments_inserted"]
                - counts["assignments_updated"],
                status="partial" if unknown else "succeeded",
            )
        self._finished = True
        self._report("published")
        return ctx

    def checkpoint(self, ctx: ConnectorContext) -> ConnectorContext:
        """Close the run once. Unknown BioGuide ids make the run partial, not a failure."""
        failure: BaseException | None = None
        if self._run is not None and (ctx.error or not self._finished):
            failure = RuntimeError(ctx.error or "interrupted before publish finished")
        try:
            if failure is None and self.result.get("partial") and self._run is not None:
                self._run.mark_partial()
        finally:
            try:
                if self._run is not None:
                    self._run.__exit__(type(failure) if failure else None, failure, None)
                    self._run = None
            finally:
                if self._lock is not None:
                    self._lock.close()
                    self._lock = None
                if self._owns_http and self._http is not None:
                    self._http.close()
                    self._http = None
        self._report("checkpointed")
        return ctx

    def _client(self) -> httpx.Client:
        if self._http is None:
            self._http = httpx.Client(
                timeout=45,
                follow_redirects=True,
                # Identity encoding: GitHub's HEAD content-length is the compressed
                # size when gzip is accepted, and that must match the bytes we keep.
                headers={
                    "User-Agent": "opendiscourse-research/0.1",
                    "Accept-Encoding": "identity",
                },
            )
        return self._http

    def _size(self, url: str, name: str) -> int:
        try:
            response = self._client().request("HEAD", url)
        except httpx.HTTPError as exc:
            raise RuntimeError(f"could not download {name}: {exc.__class__.__name__}") from None
        if response.status_code != 200:
            raise RuntimeError(f"could not download {name}: HTTP {response.status_code}")
        length = response.headers.get("content-length")
        if length is None or not length.isdigit():
            raise RuntimeError(f"capacity gate: size unavailable for {name}")
        return int(length)

    def _download(self, url: str, name: str, expected: int) -> bytes:
        try:
            response = self._client().get(url)
        except httpx.HTTPError as exc:
            raise RuntimeError(f"could not download {name}: {exc.__class__.__name__}") from None
        if response.status_code != 200:
            raise RuntimeError(f"could not download {name}: HTTP {response.status_code}")
        body = response.content
        if len(body) != expected:
            raise RuntimeError(
                f"{name}: downloaded {len(body)} bytes but the origin reports {expected}"
            )
        return body

    def _acquire_lock(self) -> None:
        """One sync at a time: two would race on the assignment snapshot."""
        conn = connect()
        conn.autocommit = True
        if not try_sync_lock(conn, LOCK_KEY):
            conn.close()
            raise RuntimeError(
                "another sync-committee-membership is in progress (it holds the database lock); "
                "wait for it to finish, then rerun"
            )
        self._lock = conn
