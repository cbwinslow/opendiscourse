"""Load Congress.gov bills for Congresses that GovInfo bulk files do not cover.

GovInfo BILLSTATUS starts at the 108th Congress (2003). Congress.gov is the
government record for earlier bills, back to the 93rd Congress (1973). This
loader refuses Congress 108 and later so it cannot overwrite those GovInfo rows.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from ..artifact_storage import retain_artifact_bytes, retained_path
from ..config import settings
from ..db import connect
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


def _people(items: Any, role: str) -> list[dict[str, Any]]:
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
        "sponsorships": _people(bill.get("sponsors"), "sponsor") + _people(_list_payload(cosponsors, "cosponsors"), "cosponsor"),
        "actions": action_rows,
        "committees": committee_rows,
        "subjects": subject_rows,
        "summaries": summary_rows,
        "documents": documents,
        "record": record,
        "policy_area": _text(policy.get("name")),
    }


SOURCE_ID = "congress.congress_gov_bills"
LOCK_KEY = f"{SOURCE_ID}:sync"
DEFAULT_CONGRESSES = (106, 107)


def _key(congress: int, bill_type: str, number: str, part: str) -> str:
    return f"{congress}/{bill_type.lower()}/{number}/{part}"


class CongressBillConnector:
    """Download Congress.gov bill JSON and save it beside the GovInfo bills.

    Congress 108 and later are refused: those bills already come from GovInfo.
    A second run skips a part whose retained file is already marked loaded.
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
    ) -> None:
        chosen = congresses or DEFAULT_CONGRESSES
        refused = [item for item in chosen if item not in ALLOWED]
        if refused:
            raise ValueError(
                "Congress.gov bill sync is only for Congresses 93 through 107, "
                f"before GovInfo bill files; refusing {refused}"
            )
        self._congresses = tuple(dict.fromkeys(chosen))
        self._limit = limit
        if http is not None:
            self._client = CongressBillClient(http=http, api_key=api_key or "test")
        else:
            self._client = CongressBillClient(api_key=api_key)
        self._report = report or (lambda _phase: None)
        self._run: IngestionRun | None = None
        self._lock: Any = None
        self._loaded: dict[str, dict[str, Any]] = {}
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
        self._run = IngestionRun(SOURCE_ID, {"congresses": list(self._congresses)}, mode="backfill")
        self._run.__enter__()
        ctx.run_id = str(self._run.run_id)
        self._loaded = current_artifacts(SOURCE_ID)
        self._report("discovered retained bills")
        return ctx

    def select(self, ctx: ConnectorContext) -> ConnectorContext:
        ctx.selected_ids = tuple(str(item) for item in self._congresses)
        return ctx

    def plan(self, ctx: ConnectorContext) -> ConnectorContext:
        ctx.plan_id = SOURCE_ID
        self._report("planned Congress.gov bills")
        return ctx

    def extract(self, ctx: ConnectorContext) -> ConnectorContext:
        """Download what is not already loaded. Each bill is saved before the next."""
        counts = {"bills": 0, "skipped": 0}
        try:
            for congress in self._congresses:
                identities = self._identities(congress)
                if self._limit is not None:
                    identities = identities[: self._limit]
                for identity in identities:
                    key = _key(int(identity["congress"]), identity["bill_type"], identity["number"], "detail")
                    if key in self._loaded and self._loaded[key].get("status") == "loaded":
                        counts["skipped"] += 1
                        continue
                    self._one(identity)
                    counts["bills"] += 1
                    self._report(f"loaded {identity['congress']} {identity['bill_type']} {identity['number']}")
        finally:
            self._client.close()
        self.result = counts
        self._finished = True
        if self._run is not None:
            self._run.record_count = counts["bills"]
            self._run.record_target("core.bill", "106-107", inserted=counts["bills"], skipped=counts["skipped"])
        self._report("extracted bills")
        return ctx

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

    def _one(self, identity: dict[str, str]) -> None:
        congress = int(identity["congress"])
        bill_type = identity["bill_type"]
        number = identity["number"]
        parts: dict[str, bytes] = {}
        detail_artifact = None
        for name in ("detail", *PARTS):
            key = _key(congress, bill_type, number, name)
            current = self._loaded.get(key)
            if current and current.get("status") == "loaded" and current.get("local_path"):
                body = Path(current["local_path"]).read_bytes()
                artifact_id = str(current["artifact_id"])
            else:
                body = self._client.part(congress, bill_type, number, name)
                artifact_id = self._keep(
                    key,
                    CongressBillClient.url_for(congress, bill_type, number, name),
                    body,
                )
            parts[name] = body
            if name == "detail":
                detail_artifact = artifact_id
        assert detail_artifact is not None
        parsed = assemble_bill(
            detail=parts["detail"],
            actions=parts.get("actions"),
            committees=parts.get("committees"),
            subjects=parts.get("subjects"),
            summaries=parts.get("summaries"),
            cosponsors=parts.get("cosponsors"),
            text=parts.get("text"),
        )
        with connect() as conn:
            session_id = ensure_us_legislative_session(
                congress,
                source_artifact_id=detail_artifact,
                metadata={"congress": congress, "source": SOURCE_ID},
                conn=conn,
            )
            save_billstatus_bill(
                parsed,
                session_id,
                source_artifact_id=detail_artifact,
                source_member="detail",
                conn=conn,
                source_name=SOURCE_ID,
            )
            conn.commit()

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
        self._loaded[key] = artifact
        return str(artifact["artifact_id"])
