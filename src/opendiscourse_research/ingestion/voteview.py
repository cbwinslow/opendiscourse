"""Connector for Voteview ideology scores and the roll-call index.

Downloads the current all-Congress member, roll-call, and party files from
voteview.com into ``DATA_ROOT``, keeps each file as evidence, and loads one
row per member-Congress, one row per roll call, and one row per party. People link on an ICPSR that already belongs to exactly one person. When that
number is missing and the row's BioGuide matches exactly one person who has no
ICPSR yet, the row links and that ICPSR is stored. A conflicting number is not
overwritten, and no person is created. Official votes are linked and never
rewritten. The individual-vote file is not downloaded, and
``vendor/unitedstates-congress`` task ``voteview`` is not run.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from ..artifact_storage import retain_artifact_bytes, retained_path, validate_retained
from ..capacity import GiB, RemoteObject, storage_preview
from ..config import settings
from ..db import connect
from ..providers.voteview import (
    FILES,
    MEMBERS,
    ORIGIN,
    PARTIES,
    ROLLCALLS,
    VoteviewClient,
)
from ..repositories.artifacts import get_current_artifact
from ..repositories.legislation import register_artifact
from ..repositories.voteview import publish_voteview, stored_counts, try_sync_lock
from .base import IngestionRun
from .connector import ConnectorContext

SOURCE_ID = "congress.voteview"
LOCK_KEY = f"{SOURCE_ID}:sync"
# Bumped when member linking changes. A retained file is reloaded once so an
# existing database picks up the new rule without a second download.
LINK_RULE = "bioguide-if-no-icpsr"
CITATION = (
    "Lewis, Poole, Rosenthal, Boche, Rudkin, and Sonnet, "
    "Voteview: Congressional Roll-Call Votes Database, https://voteview.com/"
)
CAPACITY_RESERVE_BYTES = GiB
_CONTENT_TYPE = {
    MEMBERS: "text/csv",
    PARTIES: "text/csv",
    ROLLCALLS: "application/json",
}
_CHAMBERS = {"House": "house", "Senate": "senate", "President": "president"}
_ROLL_CHAMBERS = {"House": "house", "Senate": "senate"}
_MEMBER_FIELDS = (
    "congress",
    "chamber",
    "icpsr",
    "state_icpsr",
    "district_code",
    "state_abbrev",
    "party_code",
    "occupancy",
    "last_means",
    "bioname",
    "bioguide_id",
    "born",
    "died",
    "nominate_dim1",
    "nominate_dim2",
    "nominate_log_likelihood",
    "nominate_geo_mean_probability",
    "nominate_number_of_votes",
    "nominate_number_of_errors",
    "conditional",
    "nokken_poole_dim1",
    "nokken_poole_dim2",
)
_PARTY_FIELDS = (
    "congress",
    "chamber",
    "party_code",
    "party_name",
    "n_members",
    "nominate_dim1_median",
    "nominate_dim2_median",
    "nominate_dim1_mean",
    "nominate_dim2_mean",
)
_ROLL_FIELDS = (
    "congress",
    "chamber",
    "rollnumber",
    "date",
    "session",
    "clerk_rollnumber",
    "majority_requirement",
    "yea_count",
    "nay_count",
    "nominate_mid_1",
    "nominate_mid_2",
    "nominate_spread_1",
    "nominate_spread_2",
    "nominate_log_likelihood",
    "bill_number",
    "vote_result",
    "vote_desc",
    "vote_question",
    "dtl_desc",
    "issue_codes",
    "peltzman_codes",
    "clausen_codes",
    "crs_policy_area",
    "crs_subjects",
    "congress_url",
    "source_documents",
)
_ZERO_COUNTS = {
    "members_inserted": 0,
    "members_deleted": 0,
    "roll_calls_inserted": 0,
    "roll_calls_deleted": 0,
    "parties_inserted": 0,
    "parties_deleted": 0,
    "names_inserted": 0,
    "names_updated": 0,
    "names_deleted": 0,
}


def _missing(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _text(value: Any, where: str, *, required: bool) -> str | None:
    if _missing(value):
        if required:
            raise ValueError(f"{where} is missing")
        return None
    if not isinstance(value, str):
        raise ValueError(f"{where} must be text")
    cleaned = value.strip()
    if required and not cleaned:
        raise ValueError(f"{where} is blank")
    return cleaned or None


def _whole(value: Any, where: str, *, required: bool) -> int | None:
    """An integer, including a whole number Voteview wrote as ``1.0``.

    The member and party CSVs store some codes with a trailing ``.0``. A
    fraction such as ``1.5`` is still refused.
    """
    if _missing(value):
        if required:
            raise ValueError(f"{where} is missing")
        return None
    if isinstance(value, bool):
        raise ValueError(f"{where} must be an integer")
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if value.is_integer():
            return int(value)
        raise ValueError(f"{where} must be an integer")
    if isinstance(value, str):
        text = value.strip()
        whole, dot, fraction = text.partition(".")
        if dot and fraction.strip("0") == "" and whole.lstrip("-").isdigit() and whole not in {"", "-"}:
            return int(whole)
        if not dot and whole.lstrip("-").isdigit() and whole not in {"", "-"}:
            return int(whole)
    raise ValueError(f"{where} must be an integer")


def _real(value: Any, where: str) -> float | None:
    if _missing(value):
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise ValueError(f"{where} must be a number")
    try:
        return float(value.strip() if isinstance(value, str) else value)
    except ValueError as exc:
        raise ValueError(f"{where} must be a number") from exc


def _json_value(value: Any, where: str) -> Any:
    if value is None or isinstance(value, (str, int, float, bool, list, dict)):
        return value
    raise ValueError(f"{where} is not a JSON value")


def _chamber(value: Any, where: str, allowed: Mapping[str, str]) -> str:
    if not isinstance(value, str) or value not in allowed:
        names = ", ".join(allowed)
        raise ValueError(f"{where} chamber must be one of {names}")
    return allowed[value]


def _positive(value: int | None, where: str) -> int:
    if value is None or value <= 0:
        raise ValueError(f"{where} must be a positive integer")
    return value


def _csv_rows(name: str, content: bytes, fields: tuple[str, ...]) -> list[dict[str, str]]:
    try:
        text = content.decode("utf-8")
    except UnicodeError as exc:
        raise ValueError(f"{name} is not UTF-8") from exc
    reader = csv.DictReader(io.StringIO(text))
    header = reader.fieldnames or []
    if len(header) != len(set(header)):
        raise ValueError(f"{name} repeats a column")
    missing = [field for field in fields if field not in header]
    if missing:
        raise ValueError(f"{name} is missing {', '.join(missing)}")
    rows = list(reader)
    if not rows:
        raise ValueError(f"{name} has no rows")
    return rows


def _json_rows(name: str, content: bytes) -> list[dict[str, Any]]:
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        keys = [key for key, _ in items]
        if len(keys) != len(set(keys)):
            raise ValueError(f"{name} repeats a key")
        return dict(items)

    try:
        document = json.loads(content.decode("utf-8"), object_pairs_hook=pairs)
    except UnicodeError as exc:
        raise ValueError(f"{name} is not UTF-8") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"{name} is not valid JSON") from exc
    if not isinstance(document, list) or not document:
        raise ValueError(f"{name} must be a non-empty JSON list")
    rows: list[dict[str, Any]] = []
    for index, row in enumerate(document, start=1):
        if not isinstance(row, dict):
            raise ValueError(f"{name} row {index} is not an object")
        rows.append(row)
    return rows


def _remember(seen: set[tuple[Any, ...]], key: tuple[Any, ...], where: str) -> None:
    if key in seen:
        raise ValueError(f"{where} repeats {key}")
    seen.add(key)


def parse_members(content: bytes) -> list[dict[str, Any]]:
    """One row per Congress, chamber, and ICPSR. The CSV row is kept whole."""
    seen: set[tuple[Any, ...]] = set()
    parsed: list[dict[str, Any]] = []
    for index, row in enumerate(_csv_rows(MEMBERS, content, _MEMBER_FIELDS), start=1):
        where = f"{MEMBERS} row {index}"
        congress = _positive(_whole(row["congress"], f"{where} congress", required=True), where)
        chamber = _chamber(row["chamber"], where, _CHAMBERS)
        icpsr = str(_positive(_whole(row["icpsr"], f"{where} icpsr", required=True), f"{where} icpsr"))
        _remember(seen, (congress, chamber, icpsr), where)
        bioname = _text(row["bioname"], f"{where} bioname", required=True)
        parsed.append(
            {
                "congress": congress,
                "chamber": chamber,
                "icpsr": icpsr,
                "state_icpsr": _whole(row["state_icpsr"], f"{where} state_icpsr", required=False),
                "district_code": _whole(row["district_code"], f"{where} district_code", required=False),
                "state_abbrev": _text(row["state_abbrev"], f"{where} state_abbrev", required=False),
                "party_code": _whole(row["party_code"], f"{where} party_code", required=True),
                "occupancy": _whole(row["occupancy"], f"{where} occupancy", required=False),
                "last_means": _whole(row["last_means"], f"{where} last_means", required=False),
                "bioname": bioname,
                "bioguide": _text(row["bioguide_id"], f"{where} bioguide_id", required=False),
                "born": _real(row["born"], f"{where} born"),
                "died": _real(row["died"], f"{where} died"),
                "nominate_dim1": _real(row["nominate_dim1"], f"{where} nominate_dim1"),
                "nominate_dim2": _real(row["nominate_dim2"], f"{where} nominate_dim2"),
                "nominate_log_likelihood": _real(
                    row["nominate_log_likelihood"], f"{where} nominate_log_likelihood"
                ),
                "nominate_geo_mean_probability": _real(
                    row["nominate_geo_mean_probability"], f"{where} nominate_geo_mean_probability"
                ),
                "nominate_number_of_votes": _whole(
                    row["nominate_number_of_votes"], f"{where} nominate_number_of_votes", required=False
                ),
                "nominate_number_of_errors": _whole(
                    row["nominate_number_of_errors"],
                    f"{where} nominate_number_of_errors",
                    required=False,
                ),
                "conditional": _text(row["conditional"], f"{where} conditional", required=False),
                "nokken_poole_dim1": _real(row["nokken_poole_dim1"], f"{where} nokken_poole_dim1"),
                "nokken_poole_dim2": _real(row["nokken_poole_dim2"], f"{where} nokken_poole_dim2"),
                "record": dict(row),
            }
        )
    return parsed


def parse_parties(content: bytes) -> list[dict[str, Any]]:
    """One row per Congress, chamber, and party code. The CSV row is kept whole."""
    seen: set[tuple[Any, ...]] = set()
    parsed: list[dict[str, Any]] = []
    for index, row in enumerate(_csv_rows(PARTIES, content, _PARTY_FIELDS), start=1):
        where = f"{PARTIES} row {index}"
        congress = _positive(_whole(row["congress"], f"{where} congress", required=True), where)
        chamber = _chamber(row["chamber"], where, _CHAMBERS)
        party_code = _whole(row["party_code"], f"{where} party_code", required=True)
        if party_code is None:
            raise ValueError(f"{where} party_code is missing")
        _remember(seen, (congress, chamber, party_code), where)
        parsed.append(
            {
                "congress": congress,
                "chamber": chamber,
                "party_code": party_code,
                "party_name": _text(row["party_name"], f"{where} party_name", required=True),
                "n_members": _whole(row["n_members"], f"{where} n_members", required=False),
                "nominate_dim1_median": _real(
                    row["nominate_dim1_median"], f"{where} nominate_dim1_median"
                ),
                "nominate_dim2_median": _real(
                    row["nominate_dim2_median"], f"{where} nominate_dim2_median"
                ),
                "nominate_dim1_mean": _real(row["nominate_dim1_mean"], f"{where} nominate_dim1_mean"),
                "nominate_dim2_mean": _real(row["nominate_dim2_mean"], f"{where} nominate_dim2_mean"),
                "record": dict(row),
            }
        )
    return parsed


def _roll_date(value: Any, where: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or len(value) != 10 or value[4] != "-" or value[7] != "-":
        raise ValueError(f"{where} date must be YYYY-MM-DD")
    return value


def parse_roll_calls(content: bytes) -> list[dict[str, Any]]:
    """One row per Congress, chamber, and Voteview roll number. The JSON object is kept whole."""
    seen: set[tuple[Any, ...]] = set()
    parsed: list[dict[str, Any]] = []
    for index, row in enumerate(_json_rows(ROLLCALLS, content), start=1):
        where = f"{ROLLCALLS} row {index}"
        missing = [field for field in _ROLL_FIELDS if field not in row]
        if missing:
            raise ValueError(f"{where} is missing {', '.join(missing)}")
        congress = _positive(_whole(row["congress"], f"{where} congress", required=True), where)
        chamber = _chamber(row["chamber"], where, _ROLL_CHAMBERS)
        rollnumber = _positive(
            _whole(row["rollnumber"], f"{where} rollnumber", required=True), f"{where} rollnumber"
        )
        _remember(seen, (congress, chamber, rollnumber), where)
        parsed.append(
            {
                "congress": congress,
                "chamber": chamber,
                "rollnumber": rollnumber,
                "session": _whole(row["session"], f"{where} session", required=False),
                "clerk_rollnumber": _whole(
                    row["clerk_rollnumber"], f"{where} clerk_rollnumber", required=False
                ),
                "vote_date": _roll_date(row["date"], where),
                "majority_requirement": _text(
                    row["majority_requirement"], f"{where} majority_requirement", required=False
                ),
                "yea_count": _whole(row["yea_count"], f"{where} yea_count", required=False),
                "nay_count": _whole(row["nay_count"], f"{where} nay_count", required=False),
                "nominate_mid_1": _real(row["nominate_mid_1"], f"{where} nominate_mid_1"),
                "nominate_mid_2": _real(row["nominate_mid_2"], f"{where} nominate_mid_2"),
                "nominate_spread_1": _real(row["nominate_spread_1"], f"{where} nominate_spread_1"),
                "nominate_spread_2": _real(row["nominate_spread_2"], f"{where} nominate_spread_2"),
                "nominate_log_likelihood": _real(
                    row["nominate_log_likelihood"], f"{where} nominate_log_likelihood"
                ),
                "bill_number": _text(row["bill_number"], f"{where} bill_number", required=False),
                "vote_result": _text(row["vote_result"], f"{where} vote_result", required=False),
                "vote_desc": _text(row["vote_desc"], f"{where} vote_desc", required=False),
                "vote_question": _text(row["vote_question"], f"{where} vote_question", required=False),
                "dtl_desc": _text(row["dtl_desc"], f"{where} dtl_desc", required=False),
                "issue_codes": _json_value(row["issue_codes"], f"{where} issue_codes"),
                "peltzman_codes": _json_value(row["peltzman_codes"], f"{where} peltzman_codes"),
                "clausen_codes": _json_value(row["clausen_codes"], f"{where} clausen_codes"),
                "crs_policy_area": _text(
                    row["crs_policy_area"], f"{where} crs_policy_area", required=False
                ),
                "crs_subjects": _json_value(row["crs_subjects"], f"{where} crs_subjects"),
                "congress_url": _text(row["congress_url"], f"{where} congress_url", required=False),
                "source_documents": _json_value(
                    row["source_documents"], f"{where} source_documents"
                ),
                "record": row,
            }
        )
    return parsed


def parse_voteview_files(contents: Mapping[str, bytes]) -> dict[str, list[dict[str, Any]]]:
    """Validate whichever of the three files are present. Raises before any database write."""
    unknown = [name for name in contents if name not in FILES]
    if unknown:
        raise ValueError(f"refusing Voteview file(s): {', '.join(unknown)}")
    parsed: dict[str, list[dict[str, Any]]] = {}
    if MEMBERS in contents:
        parsed[MEMBERS] = parse_members(contents[MEMBERS])
    if ROLLCALLS in contents:
        parsed[ROLLCALLS] = parse_roll_calls(contents[ROLLCALLS])
    if PARTIES in contents:
        parsed[PARTIES] = parse_parties(contents[PARTIES])
    return parsed


class VoteviewConnector:
    """Ten-stage Connector. A changed file replaces its rows in one transaction."""

    source_id = SOURCE_ID

    def __init__(
        self,
        *,
        origin: str = ORIGIN,
        http: Any = None,
        report: Callable[[str], None] | None = None,
    ) -> None:
        self._files = VoteviewClient(origin=origin, http=http)
        self._report = report or (lambda phase: None)
        self._run: IngestionRun | None = None
        self._lock: Any = None
        self._remotes: dict[str, Any] = {}
        self._decision: dict[str, str] = {}
        self._content: dict[str, bytes] = {}
        self._checksums: dict[str, str] = {}
        self._paths: dict[str, str] = {}
        self._artifact_ids: dict[str, str] = {}
        self._publish: set[str] = set()
        self._snapshot: dict[str, list[dict[str, Any]]] = {}
        self._finished = False
        self.result: dict[str, Any] = {}

    def discover(self, ctx: ConnectorContext) -> ConnectorContext:
        """Learn each file's size and Last-Modified. A bad HEAD stops before any download."""
        self._acquire_lock()
        self._run = IngestionRun(
            SOURCE_ID,
            {"files": list(FILES), "citation": CITATION},
            mode="backfill",
        )
        self._run.__enter__()
        ctx.run_id = str(self._run.run_id)
        for name in FILES:
            self._report(f"checking origin: {name}")
            self._remotes[name] = self._files.describe(name)
        return ctx

    def select(self, ctx: ConnectorContext) -> ConnectorContext:
        """The three files. The individual-vote file is not selectable."""
        ctx.selected_ids = FILES
        self._report("selected files")
        return ctx

    def plan(self, ctx: ConnectorContext) -> ConnectorContext:
        """Capacity gate. An unknown size never reaches this stage."""
        ctx.plan_id = SOURCE_ID
        ctx.artifact_urls = tuple(self._remotes[name].url for name in FILES)
        preview = storage_preview(
            [
                RemoteObject(self._remotes[name].url, self._remotes[name].size, "head")
                for name in FILES
            ],
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
        """Download a file only when its size or Last-Modified differs from the retained one."""
        for name in FILES:
            current = get_current_artifact(name, dataset_id=SOURCE_ID)
            decision = self._decide(name, current, self._remotes[name])
            self._decision[name] = decision
            if decision == "reuse":
                assert current is not None
                self._keep_current(name, current)
                continue
            if decision == "reload":
                assert current is not None
                self._keep_current(name, current)
                self._content[name] = Path(current["local_path"]).read_bytes()
                self._publish.add(name)
                continue
            self._report(f"downloading {name}")
            body = self._files.download(name, self._remotes[name].size)
            digest = hashlib.sha256(body).hexdigest()
            self._checksums[name] = digest
            self._content[name] = body
            if (
                current is not None
                and current["checksum_sha256"] == digest
                and current["status"] == "loaded"
                and self._rule_current(name, current.get("metadata") or {})
            ):
                # Same bytes, new Last-Modified: keep the version and do not reload rows.
                self._decision[name] = "same_bytes"
                self._artifact_ids[name] = str(current["artifact_id"])
                continue
            self._publish.add(name)
        self._parse()
        ctx.checksums = tuple(self._checksums[name] for name in FILES)
        self._report("validated files")
        return ctx

    def evidence(self, ctx: ConnectorContext) -> ConnectorContext:
        """Retain new bytes beside the old file. Registration waits until publish commits."""
        root = Path(settings.data_root).expanduser().resolve() / "congress" / "voteview"
        root.mkdir(parents=True, exist_ok=True)
        for name, body in self._content.items():
            if name in self._paths:
                continue
            checksum = self._checksums[name]
            destination = retained_path(root / name, checksum)
            staging = root / f".{name}.{checksum}.incoming"
            staging.write_bytes(body)
            retained = retain_artifact_bytes(
                staging, checksum, destination=destination, move=True
            )
            self._paths[name] = str(retained)
        self._report("retained evidence")
        return ctx

    def stage(self, ctx: ConnectorContext) -> ConnectorContext:
        """The parsed rows are the stage. Nothing is written here."""
        self._report("staged snapshot")
        return ctx

    def normalize(self, ctx: ConnectorContext) -> ConnectorContext:
        """Chambers are house, senate, or president. Scores stay Voteview's numbers."""
        self._report("normalized keys")
        return ctx

    def validate(self, ctx: ConnectorContext) -> ConnectorContext:
        """Parse again from the bytes so a damaged read cannot publish."""
        self._parse()
        self._report("validated")
        return ctx

    def publish(self, ctx: ConnectorContext) -> ConnectorContext:
        """Register changed evidence and replace that file's rows, in one transaction."""
        if ctx.run_id is None:
            raise RuntimeError("voteview snapshot is not ready to publish")
        register = self._publish | {
            name for name, decision in self._decision.items() if decision == "same_bytes"
        }
        counts = dict(_ZERO_COUNTS)
        if register:
            with connect() as conn:
                for name in FILES:
                    if name not in register:
                        continue
                    artifact = register_artifact(
                        SOURCE_ID,
                        self._remotes[name].url,
                        self._paths[name],
                        name,
                        status="loaded",
                        checksum_sha256=self._checksums[name],
                        bytes_downloaded=self._remotes[name].size,
                        content_type=_CONTENT_TYPE[name],
                        metadata={
                            "file": name,
                            "remote_size": self._remotes[name].size,
                            "remote_last_modified": self._remotes[name].last_modified,
                            "citation": CITATION,
                            **({"link_rule": LINK_RULE} if name == MEMBERS else {}),
                        },
                        conn=conn,
                    )
                    self._artifact_ids[name] = str(artifact["artifact_id"])
                counts = publish_voteview(
                    conn,
                    members=self._stamped(MEMBERS, ctx.run_id),
                    roll_calls=self._stamped(ROLLCALLS, ctx.run_id),
                    parties=self._stamped(PARTIES, ctx.run_id),
                    run_id=ctx.run_id,
                    members_artifact_id=self._artifact_ids.get(MEMBERS),
                )
                gaps = stored_counts(conn)
                conn.commit()
        else:
            with connect() as conn:
                gaps = stored_counts(conn)
        partial = gaps["unlinked_members"] > 0
        self.result = {
            **counts,
            **gaps,
            "citation": CITATION,
            "downloaded": [
                name for name in FILES if self._decision.get(name) in {"download", "same_bytes"}
            ],
            "reused": [name for name in FILES if self._decision.get(name) == "reuse"],
            "partial": partial,
        }
        if self._run is not None:
            self._run.record_count = gaps["members"] + gaps["roll_calls"] + gaps["parties"]
            self._target("core.voteview_member", gaps["members"], counts["members_inserted"], partial)
            self._target(
                "core.voteview_roll_call", gaps["roll_calls"], counts["roll_calls_inserted"], False
            )
            self._target("core.voteview_party", gaps["parties"], counts["parties_inserted"], False)
        self._finished = True
        self._report("published")
        return ctx

    def checkpoint(self, ctx: ConnectorContext) -> ConnectorContext:
        """Close the run once. A House or Senate member with no person is partial, not a failure."""
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
                self._files.close()
        self._report("checkpointed")
        return ctx

    def _parse(self) -> None:
        self._snapshot = parse_voteview_files(
            {name: self._content[name] for name in self._publish}
        )

    def _stamped(self, name: str, run_id: str) -> list[dict[str, Any]] | None:
        if name not in self._publish:
            return None
        artifact_id = self._artifact_ids[name]
        return [
            {**row, "source_artifact_id": artifact_id, "run_id": run_id}
            for row in self._snapshot[name]
        ]

    def _target(self, table: str, total: int, inserted: int, partial: bool) -> None:
        assert self._run is not None
        self._run.record_target(
            table,
            "all",
            inserted=inserted,
            updated=0,
            skipped=max(total - inserted, 0),
            status="partial" if partial else "succeeded",
        )

    def _keep_current(self, name: str, current: Mapping[str, Any]) -> None:
        self._checksums[name] = str(current["checksum_sha256"])
        self._paths[name] = str(current["local_path"])
        self._artifact_ids[name] = str(current["artifact_id"])

    def _decide(self, name: str, current: Mapping[str, Any] | None, remote: Any) -> str:
        if current is None or not current.get("checksum_sha256"):
            return "download"
        meta = current.get("metadata") or {}
        headers_match = (
            meta.get("remote_size") == remote.size
            and meta.get("remote_last_modified") == remote.last_modified
        )
        try:
            validate_retained(str(current["local_path"]), str(current["checksum_sha256"]))
            intact = Path(str(current["local_path"])).stat().st_size == remote.size
        except (ValueError, OSError):
            intact = False
        if headers_match and intact and current.get("bytes_downloaded") == remote.size:
            if current.get("status") == "loaded" and self._rule_current(name, meta):
                return "reuse"
            return "reload"
        return "download"

    def _rule_current(self, name: str, metadata: Mapping[str, Any]) -> bool:
        """Member files reload once after the link rule changes. Other files do not."""
        if name != MEMBERS:
            return True
        return metadata.get("link_rule") == LINK_RULE

    def _acquire_lock(self) -> None:
        """One sync at a time: two would race on a file replace."""
        conn = connect()
        conn.autocommit = True
        if not try_sync_lock(conn, LOCK_KEY):
            conn.close()
            raise RuntimeError(
                "another sync-voteview is in progress (it holds the database lock); "
                "wait for it to finish, then rerun"
            )
        self._lock = conn
