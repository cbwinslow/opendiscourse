"""Connector for House roll-call votes from the Clerk's official XML: download -> inventory -> ingest (Story 11.1).

Every roll call the Clerk lists for a Congress's two calendar years is one XML file. Each is fetched
from ``clerk.house.gov`` into ``DATA_ROOT`` as its own retained artifact (URL, size, checksum, the
server's ``Last-Modified``), then loaded: the whole record as JSON (``core.roll_call_source_record``),
the typed header and totals on ``core.roll_call``, and one ``fact.member_vote`` per member the file
names by BioGuide id. A roll call OpenStates already created under ``us-<year>-lower-<number>`` is
enriched in place, keeping its ``roll_call_id``. Nothing here reads a machine-specific path, and no
member is ever found by name: an unknown id is reported and the run is ``partial``.

Reruns are cheap and safe. A HEAD per file detects a refresh (size or ``Last-Modified``); an
unchanged, origin-verified file is not downloaded again, and a roll call with a record row for its
artifact version is not loaded again, so a killed run resumes where it stopped. A refreshed file is a
new artifact version whose rows replace the older version's in one transaction.
"""

from __future__ import annotations

import time
from collections import Counter, defaultdict
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

import httpx

from ..artifact_storage import validate_retained
from ..capacity import GiB, RemoteObject, storage_preview
from ..coverage import FIRST_CONGRESS, LAST_CONGRESS
from ..db import connect
from ..providers.clerk import (
    PACE_SECONDS,
    ClerkError,
    ClerkHouseVotes,
    ClerkNotFound,
    RemoteRoll,
)
from ..repositories.artifacts import current_artifacts
from ..repositories.legislation import ensure_us_legislative_session, register_artifact
from ..repositories.votes import (
    HOUSE_OCD_ORGANIZATION,
    bioguide_people,
    count_disagreements,
    house_organization_id,
    legislative_session_id,
    loaded_roll_records,
    older_artifact_ids,
    save_house_roll_call,
    try_sync_lock,
)
from .base import IngestionRun
from .bulk import ArtifactSpec, artifact_path, download
from .connector import ConnectorContext
from .house_vote_parse import parse_house_vote

SOURCE_ID = "congress.house_votes"
LOCK_KEY = f"{SOURCE_ID}:sync"
BATCH_SIZE = 50  # roll calls per transaction; each carries ~430 votes
# About 1.3 GB in all; keep a small floor instead of the 100 GiB default.
CAPACITY_RESERVE_BYTES = 10 * GiB
DISAGREEMENT_EXAMPLES = 20
UNRESOLVED_EXAMPLES = 5

Downloader = Callable[..., Path]


def congress_years(congress: int) -> tuple[int, int]:
    """The two calendar years a Congress sits in (108th = 2003 and 2004)."""
    first = 1789 + 2 * (congress - 1)
    return first, first + 1


def artifact_key(year: int, number: int) -> str:
    """Registry key of one roll-call file."""
    return f"house-roll-{year}-{number:03d}.xml"


@dataclass
class _Roll:
    """One roll-call file as it moves through the stages."""

    remote: RemoteRoll
    congress: int
    action: str = "reuse"  # or "download"
    reason: str = ""
    artifact: dict[str, Any] | None = None
    usable: bool = True  # False once a download or the registry check failed
    todo: bool = False

    @property
    def key(self) -> str:
        return artifact_key(self.remote.year, self.remote.number)


def _origin_state(remote: RemoteRoll, congress: int) -> dict[str, Any]:
    return {
        "origin": "clerk.house.gov",
        "congress": congress,
        "year": remote.year,
        "roll_number": remote.number,
        "remote_size": remote.size,
        "remote_last_modified": remote.last_modified,
    }


def _matches_origin(metadata: dict[str, Any] | None, remote: RemoteRoll) -> bool:
    meta = metadata or {}
    return (
        meta.get("remote_size") == remote.size
        and meta.get("remote_last_modified") == remote.last_modified
    )


class HouseVotesConnector:
    """Ten-stage Connector. Roll calls load in batched transactions and resume by record row."""

    source_id = SOURCE_ID

    def __init__(
        self,
        congresses: Sequence[int] | None = None,
        *,
        clerk: ClerkHouseVotes | None = None,
        downloader: Downloader = download,
        batch_size: int = BATCH_SIZE,
        download_only: bool = False,
        report: Callable[[str], None] | None = None,
        sleep: Callable[[float], None] = time.sleep,
        download_pace_seconds: float = PACE_SECONDS,
    ) -> None:
        if batch_size < 1:
            raise ValueError("batch_size must be positive")
        wanted = tuple(sorted(set(congresses))) if congresses else tuple(
            range(FIRST_CONGRESS, LAST_CONGRESS + 1)
        )
        bad = [c for c in wanted if not FIRST_CONGRESS <= c <= LAST_CONGRESS]
        if bad:
            raise ValueError(
                f"House votes are supported for Congresses {FIRST_CONGRESS}-{LAST_CONGRESS}; not {bad}"
            )
        self.congresses = wanted
        self.batch_size = batch_size
        self.download_only = download_only
        self._clerk = clerk or ClerkHouseVotes(pace_seconds=download_pace_seconds)
        self._download = downloader
        self._report = report or (lambda phase: None)
        self._sleep = sleep
        self._pace = download_pace_seconds
        self._run: IngestionRun | None = None
        self._lock: Any = None
        self._listing: dict[int, list[int]] = {}
        self._rolls: list[_Roll] = []
        self._finished = False
        self._partial = False
        self._not_published: list[str] = []
        self._problems: list[str] = []
        self._failed: dict[str, str] = {}
        self._malformed: list[str] = []
        self._unresolved: dict[str, list[str]] = {}
        self._unlisted: dict[int, list[int]] = {}
        self._notes: dict[str, list[str]] = {}
        self._disagreements: list[dict[str, Any]] = []
        self.result: dict[str, Any] = {}

    # -- stages -----------------------------------------------------------
    def discover(self, ctx: ConnectorContext) -> ConnectorContext:
        """Ask the Clerk which roll numbers it lists for each calendar year."""
        self._acquire_lock()
        self._run = IngestionRun(
            SOURCE_ID,
            {"congresses": list(self.congresses), "chamber": "house", "download_only": self.download_only},
            mode="backfill",
        )
        self._run.__enter__()
        ctx.run_id = str(self._run.run_id)
        for congress in self.congresses:
            for year in congress_years(congress):
                self._report(f"listing House roll calls: {year}")
                numbers = self._clerk.roll_numbers(year)
                self._listing[year] = numbers
                # Roll numbers run 1..max without gaps, so a hole means a truncated listing page.
                if gaps := sorted(set(range(1, numbers[-1] + 1)) - set(numbers) if numbers else ()):
                    self._unlisted[year] = gaps
        ctx.extras["congresses"] = list(self.congresses)
        return ctx

    def select(self, ctx: ConnectorContext) -> ConnectorContext:
        """HEAD every listed file, then download only what is new or changed at the origin."""
        current = current_artifacts(SOURCE_ID)
        for congress in self.congresses:
            for year in congress_years(congress):
                numbers = self._listing[year]
                for position, number in enumerate(numbers, 1):
                    if position % 50 == 0 or position == len(numbers):
                        self._report(f"checking origin: {year} {position}/{len(numbers)}")
                    key = artifact_key(year, number)
                    try:
                        remote = self._clerk.roll_info(year, number)
                    except ClerkNotFound:
                        # Listed by the index but not served (a vacated or withdrawn roll): the origin's
                        # state, not a failure. Listed in the result so nothing is silently absent.
                        self._not_published.append(key)
                        continue
                    except ClerkError as exc:
                        self._failed[key] = str(exc)
                        continue
                    roll = _Roll(remote, congress)
                    roll.action, roll.reason = self._decide(roll, current.get(key))
                    self._rolls.append(roll)
        ctx.selected_ids = tuple(r.key for r in self._rolls)
        self._report(
            f"selected {sum(r.action == 'download' for r in self._rolls)} of {len(self._rolls)} files to download"
        )
        return ctx

    def plan(self, ctx: ConnectorContext) -> ConnectorContext:
        """Capacity gate on the bytes to fetch; unknown or excessive size stops the run."""
        downloads = [r for r in self._rolls if r.action == "download"]
        ctx.plan_id = f"{SOURCE_ID}:{self.congresses[0]}-{self.congresses[-1]}"
        ctx.artifact_urls = tuple(r.remote.url for r in downloads)
        if downloads:
            preview = storage_preview(
                [RemoteObject(r.remote.url, r.remote.size, "head") for r in downloads],
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
        """Download each selected file into ``DATA_ROOT``; one failure is reported, not fatal."""
        downloads = [r for r in self._rolls if r.action == "download"]
        for position, roll in enumerate(downloads):
            if position:
                self._sleep(self._pace)
            if position % 25 == 0 or position + 1 == len(downloads):
                self._report(f"downloading ({position + 1}/{len(downloads)}): {roll.key}")
            spec = ArtifactSpec(
                dataset_id=SOURCE_ID,
                artifact_key=roll.key,
                url=roll.remote.url,
                filename=f"{roll.remote.year}/roll{roll.remote.number:03d}.xml",
                metadata={**_origin_state(roll.remote, roll.congress), "run_id": ctx.run_id},
            )
            # A partial from before the file changed must never be resumed onto new bytes. Files are
            # small, so a fresh fetch costs nothing.
            target = artifact_path(spec)
            target.with_suffix(".xml.part").unlink(missing_ok=True)
            try:
                path = self._download(spec, overwrite=True)
                got = Path(path).stat().st_size
                if got != roll.remote.size:
                    raise RuntimeError(
                        f"downloaded {got} bytes but the Clerk reports {roll.remote.size}"
                    )
            except (httpx.HTTPError, OSError, ValueError, RuntimeError) as exc:
                # The next run's origin check sees the missing or wrong bytes and fetches it again.
                roll.usable = False
                self._failed[roll.key] = str(exc)
            finally:
                # ``download`` leaves an empty lock file beside every artifact; with one sync at a time
                # (the advisory lock) it guards nothing, and 16,000 of them would clutter the evidence folder.
                target.with_suffix(".xml.lock").unlink(missing_ok=True)
        return ctx

    def evidence(self, ctx: ConnectorContext) -> ConnectorContext:
        """Confirm the registry holds origin-verified, checksummed bytes for every usable file."""
        current = current_artifacts(SOURCE_ID)
        checksums = []
        for roll in self._rolls:
            if not roll.usable:
                continue
            row = current.get(roll.key)
            if (
                row is None
                or not row["checksum_sha256"]
                or not _matches_origin(row["metadata"], roll.remote)
            ):
                roll.usable = False
                self._failed[roll.key] = "the artifact registry does not hold bytes verified against the origin"
                continue
            roll.artifact = row
            checksums.append(row["checksum_sha256"])
        ctx.checksums = tuple(checksums)
        self._report("inventoried artifacts")
        return ctx

    def stage(self, ctx: ConnectorContext) -> ConnectorContext:
        """Compare what the Clerk lists with what it serves, per calendar year."""
        served = Counter(r.remote.year for r in self._rolls)
        ctx.extras["years"] = {
            year: {"listed": len(numbers), "served": served[year]}
            for year, numbers in self._listing.items()
        }
        return ctx

    def normalize(self, ctx: ConnectorContext) -> ConnectorContext:
        """Work out what is left to load: files with no record row for this artifact version.

        The record row is written last in a roll call's transaction, so a file without one is not
        fully loaded. A file whose record still lists BioGuide ids we could not resolve is tried
        again: the person may have been loaded since.
        """
        if self.download_only:
            return ctx
        usable = [r for r in self._rolls if r.usable and r.artifact is not None]
        done: dict[str, list[str]] = {}
        with connect() as conn:
            ids = [str(r.artifact["artifact_id"]) for r in usable]  # type: ignore[index]
            for start in range(0, len(ids), 5000):
                done.update(loaded_roll_records(conn, ids[start : start + 5000]))
        for roll in usable:
            assert roll.artifact is not None
            key = str(roll.artifact["artifact_id"])
            roll.todo = key not in done or bool(done[key])
        self._report(f"{sum(r.todo for r in usable)} roll calls left to load")
        return ctx

    def validate(self, ctx: ConnectorContext) -> ConnectorContext:
        """Refuse a run whose files do not belong to the Congresses asked for."""
        wrong = [
            r.key
            for r in self._rolls
            if r.congress not in self.congresses or r.remote.year not in congress_years(r.congress)
        ]
        if wrong:
            raise ValueError(f"files outside the requested Congresses: {wrong[:3]}")
        self._partial = bool(self._failed) or bool(self._unlisted)
        self._report("validated")
        return ctx

    def publish(self, ctx: ConnectorContext) -> ConnectorContext:
        """Load each Congress's remaining roll calls in batched transactions."""
        totals: Counter[str] = Counter()
        per_congress: dict[int, Counter[str]] = defaultdict(Counter)
        loading = {c: [r for r in self._rolls if r.congress == c and r.todo] for c in self.congresses}
        left = {c: len(rolls) for c, rolls in loading.items()}

        def record(congress: int) -> None:
            """Write the Congress's running totals; only a finished, clean Congress is 'succeeded'."""
            if self._run is None:
                return
            slice_ = per_congress[congress]
            years = tuple(f"house-roll-{y}-" for y in congress_years(congress))
            problems = (
                left[congress] > 0
                or slice_["malformed"]
                or slice_["unresolved"]
                or any(key.startswith(years) for key in self._failed)
                or any(year in self._unlisted for year in congress_years(congress))
            )
            status = "partial" if problems else "succeeded"
            self._run.record_target(
                "core.roll_call",
                f"congress={congress}",
                inserted=slice_["inserted"],
                updated=slice_["enriched"] + slice_["refreshed"],
                skipped=slice_["skipped"],
                status=status,
            )
            self._run.record_target(
                "fact.member_vote", f"congress={congress}", inserted=slice_["votes"], status=status
            )

        if not self.download_only:
            with connect() as conn:
                people = bioguide_people(conn)
                organization_id = house_organization_id(conn)
            if organization_id is None:
                self._problems.append(
                    f"the House organization (ocd identifier {HOUSE_OCD_ORGANIZATION}) is not in the "
                    "warehouse; new roll calls are loaded without an organization"
                )
            self._settle(ctx)
            for congress in self.congresses:
                usable = [r for r in self._rolls if r.congress == congress and r.usable]
                per_congress[congress]["skipped"] += len(usable) - len(loading[congress])
                self._load_congress(
                    congress, loading[congress], ctx, people, organization_id, totals, per_congress, left, record
                )
                record(congress)
        self._partial = (
            self._partial
            or bool(self._malformed)
            or bool(self._unresolved)
            or bool(self._failed)
            or bool(self._unlisted)
        )
        self._finished = True
        self.result = {
            "chamber": "house",
            "congresses": list(self.congresses),
            "files_listed": sum(len(n) for n in self._listing.values()),
            "files_served": len(self._rolls),
            "downloaded": sum(r.action == "download" and r.usable for r in self._rolls),
            "reused": sum(r.action == "reuse" for r in self._rolls),
            "bytes_downloaded": sum(
                r.remote.size for r in self._rolls if r.action == "download" and r.usable
            ),
            "download_only": self.download_only,
            "roll_calls_loaded": totals["loaded"],
            "roll_calls_inserted": totals["inserted"],
            "roll_calls_enriched_from_openstates": totals["enriched"],
            "roll_calls_refreshed": totals["refreshed"],
            "member_votes_written": totals["votes"],
            "entries_without_bioguide_id": totals["without_id"],
            "unresolved_bioguide_ids": {
                bioguide: rolls for bioguide, rolls in sorted(self._unresolved.items())
            },
            "count_disagreements": len(self._disagreements),
            "count_disagreement_examples": self._disagreements[:DISAGREEMENT_EXAMPLES],
            "not_published": self._not_published,
            "failed": self._failed,
            "malformed": self._malformed,
            "unlisted": {year: gaps[:50] for year, gaps in sorted(self._unlisted.items())},
            "parse_problems": {
                kind: {"count": len(keys), "examples": keys[:5]} for kind, keys in sorted(self._notes.items())
            },
            "problems": [
                f"{kind}: {len(keys)} roll call(s) loaded with that field empty (first: {keys[0]})"
                for kind, keys in sorted(self._notes.items())
            ]
            + self._problems[:20],
            "partial": self._partial,
            "years": ctx.extras.get("years", {}),
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
        """One sync at a time: two would race on artifact versions and on the same roll calls."""
        conn = connect()
        conn.autocommit = True  # never sit idle in a transaction for the length of a sync
        if not try_sync_lock(conn, LOCK_KEY):
            conn.close()
            raise RuntimeError(
                "another sync-votes run is in progress (it holds the database lock); "
                "wait for it to finish, then rerun"
            )
        self._lock = conn

    def _settle(self, ctx: ConnectorContext) -> None:
        """Mark loaded the files that are fully loaded but re-registered as downloaded.

        Same bytes under a new ``Last-Modified`` are re-registered on the same version; nothing is
        reloaded, but the registry should not say the roll call is merely downloaded.
        """
        stale = [r for r in self._rolls if r.usable and not r.todo and r.artifact and r.artifact["status"] != "loaded"]
        if not stale:
            return
        with connect() as conn:
            for roll in stale:
                assert roll.artifact is not None
                self._mark_loaded(conn, roll, roll.artifact, ctx)
            conn.commit()

    @staticmethod
    def _mark_loaded(conn: Any, roll: _Roll, artifact: dict[str, Any], ctx: ConnectorContext) -> None:
        register_artifact(
            SOURCE_ID,
            roll.remote.url,
            artifact["local_path"],
            roll.key,
            status="loaded",
            checksum_sha256=artifact["checksum_sha256"],
            bytes_downloaded=roll.remote.size,
            content_type="text/xml",
            metadata={"run_id": ctx.run_id},
            conn=conn,
        )

    @staticmethod
    def _decide(roll: _Roll, row: dict[str, Any] | None) -> tuple[str, str]:
        if row is None or not row["checksum_sha256"]:
            return "download", "not downloaded yet"
        try:
            validate_retained(row["local_path"], row["checksum_sha256"])
        except (ValueError, OSError):
            return "download", "retained file missing or damaged"
        meta = row["metadata"] or {}
        if "remote_size" not in meta:
            return "download", "not yet verified against the origin"
        if not _matches_origin(meta, roll.remote):
            return "download", "changed at the origin"
        if Path(row["local_path"]).stat().st_size != roll.remote.size:
            return "download", "retained size differs from the origin"
        return "reuse", "unchanged at the origin"

    def _load_congress(
        self,
        congress: int,
        rolls: list[_Roll],
        ctx: ConnectorContext,
        people: dict[str, str],
        organization_id: str | None,
        totals: Counter[str],
        per_congress: dict[int, Counter[str]],
        left: dict[int, int],
        record: Callable[[int], None],
    ) -> None:
        """Load one Congress's remaining roll calls; ``record`` follows every batch commit."""
        if not rolls:
            return
        with connect() as conn:
            session_id = legislative_session_id(conn, congress)
            if session_id is None:
                first = rolls[0].artifact
                assert first is not None
                session_id = ensure_us_legislative_session(
                    congress,
                    source_artifact_id=str(first["artifact_id"]),
                    metadata={"congress": congress},
                    conn=conn,
                )
                conn.commit()
            for start in range(0, len(rolls), self.batch_size):
                batch = rolls[start : start + self.batch_size]
                ids: list[str] = []
                gained: Counter[str] = Counter()
                for roll in batch:
                    saved = self._load_roll(conn, roll, ctx, session_id, organization_id, people)
                    if saved is None:
                        gained["malformed"] += 1
                        continue
                    ids.append(saved["roll_call_id"])
                    gained["loaded"] += 1
                    gained["votes"] += saved["typed"]
                    gained["without_id"] += saved["entries_without_id"]
                    if saved["inserted"]:
                        gained["inserted"] += 1
                    elif saved["enriched"]:
                        gained["enriched"] += 1
                    else:
                        gained["refreshed"] += 1
                    if saved["unresolved"]:
                        gained["unresolved"] += 1
                        for bioguide in saved["unresolved"]:
                            examples = self._unresolved.setdefault(bioguide, [])
                            if len(examples) < UNRESOLVED_EXAMPLES:
                                examples.append(roll.key)
                for row in count_disagreements(conn, ids):
                    self._disagreements.append(
                        {
                            "roll": row["external_id"],
                            "official": [row["yea_total"], row["nay_total"], row["not_voting_total"]],
                            "stored": [row["yes_votes"], row["no_votes"], row["not_voting_votes"]],
                        }
                    )
                conn.commit()
                totals.update(gained)
                per_congress[congress].update(gained)
                left[congress] -= len(batch)
                if self._run is not None:
                    self._run.record_count += gained["loaded"]
                record(congress)
                self._report(f"loading {congress}: {min(start + self.batch_size, len(rolls))}/{len(rolls)} roll calls")

    def _load_roll(
        self,
        conn: Any,
        roll: _Roll,
        ctx: ConnectorContext,
        session_id: str | None,
        organization_id: str | None,
        people: dict[str, str],
    ) -> dict[str, Any] | None:
        """Parse and save one file in the batch's transaction; None (nothing written) if unusable."""
        artifact = roll.artifact
        assert artifact is not None
        try:
            parsed = parse_house_vote(Path(artifact["local_path"]).read_bytes())
        except (ElementTree.ParseError, ValueError, OSError) as exc:
            self._malformed.append(roll.key)
            self._problems.append(f"{roll.key}: unreadable ({exc})")
            return None
        found = (parsed.roll["congress"], parsed.roll["roll_number"])
        if found != (roll.congress, roll.remote.number):
            # Which roll call this is can no longer be trusted: write nothing for it, report it.
            self._malformed.append(roll.key)
            self._problems.append(
                f"{roll.key} describes Congress {found[0]} roll {found[1]}, not the roll call its name promises"
            )
            return None
        for note in parsed.notes:
            keys = self._notes.setdefault(note, [])
            if roll.key not in keys:
                keys.append(roll.key)
        artifact_id = str(artifact["artifact_id"])
        older = older_artifact_ids(conn, artifact_id) if artifact["artifact_version"] > 1 else []
        saved = save_house_roll_call(
            conn,
            parsed,
            year=roll.remote.year,
            artifact_id=artifact_id,
            session_id=session_id,
            organization_id=organization_id,
            people=people,
            older_versions=older,
        )
        if artifact["status"] != "loaded":
            self._mark_loaded(conn, roll, artifact, ctx)
        return saved
