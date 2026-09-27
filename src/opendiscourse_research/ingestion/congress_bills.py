"""Load Congress.gov bills for Congresses that GovInfo bulk files do not cover.

GovInfo BILLSTATUS starts at the 108th Congress (2003). Congress.gov is the
government record for earlier bills, back to the 93rd Congress (1973). This
loader refuses Congress 108 and later so it cannot overwrite those GovInfo rows.
"""

from __future__ import annotations

import hashlib
import json
import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Protocol

from ..artifact_storage import retain_artifact_bytes, retained_path
from ..config import settings
from ..db import connect
from ..providers.congress_api import CongressServerError
from ..providers.congress_bills import PARTS, CongressBillClient
from ..repositories.artifacts import current_artifacts
from ..repositories.legislation import (
    ensure_us_legislative_session,
    register_artifact,
    save_billstatus_bill,
)
from ..repositories.votes import try_sync_lock
from .base import IngestionRun
from .connector import ConnectorContext

ALLOWED = range(93, 108)
BILL_TYPES = {
    "HR": "hr",
    "S": "s",
    "HRES": "hres",
    "SRES": "sres",
    "HJRES": "hjres",
    "SJRES": "sjres",
    "HCONRES": "hconres",
    "SCONRES": "sconres",
}


def _object(payload: Any, where: str) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError(f"{where} is not a JSON object")
    return payload


def _text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned or None


def parse_list_page(content: bytes) -> tuple[list[dict[str, str]], int | None]:
    """Bill identities on one list page, and the next offset when Congress.gov sends one."""
    document = _object(json.loads(content.decode("utf-8")), "bill list")
    bills = document.get("bills")
    if not isinstance(bills, list):
        raise ValueError("bill list has no bills")
    parsed: list[dict[str, str]] = []
    for index, item in enumerate(bills, start=1):
        row = _object(item, f"bill list row {index}")
        bill_type = _text(row.get("type"))
        number = _text(row.get("number"))
        congress = row.get("congress")
        if bill_type not in BILL_TYPES or number is None or not str(number).isdigit():
            raise ValueError(f"bill list row {index} has no usable identity")
        if not isinstance(congress, int):
            raise ValueError(f"bill list row {index} congress is not an integer")
        parsed.append({"congress": str(congress), "bill_type": bill_type, "number": number})
    nxt = document.get("pagination", {})
    offset = None
    if isinstance(nxt, dict) and isinstance(nxt.get("next"), str):
        query = nxt["next"].split("?", 1)[-1]
        for piece in query.split("&"):
            if piece.startswith("offset=") and piece[7:].isdigit():
                offset = int(piece[7:])
    return parsed, offset


def _people(items: Any, role: str, source_member: str) -> list[dict[str, Any]]:
    if not isinstance(items, list):
        return []
    people: list[dict[str, Any]] = []
    for ordinal, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            continue
        bioguide = _text(item.get("bioguideId"))
        if bioguide is None:
            continue
        people.append(
            {
                "member_namespace": "bioguide",
                "member_external_id": bioguide,
                "role": role,
                "source_member": source_member,
                "source_ordinal": ordinal,
                "metadata": {"name": _text(item.get("fullName"))},
            }
        )
    return people


def _list_payload(content: bytes | None, key: str) -> list[Any]:
    if content is None:
        return []
    document = _object(json.loads(content.decode("utf-8")), key)
    value = document.get(key)
    return value if isinstance(value, list) else []


def assemble_bill(
    *,
    detail: bytes,
    actions: bytes | None = None,
    committees: bytes | None = None,
    subjects: bytes | None = None,
    summaries: bytes | None = None,
    cosponsors: bytes | None = None,
    text: bytes | None = None,
) -> dict[str, Any]:
    """Turn the retained Congress.gov JSON into the bill shape the warehouse already saves."""
    document = _object(json.loads(detail.decode("utf-8")), "bill detail")
    bill = _object(document.get("bill"), "bill detail bill")
    raw_type = _text(bill.get("type"))
    number = _text(bill.get("number"))
    congress = bill.get("congress")
    if raw_type not in BILL_TYPES or number is None or not isinstance(congress, int):
        raise ValueError("bill detail has no usable identity")
    latest = bill.get("latestAction") if isinstance(bill.get("latestAction"), dict) else {}
    action_rows = []
    for ordinal, item in enumerate(_list_payload(actions, "actions"), start=1):
        if not isinstance(item, dict) or not _text(item.get("text")):
            continue
        kind = _text(item.get("type"))
        action_rows.append(
            {
                "action_date": _text(item.get("actionDate")),
                "description": _text(item.get("text")),
                "classification": [kind] if kind else None,
                "source_ordinal": ordinal,
                "metadata": {"action_code": _text(item.get("actionCode"))},
                "source_member": "actions",
            }
        )
    committee_rows = []
    for ordinal, item in enumerate(_list_payload(committees, "committees"), start=1):
        if not isinstance(item, dict) or not _text(item.get("systemCode")):
            continue
        committee_rows.append(
            {
                "namespace": "congress.gov.committee",
                "external_id": _text(item.get("systemCode")),
                "name": _text(item.get("name")),
                "chamber": _text(item.get("chamber")),
                "source_ordinal": ordinal,
                "source_member": "committees",
            }
        )
    subject_rows = []
    if subjects is not None:
        body = _object(json.loads(subjects.decode("utf-8")), "subjects")
        block = body.get("subjects") if isinstance(body.get("subjects"), dict) else {}
        area = block.get("policyArea") if isinstance(block.get("policyArea"), dict) else {}
        if _text(area.get("name")):
            subject_rows.append(
                {
                    "namespace": "congress.gov.subject",
                    "external_id": f"policy-area:{_text(area.get('name'))}",
                    "label": _text(area.get("name")),
                    "source_member": "subjects",
                }
            )
        named = block.get("legislativeSubjects")
        if isinstance(named, list):
            for item in named:
                if isinstance(item, dict) and _text(item.get("name")):
                    subject_rows.append(
                        {
                            "namespace": "congress.gov.subject",
                            "external_id": _text(item.get("name")),
                            "label": _text(item.get("name")),
                            "source_member": "subjects",
                        }
                    )
    summary_rows = []
    for ordinal, item in enumerate(_list_payload(summaries, "summaries"), start=1):
        if not isinstance(item, dict) or not _text(item.get("text")):
            continue
        summary_rows.append(
            {
                "version_code": _text(item.get("versionCode")),
                "action_date": _text(item.get("actionDate")),
                "action_description": _text(item.get("actionDesc")),
                "update_date": _text(item.get("updateDate")),
                "text": _text(item.get("text")),
                "source_ordinal": ordinal,
                "source_member": "summaries",
            }
        )
    documents = []
    for item in _list_payload(text, "textVersions"):
        if not isinstance(item, dict):
            continue
        formats = item.get("formats") if isinstance(item.get("formats"), list) else []
        for fmt in formats:
            if not isinstance(fmt, dict) or not _text(fmt.get("url")):
                continue
            documents.append(
                {
                    "source_url": _text(fmt.get("url")),
                    "title": _text(item.get("type")),
                    "published_at": _text(item.get("date")),
                    "version_code": _text(item.get("type")),
                    "source_member": "text",
                    "metadata": {"format": _text(fmt.get("type"))},
                }
            )
    policy = bill.get("policyArea") if isinstance(bill.get("policyArea"), dict) else {}
    record = {
        "bill": bill,
        "actions": json.loads(actions.decode("utf-8")) if actions else None,
        "committees": json.loads(committees.decode("utf-8")) if committees else None,
        "subjects": json.loads(subjects.decode("utf-8")) if subjects else None,
        "summaries": json.loads(summaries.decode("utf-8")) if summaries else None,
        "cosponsors": json.loads(cosponsors.decode("utf-8")) if cosponsors else None,
        "textVersions": json.loads(text.decode("utf-8")) if text else None,
    }
    return {
        "congress": congress,
        "bill_type": BILL_TYPES[raw_type],
        "bill_number": number,
        "title": _text(bill.get("title")),
        "introduced_date": _text(bill.get("introducedDate")),
        "latest_action_date": _text(latest.get("actionDate")),
        "latest_action": _text(latest.get("text")),
        "sponsorships": _people(bill.get("sponsors"), "sponsor", "detail")
        + _people(_list_payload(cosponsors, "cosponsors"), "cosponsor", "cosponsors"),
        "actions": action_rows,
        "committees": committee_rows,
        "subjects": subject_rows,
        "summaries": summary_rows,
        "documents": documents,
        "record": record,
        "policy_area": _text(policy.get("name")),
    }


def assemble_list_bill(
    row: dict[str, Any],
    *,
    actions: bytes | None = None,
    committees: bytes | None = None,
    subjects: bytes | None = None,
    summaries: bytes | None = None,
    cosponsors: bytes | None = None,
    text: bytes | None = None,
) -> dict[str, Any]:
    """Build an explicitly partial bill from one official Congress.gov list row."""
    raw_type = _text(row.get("type"))
    number = _text(row.get("number"))
    congress = row.get("congress")
    if raw_type not in BILL_TYPES or number is None or not isinstance(congress, int):
        raise ValueError("bill list row has no usable identity")
    latest = row.get("latestAction") if isinstance(row.get("latestAction"), dict) else {}
    # Reuse the child-response parser, but give it only fields actually present
    # in the list row.  This synthetic wrapper is never retained as evidence:
    # ``record`` below remains the original list row and sponsorship/policy
    # fields cannot appear because the list does not supply them.
    parsed = assemble_bill(
        detail=json.dumps(
            {
                "bill": {
                    "congress": congress,
                    "type": raw_type,
                    "number": number,
                    "title": _text(row.get("title")),
                    "introducedDate": _text(row.get("introducedDate")),
                    "latestAction": latest,
                }
            }
        ).encode(),
        actions=actions,
        committees=committees,
        subjects=subjects,
        summaries=summaries,
        cosponsors=cosponsors,
        text=text,
    )
    parsed["record"] = row
    return parsed


SOURCE_ID = "congress.congress_gov_bills"
LOCK_KEY = f"{SOURCE_ID}:sync"
DEFAULT_CONGRESSES = (106, 107)
# Several bills at once, so a slow reply does not leave the hourly allowance idle.
PART_WORKERS = 8
BILL_WINDOW = 8
# Saving a bill is slower than asking for the next one. A few saves run at once
# so the hourly allowance does not sit idle while the database catches up.
SAVE_WINDOW = 3

# This is intentionally finite.  It is the only selection accepted by the
# recovery command, so a convenience retry cannot turn into a 106--107 crawl.
RECOVERY_MANIFEST: dict[str, dict[str, str | int]] = {
    "107/hr/2842/detail": {"congress": 107, "bill_type": "HR", "number": "2842", "part": "detail", "list_offset": 4000},
    "107/hr/2843/detail": {"congress": 107, "bill_type": "HR", "number": "2843", "part": "detail", "list_offset": 4000},
    "106/s/1378/cosponsors": {"congress": 106, "bill_type": "S", "number": "1378", "part": "cosponsors"},
    "106/sres/218/cosponsors": {"congress": 106, "bill_type": "SRES", "number": "218", "part": "cosponsors"},
    "107/hr/5346/cosponsors": {"congress": 107, "bill_type": "HR", "number": "5346", "part": "cosponsors"},
}


class PartSource(Protocol):
    """The slice of the bill client the parallel download uses."""

    def part(self, congress: int, bill_type: str, number: str, name: str) -> bytes:
        """One bill JSON document."""


def download_parts(
    client: PartSource,
    congress: int,
    bill_type: str,
    number: str,
    names: tuple[str, ...] | list[str],
    *,
    workers: int = PART_WORKERS,
    on_part: Callable[[str, bytes], None] | None = None,
) -> dict[str, bytes]:
    """Fetch bill parts together. The shared turnstile still starts each request.

    ``on_part`` runs on this thread as each body arrives, so a later failure
    keeps the parts already handed over. One failure still raises after that.
    """
    return _fetch_parts(
        client,
        congress,
        bill_type,
        number,
        names,
        workers=workers,
        on_part=on_part,
        tolerate=(),
    )


def download_parts_best_effort(
    client: PartSource,
    congress: int,
    bill_type: str,
    number: str,
    names: tuple[str, ...] | list[str],
    *,
    workers: int = PART_WORKERS,
) -> tuple[dict[str, bytes], dict[str, str]]:
    """Fetch bill parts together. One server error does not drop the others."""
    return _fetch_parts(
        client,
        congress,
        bill_type,
        number,
        names,
        workers=workers,
        on_part=None,
        tolerate=(CongressServerError,),
    )


def _fetch_parts(
    client: PartSource,
    congress: int,
    bill_type: str,
    number: str,
    names: tuple[str, ...] | list[str],
    *,
    workers: int,
    on_part: Callable[[str, bytes], None] | None,
    tolerate: tuple[type[BaseException], ...],
) -> dict[str, bytes] | tuple[dict[str, bytes], dict[str, str]]:
    chosen = tuple(names)
    found: dict[str, bytes] = {}
    errors: dict[str, str] = {}
    best_effort = bool(tolerate)

    def deliver(name: str, body: bytes) -> None:
        found[name] = body
        if on_part is not None:
            on_part(name, body)

    def one(name: str, body: bytes | None = None, caught: BaseException | None = None) -> None:
        if caught is None:
            assert body is not None
            deliver(name, body)
        else:
            errors[name] = str(caught)

    def read(name: str) -> tuple[bytes | None, BaseException | None]:
        try:
            return client.part(congress, bill_type, number, name), None
        except tolerate as caught:
            if not tolerate:
                raise
            return None, caught

    if len(chosen) < 2 or workers < 2:
        for name in chosen:
            body, caught = read(name)
            one(name, body, caught)
    else:
        with ThreadPoolExecutor(max_workers=min(workers, len(chosen))) as pool:
            futures = {
                pool.submit(read, name): name for name in chosen
            }
            try:
                for future in as_completed(futures):
                    body, caught = future.result()
                    one(futures[future], body, caught)
            except Exception:
                for future in futures:
                    future.cancel()
                raise
    if best_effort:
        return found, errors
    return found


def _key(congress: int, bill_type: str, number: str, part: str) -> str:
    return f"{congress}/{bill_type.lower()}/{number}/{part}"


class CongressBillConnector:
    """Download Congress.gov bill JSON and save it beside the GovInfo bills.

    Congress 108 and later are refused: those bills already come from GovInfo.
    A second run skips a bill whose every part is already marked loaded and
    whose row is already in ``core.bill``. Files without that row are saved
    from disk. One part the server cannot serve is recorded and the other
    bills continue. The missing part is tried again on the next run.
    """

    source_id = SOURCE_ID

    def __init__(
        self,
        congresses: tuple[int, ...] | None = None,
        *,
        limit: int | None = None,
        http: Any = None,
        api_key: str | None = None,
        report: Any = None,
        recovery_keys: tuple[str, ...] | None = None,
    ) -> None:
        chosen = congresses or DEFAULT_CONGRESSES
        refused = [item for item in chosen if item not in ALLOWED]
        if refused:
            raise ValueError(
                "Congress.gov bill sync is only for Congresses 93 through 107, "
                f"before GovInfo bill files; refusing {refused}"
            )
        self._congresses = tuple(dict.fromkeys(chosen))
        self._recovery_keys = self._validate_recovery_keys(recovery_keys)
        self._limit = limit
        if http is not None:
            self._client = CongressBillClient(http=http, api_key=api_key or "test")
        else:
            self._client = CongressBillClient(api_key=api_key)
        self._report = report or (lambda _phase: None)
        self._run: IngestionRun | None = None
        self._lock: Any = None
        self._loaded: dict[str, dict[str, Any]] = {}
        self._stored: set[tuple[str, str, str]] | None = None
        self._loaded_lock = threading.Lock()
        self._failed: dict[str, str] = {}
        self._failure_lock = threading.Lock()
        self._finished = False
        self.result: dict[str, Any] = {}

    def discover(self, ctx: ConnectorContext) -> ConnectorContext:
        """One run at a time. The bill list itself is the catalog."""
        conn = connect()
        conn.autocommit = True
        if not try_sync_lock(conn, LOCK_KEY):
            conn.close()
            raise RuntimeError("another Congress.gov bill sync is in progress; wait, then rerun")
        self._lock = conn
        self._run = IngestionRun(
            SOURCE_ID,
            {"congresses": list(self._congresses), "recovery_keys": list(self._recovery_keys)},
            mode="backfill",
        )
        self._run.__enter__()
        ctx.run_id = str(self._run.run_id)
        self._loaded = current_artifacts(SOURCE_ID)
        self._stored = self._load_stored_bills()
        self._report("discovered retained bills")
        return ctx

    def select(self, ctx: ConnectorContext) -> ConnectorContext:
        ctx.selected_ids = self._recovery_keys or tuple(str(item) for item in self._congresses)
        return ctx

    def plan(self, ctx: ConnectorContext) -> ConnectorContext:
        ctx.plan_id = SOURCE_ID
        self._report("planned Congress.gov bills")
        return ctx

    def extract(self, ctx: ConnectorContext) -> ConnectorContext:
        """Download what is not already loaded. The next bill starts while this one is saved."""
        counts = {"bills": 0, "skipped": 0, "not_saved": 0}
        if self._stored is None:
            self._stored = self._load_stored_bills()
        try:
            if self._recovery_keys:
                self._recover(counts)
            else:
                for congress in self._congresses:
                    identities = self._identities(congress)
                    if self._limit is not None:
                        identities = identities[: self._limit]
                    todo: list[dict[str, str]] = []
                    for identity in identities:
                        if self._bill_complete(identity):
                            counts["skipped"] += 1
                            continue
                        todo.append(identity)
                    self._drain(todo, counts)
        finally:
            self._client.close()
        failed_parts = [
            {"key": key, "error": message} for key, message in sorted(self._failed.items())
        ]
        self.result = {
            "bills": counts["bills"],
            "skipped": counts["skipped"],
            "not_saved": counts["not_saved"],
            "partial": bool(failed_parts),
            "failed_parts": failed_parts,
        }
        self._finished = True
        if self._run is not None:
            self._run.record_count = counts["bills"]
            if failed_parts:
                self._run.mark_partial()
            self._run.record_target(
                "core.bill",
                "recovery" if self._recovery_keys else "106-107",
                inserted=counts["bills"],
                skipped=counts["skipped"],
                status="partial" if failed_parts else "succeeded",
            )
        self._report("extracted bills")
        return ctx

    @staticmethod
    def _validate_recovery_keys(keys: tuple[str, ...] | None) -> tuple[str, ...]:
        if keys is None:
            return ()
        chosen = tuple(dict.fromkeys(keys))
        unknown = [key for key in chosen if key not in RECOVERY_MANIFEST]
        if unknown:
            raise ValueError(
                "Congress.gov recovery only accepts known failed endpoint keys: "
                f"{', '.join(sorted(RECOVERY_MANIFEST))}; refused {', '.join(unknown)}"
            )
        return chosen or tuple(RECOVERY_MANIFEST)

    def _recover(self, counts: dict[str, int]) -> None:
        """Retry only manifest endpoints, using retained list and child evidence."""
        for key in self._recovery_keys:
            item = RECOVERY_MANIFEST[key]
            identity = {
                "congress": str(item["congress"]),
                "bill_type": str(item["bill_type"]),
                "number": str(item["number"]),
            }
            part = str(item["part"])
            ready, list_row = self._recovery_ready(identity, item)
            fetched, errors = self._download(identity, [part])
            saved, missing = self._commit(
                identity,
                fetched,
                errors,
                ready,
                list_row=list_row,
                recovery_part=part,
            )
            if saved:
                counts["bills"] += 1
            else:
                counts["not_saved"] += 1
            if missing:
                self._report(f"recovery still missing {', '.join(missing)} for {key}")
            else:
                self._report(f"recovered {key}")

    def _recovery_ready(
        self, identity: dict[str, str], manifest: dict[str, str | int]
    ) -> tuple[dict[str, tuple[bytes, str]], tuple[bytes, str] | None]:
        """Load existing evidence without fetching a list or unrelated child endpoint."""
        congress, bill_type, number = int(identity["congress"]), identity["bill_type"], identity["number"]
        ready: dict[str, tuple[bytes, str]] = {}
        list_row: tuple[bytes, str] | None = None
        for name in ("detail", *PARTS):
            current = self._loaded.get(_key(congress, bill_type, number, name))
            if current and current.get("status") == "loaded" and current.get("local_path"):
                ready[name] = (Path(current["local_path"]).read_bytes(), str(current["artifact_id"]))
        offset = manifest.get("list_offset")
        if offset is not None:
            list_key = f"{congress}/list/{offset}"
            current = self._loaded.get(list_key)
            if not (current and current.get("status") == "loaded" and current.get("local_path")):
                raise ValueError(f"recovery needs retained official list evidence at {list_key}")
            body = Path(current["local_path"]).read_bytes()
            document = _object(json.loads(body.decode("utf-8")), "bill list")
            rows = document.get("bills")
            row = next((value for value in rows if isinstance(value, dict) and value.get("congress") == congress and _text(value.get("type")) == bill_type and _text(value.get("number")) == number), None) if isinstance(rows, list) else None
            if row is None:
                raise ValueError(f"recovery list evidence at {list_key} has no {congress} {bill_type} {number}")
            list_row = (json.dumps(row).encode(), str(current["artifact_id"]))
        return ready, list_row

    def evidence(self, ctx: ConnectorContext) -> ConnectorContext:
        return ctx

    def stage(self, ctx: ConnectorContext) -> ConnectorContext:
        return ctx

    def normalize(self, ctx: ConnectorContext) -> ConnectorContext:
        return ctx

    def validate(self, ctx: ConnectorContext) -> ConnectorContext:
        return ctx

    def publish(self, ctx: ConnectorContext) -> ConnectorContext:
        """Rows are committed with each bill during extract, so a killed run can resume."""
        return ctx

    def checkpoint(self, ctx: ConnectorContext) -> ConnectorContext:
        failure = None
        if self._run is not None and (ctx.error or not self._finished):
            failure = RuntimeError(ctx.error or "interrupted before the bill sync finished")
        try:
            if self._run is not None:
                self._run.__exit__(type(failure) if failure else None, failure, None)
        finally:
            if self._lock is not None:
                self._lock.close()
                self._lock = None
        if failure is not None and ctx.error is None:
            raise failure
        return ctx

    def _identities(self, congress: int) -> list[dict[str, str]]:
        found: list[dict[str, str]] = []
        offset = 0
        while True:
            key = f"{congress}/list/{offset}"
            current = self._loaded.get(key)
            if current and current.get("status") == "loaded" and current.get("local_path"):
                body = Path(current["local_path"]).read_bytes()
            else:
                body = self._client.list_page(congress, offset)
                self._keep(key, f"https://api.congress.gov/v3/bill/{congress}?offset={offset}&limit=250&format=json", body)
            page, nxt = parse_list_page(body)
            found.extend(page)
            if nxt is None:
                return found
            offset = nxt

    def _drain(self, todo: list[dict[str, str]], counts: dict[str, int]) -> None:
        """Keep several bills downloading while a few others are saved."""
        if not todo:
            return
        pending = list(todo)
        inflight: list[tuple[dict[str, str], dict[str, tuple[bytes, str]], Any]] = []
        saving: list[tuple[dict[str, str], Any]] = []
        with ThreadPoolExecutor(max_workers=BILL_WINDOW) as pool, ThreadPoolExecutor(max_workers=SAVE_WINDOW) as savers:
            while pending or inflight or saving:
                while pending and len(inflight) < BILL_WINDOW:
                    identity = pending.pop(0)
                    needed, ready = self._plan(identity)
                    inflight.append((identity, ready, pool.submit(self._download, identity, needed)))
                if inflight:
                    identity, ready, incoming = inflight.pop(0)
                    fetched, errors = incoming.result()
                    if pending and len(inflight) < BILL_WINDOW:
                        nxt = pending.pop(0)
                        nxt_needed, nxt_ready = self._plan(nxt)
                        inflight.append((nxt, nxt_ready, pool.submit(self._download, nxt, nxt_needed)))
                    saving.append(
                        (identity, savers.submit(self._commit, identity, fetched, errors, ready))
                    )
                while saving and (len(saving) >= SAVE_WINDOW or not inflight):
                    done_id, done = saving.pop(0)
                    saved, missing = done.result()
                    label = f"{done_id['congress']} {done_id['bill_type']} {done_id['number']}"
                    if saved and missing:
                        counts["bills"] += 1
                        self._report(f"loaded {label} without {', '.join(missing)}")
                    elif saved:
                        counts["bills"] += 1
                        self._report(f"loaded {label}")
                    else:
                        counts["not_saved"] += 1
                        self._report(f"recorded a missing part for {label}")

    def _load_stored_bills(self) -> set[tuple[str, str, str]]:
        """Bills already in the warehouse for this run's Congresses.

        A retained file is not enough. The previous run could mark every part
        loaded and die before the row was written, and a later run would skip it.
        """
        sessions = [str(item) for item in self._congresses]
        with connect() as conn:
            rows = conn.execute(
                """
                SELECT legislative_session, bill_type, bill_number
                FROM core.bill
                WHERE jurisdiction = 'us'
                  AND legislative_session = ANY(%(sessions)s)
                """,
                {"sessions": sessions},
            ).fetchall()
        return {
            (str(row["legislative_session"]), str(row["bill_type"]).lower(), str(row["bill_number"]))
            for row in rows
        }

    def _bill_complete(self, identity: dict[str, str]) -> bool:
        """True when every part is on disk and the bill row already exists.

        A failed part does not count. Files with no row are saved again from disk.
        """
        congress = int(identity["congress"])
        bill_type = identity["bill_type"]
        number = identity["number"]
        for name in ("detail", *PARTS):
            with self._loaded_lock:
                current = self._loaded.get(_key(congress, bill_type, number, name))
            if not (current and current.get("status") == "loaded" and current.get("local_path")):
                return False
        if self._stored is None:
            return True
        return (identity["congress"], bill_type.lower(), number) in self._stored

    def _plan(self, identity: dict[str, str]) -> tuple[list[str], dict[str, tuple[bytes, str]]]:
        """Split one bill into files still on disk and parts still to download."""
        congress = int(identity["congress"])
        bill_type = identity["bill_type"]
        number = identity["number"]
        needed: list[str] = []
        ready: dict[str, tuple[bytes, str]] = {}
        for name in ("detail", *PARTS):
            with self._loaded_lock:
                current = self._loaded.get(_key(congress, bill_type, number, name))
            if current and current.get("status") == "loaded" and current.get("local_path"):
                ready[name] = (Path(current["local_path"]).read_bytes(), str(current["artifact_id"]))
            else:
                needed.append(name)
        return needed, ready

    def _download(
        self, identity: dict[str, str], names: list[str]
    ) -> tuple[dict[str, bytes], dict[str, str]]:
        """Fetch the missing parts. One failure leaves the parts that arrived."""
        if not names:
            return {}, {}
        return download_parts_best_effort(
            self._client,
            int(identity["congress"]),
            identity["bill_type"],
            identity["number"],
            names,
        )

    def _note_failure(self, identity: dict[str, str], name: str, exc: BaseException) -> None:
        """Remember a part Congress.gov could not serve, without hiding a later good copy."""
        congress = int(identity["congress"])
        bill_type = identity["bill_type"]
        number = identity["number"]
        key = _key(congress, bill_type, number, name)
        message = str(exc)
        register_artifact(
            SOURCE_ID,
            CongressBillClient.url_for(congress, bill_type, number, name),
            f"virtual://{key}",
            key,
            status="failed",
            error_message=message[:500],
            bytes_downloaded=0,
            content_type="application/json",
            metadata={"file": key},
        )
        with self._failure_lock:
            self._failed[key] = message

    def _commit(
        self,
        identity: dict[str, str],
        fetched: dict[str, bytes],
        errors: dict[str, str],
        ready: dict[str, tuple[bytes, str]],
        *,
        list_row: tuple[bytes, str] | None = None,
        recovery_part: str | None = None,
    ) -> tuple[bool, tuple[str, ...]]:
        congress = int(identity["congress"])
        bill_type = identity["bill_type"]
        number = identity["number"]
        parts: dict[str, bytes] = {}
        kept: dict[str, str] = {}
        for name, (body, artifact_id) in ready.items():
            parts[name] = body
            kept[name] = artifact_id
        for name, body in fetched.items():
            parts[name] = body
            kept[name] = self._keep(
                _key(congress, bill_type, number, name),
                CongressBillClient.url_for(congress, bill_type, number, name),
                body,
            )
        for name, message in errors.items():
            self._note_failure(identity, name, RuntimeError(message))
        detail_artifact = kept.get("detail")
        missing = tuple(name for name in ("detail", *PARTS) if name in errors)
        if recovery_part == "cosponsors" and detail_artifact is not None:
            # This bill already exists. A retry must not re-promote its old
            # actions, committees, subjects, summaries, or text under new
            # source members. Only the newly served cosponsor response may
            # change the warehouse.
            if "cosponsors" not in parts:
                return False, missing
            parsed = assemble_bill(detail=parts["detail"], cosponsors=parts["cosponsors"])
            parsed["sponsorships"] = [
                item for item in parsed["sponsorships"] if item["role"] == "cosponsor"
            ]
            parsed["record"] = None
            base_artifact, base_member = detail_artifact, "detail"
            source_artifacts: dict[str, str] | None = {"cosponsors": kept["cosponsors"]}
        elif detail_artifact is None:
            if list_row is None:
                return False, missing
            parsed = assemble_list_bill(
                json.loads(list_row[0].decode("utf-8")),
                actions=parts.get("actions"),
                committees=parts.get("committees"),
                subjects=parts.get("subjects"),
                summaries=parts.get("summaries"),
                cosponsors=parts.get("cosponsors"),
                text=parts.get("text"),
            )
            # A list page is one artifact for many bills. Its source-member
            # key must therefore include the bill identity, or the unique
            # artifact/member record key would make one partial bill replace
            # another bill's retained list row.
            base_artifact = list_row[1]
            base_member = f"list:{congress}/{bill_type.lower()}/{number}"
            source_artifacts = kept
        else:
            parsed = assemble_bill(
                detail=parts["detail"],
                actions=parts.get("actions"),
                committees=parts.get("committees"),
                subjects=parts.get("subjects"),
                summaries=parts.get("summaries"),
                cosponsors=parts.get("cosponsors"),
                text=parts.get("text"),
            )
            base_artifact, base_member = detail_artifact, "detail"
            # Preserve the established full-sync lineage. Only the exceptional
            # recovery path needs per-member artifacts.
            source_artifacts = kept if recovery_part is not None else None
        with connect() as conn:
            session_id = ensure_us_legislative_session(
                congress,
                source_artifact_id=base_artifact,
                metadata={"congress": congress, "source": SOURCE_ID},
                conn=conn,
            )
            save_billstatus_bill(
                parsed,
                session_id,
                source_artifact_id=base_artifact,
                source_member=base_member,
                source_artifacts=source_artifacts,
                conn=conn,
                source_name=SOURCE_ID,
            )
            conn.commit()
        if self._stored is not None:
            self._stored.add((str(congress), bill_type.lower(), number))
        return True, missing

    def _keep(self, key: str, url: str, body: bytes) -> str:
        digest = hashlib.sha256(body).hexdigest()
        root = Path(settings.data_root).expanduser().resolve() / "congress" / "congress_gov"
        destination = retained_path(root / f"{key.replace('/', '__')}.json", digest)
        staging = destination.with_suffix(".incoming")
        staging.parent.mkdir(parents=True, exist_ok=True)
        staging.write_bytes(body)
        retained = retain_artifact_bytes(staging, digest, destination=destination, move=True)
        artifact = register_artifact(
            SOURCE_ID,
            url,
            str(retained),
            key,
            status="loaded",
            checksum_sha256=digest,
            bytes_downloaded=len(body),
            content_type="application/json",
            metadata={"file": key},
        )
        with self._loaded_lock:
            self._loaded[key] = artifact
        return str(artifact["artifact_id"])
