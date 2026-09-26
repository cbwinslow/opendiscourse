"""Connector for ``unitedstates/congress-legislators``: the BioGuide crosswalk.

Reads the legislator YAML files from the ``vendor/`` checkout, retains
verified copies as immutable artifacts, and promotes identifiers into
``core.person_identifier`` keyed on BioGuide only (Story 3.1), then promotes every term
into ``core.membership`` with its state or district post (Story 3.3). The same load
keeps biography, leadership, the Washington office on each term, social accounts,
and district offices.
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
from ..repositories.legislator_profile import publish_legislator_profile
from ..repositories.people import promote_legislators, promote_terms
from .base import IngestionRun
from .connector import ConnectorContext
from .legislator_profile import (
    district_offices,
    dump,
    entry_bioguide,
    load_yaml,
    odd_genders,
    person_facts,
    social_accounts,
)
from .legislator_terms import Term, parse_terms, plan_term

SOURCE_ID = "congress.legislators"
UPSTREAM = "https://raw.githubusercontent.com/unitedstates/congress-legislators"
UPSTREAM_REPO = "https://github.com/unitedstates/congress-legislators"
FILES = ("legislators-current.yaml", "legislators-historical.yaml")
PROFILE_FILES = ("legislators-social-media.yaml", "legislators-district-offices.yaml")
ALL_FILES = (*FILES, *PROFILE_FILES)
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
    terms: tuple[Term, ...] = ()


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
            Legislator(
                bioguide,
                full or bioguide,
                given,
                family,
                tuple(pairs),
                parse_terms(record.get("terms")),
            )
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
            p.terms,
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


def _commit_date(vendor: Path) -> str:
    """The checkout's commit date, used as the name-fact vintage."""
    committed = _git(vendor, "show", "-s", "--format=%cs", "HEAD")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", committed):
        raise RuntimeError(f"{vendor} commit date {committed!r} is not a calendar day")
    return committed


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
        self._records: dict[str, list[dict[str, Any]]] = {}
        self._social: list[dict[str, Any]] = []
        self._offices: list[dict[str, Any]] = []
        self._commit_date = ""
        self._shared: list[dict[str, Any]] = []
        self.result: dict[str, Any] = {}

    # -- stages -----------------------------------------------------------
    def discover(self, ctx: ConnectorContext) -> ConnectorContext:
        """Locate the checkout and pin the exact upstream commit."""
        missing = [n for n in ALL_FILES if not (self.vendor_dir / n).is_file()]
        if missing:
            raise FileNotFoundError(
                f"{', '.join(missing)} not found in {self.vendor_dir}. "
                "Run scripts/bootstrap_upstream.sh."
            )
        self._commit = verify_checkout(self.vendor_dir, self.expected_origin)
        self._commit_date = _commit_date(self.vendor_dir)
        self._run = IngestionRun(
            SOURCE_ID,
            {"commit": self._commit, "files": list(ALL_FILES), "vintage": self._commit_date},
            mode="backfill",
        )
        self._run.__enter__()
        ctx.run_id = str(self._run.run_id)
        self._report("discovered upstream checkout")
        return ctx

    def select(self, ctx: ConnectorContext) -> ConnectorContext:
        """Member files plus the current social and district-office files."""
        ctx.selected_ids = ALL_FILES
        self._report("selected files")
        return ctx

    def plan(self, ctx: ConnectorContext) -> ConnectorContext:
        """Sizes are known; retained copies are small so no capacity waiver is needed."""
        ctx.plan_id = f"{SOURCE_ID}@{self._commit[:12]}"
        ctx.artifact_urls = tuple(f"{UPSTREAM}/{self._commit}/{n}" for n in ALL_FILES)
        self._report("planned load")
        return ctx

    def extract(self, ctx: ConnectorContext) -> ConnectorContext:
        """Read each file once; the hash and the parsed content are the same bytes."""
        for name in ALL_FILES:
            content = (self.vendor_dir / name).read_bytes()
            self._content[name] = content
            self._checksums[name] = hashlib.sha256(content).hexdigest()
        ctx.checksums = tuple(self._checksums[n] for n in ALL_FILES)
        self._report("read files")
        return ctx

    def evidence(self, ctx: ConnectorContext) -> ConnectorContext:
        """Retain checksum-addressed copies and register artifact versions."""
        with connect() as conn:
            for name, url in zip(ALL_FILES, ctx.artifact_urls, strict=True):
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
        self._records = {n: load_yaml(self._content[n]) for n in ALL_FILES}
        self._people = {n: parse_legislators(self._content[n]) for n in FILES}
        self._social = self._records[PROFILE_FILES[0]]
        self._offices = self._records[PROFILE_FILES[1]]
        for name in FILES:
            for record in self._records[name]:
                person_facts(record, self._commit_date)
        for record in self._social:
            social_accounts(record)
        for record in self._offices:
            district_offices(record)
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
        term_rows, unknown = self._term_rows()
        with connect() as conn:
            counts = promote_legislators(conn, rows)
            conn.commit()
            terms = promote_terms(conn, term_rows)
            conn.commit()
            profile = publish_legislator_profile(conn, **self._profile_rows(ctx.run_id))
            conn.commit()
            for name, url in zip(ALL_FILES, ctx.artifact_urls, strict=True):
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
            **terms,
            **profile,
            "terms_unknown_jurisdiction": unknown,
            "profile_unexpected_genders": odd_genders(
                person_facts(record, self._commit_date)["gender"]
                for name in FILES
                for record in self._records[name]
            ),
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
            self._run.record_target(
                "core.membership",
                "all",
                inserted=terms["memberships_created"],
                updated=terms["memberships_updated"],
                skipped=terms["memberships_unchanged"],
                status="partial" if unknown or terms["terms_unresolved"] else "succeeded",
            )
        self._report("published")
        return ctx

    def _term_rows(self) -> tuple[list[tuple[Any, ...]], list[dict[str, Any]]]:
        """Stage rows for every term (evidence: the file it came from), and the unplaceable ones.

        A jurisdiction code outside the table is reported, never guessed.
        """
        rows: list[tuple[Any, ...]] = []
        unknown: list[dict[str, Any]] = []
        for name in FILES:
            for person in self._people[name]:
                for term in person.terms:
                    plan = plan_term(term)
                    if plan is None:
                        unknown.append(
                            {
                                "bioguide": person.bioguide,
                                "state": term.state,
                                "start": term.start.isoformat(),
                                "file": name,
                            }
                        )
                        continue
                    rows.append(
                        (
                            person.bioguide,
                            self._artifacts[name],
                            plan.chamber,
                            plan.role,
                            term.start,
                            term.end,
                            plan.state_ocd,
                            plan.state_label,
                            plan.state_class,
                            plan.post_ocd,
                            plan.post_division_label,
                            plan.post_division_class,
                            plan.post_label,
                            plan.post_role,
                            json.dumps(term.metadata, sort_keys=True),
                            json.dumps(term.contact, sort_keys=True),
                        )
                    )
        return rows, unknown

    def _profile_rows(self, run_id: Any) -> dict[str, list[tuple[Any, ...]]]:
        """Rows for the profile load. The safety copy is the file entry itself."""
        run = UUID(str(run_id))
        people: list[tuple[Any, ...]] = []
        leadership: list[tuple[Any, ...]] = []
        names: list[tuple[Any, ...]] = []
        sources: list[tuple[Any, ...]] = []
        for name in FILES:
            artifact = self._artifacts[name]
            for record in self._records[name]:
                bioguide = entry_bioguide(record, name)
                facts = person_facts(record, self._commit_date)
                people.append(
                    (bioguide, name, artifact, run, facts["birthday"], facts["gender"], dump(record))
                )
                sources.append((name, bioguide, bioguide, dump(record), artifact, run))
                for role in facts["leadership"]:
                    leadership.append(
                        (
                            bioguide,
                            role["chamber"],
                            role["title"],
                            role["start"],
                            role["end"],
                            artifact,
                            run,
                        )
                    )
                for fact in facts["names"]:
                    names.append(
                        (
                            bioguide,
                            fact["name_kind"],
                            fact["full_name"],
                            fact["given_name"],
                            fact["family_name"],
                            fact["source_vintage"],
                            artifact,
                            run,
                        )
                    )
        social_rows: list[tuple[Any, ...]] = []
        social_name = PROFILE_FILES[0]
        social_artifact = self._artifacts[social_name]
        for record in self._social:
            bioguide = entry_bioguide(record, social_name)
            sources.append((social_name, bioguide, bioguide, dump(record), social_artifact, run))
            for account in social_accounts(record):
                social_rows.append(
                    (
                        bioguide,
                        account["network"],
                        account["handle"],
                        account["external_id"],
                        social_artifact,
                        run,
                        dump(record),
                    )
                )
        office_rows: list[tuple[Any, ...]] = []
        office_name = PROFILE_FILES[1]
        office_artifact = self._artifacts[office_name]
        for record in self._offices:
            bioguide = entry_bioguide(record, office_name)
            for office in district_offices(record):
                sources.append(
                    (
                        office_name,
                        office["office_key"],
                        bioguide,
                        dump(office["record"]),
                        office_artifact,
                        run,
                    )
                )
                office_rows.append(
                    (
                        bioguide,
                        office["office_key"],
                        office["address"],
                        office["building"],
                        office["suite"],
                        office["city"],
                        office["state"],
                        office["zip"],
                        office["phone"],
                        office["fax"],
                        office["hours"],
                        office["latitude"],
                        office["longitude"],
                        office_artifact,
                        run,
                        dump(office["record"]),
                    )
                )
        return {
            "people": people,
            "leadership": leadership,
            "social": social_rows,
            "offices": office_rows,
            "names": names,
            "sources": sources,
        }

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
                self.result["conflicts"]
                or self._shared
                or self.result["terms_unknown_jurisdiction"]
                or self.result["terms_unresolved"]
                or self.result["profile_unknown_bioguides"]
                or self.result["profile_unexpected_genders"]
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
                    "terms_unknown_jurisdiction": self.result["terms_unknown_jurisdiction"],
                    "terms_unresolved": self.result["terms_unresolved"],
                },
                indent=2,
                sort_keys=True,
            )
            + "\n"
        )
        self.result["report"] = str(target)
