"""Repository queries and persistence for deterministic federal legislation."""

from __future__ import annotations

from collections import Counter
from functools import cache
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

from psycopg.pq import TransactionStatus
from psycopg.types.json import Jsonb
from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert

from ..artifact_storage import validate_retained
from ..db import connect, session
from ..identity_merge import load_same_person
from ..ingestion import billstatus_sections
from ..ingestion.billstatus_record import record_sha256, xml_to_record
from ..models.catalog import artifact_table
from ..models.core import (
    bill_action_table,
    bill_committee_table,
    bill_document_table,
    bill_identifier_table,
    bill_sponsorship_table,
    bill_subject_table,
    bill_table,
    document_table,
    jurisdiction_table,
    legislative_session_table,
    person_identifier_table,
)
from ..models.ingest import identity_exception_table, resume_cursor_table
from .people import resolve_person

_QUERY_ROOT = Path(__file__).resolve().parents[3] / "sql" / "query" / "legislation"


def _text_or_none(value: str | None) -> str | None:
    """Normalize optional XML text so blank values become database NULLs."""
    return value.strip() if value and value.strip() else None


@cache
def _query(name: str) -> str:
    """Read a named, version-controlled legislation query template (once per process)."""
    return (_QUERY_ROOT / f"{name}.sql").read_text()


def bill_keys(congress: int, bill_type: str) -> set[str]:
    """Return canonical bill numbers for one Congress and bill type."""
    bill = bill_table()
    with session() as active_session:
        return set(
            active_session.scalars(
                select(bill.c.bill_number).where(
                    bill.c.jurisdiction == "us",
                    bill.c.legislative_session == str(congress),
                    bill.c.bill_type == bill_type.lower(),
                )
            )
        )


def openstates_vote_snapshot_counts(
    congresses: list[int], conn: Any
) -> dict[str, dict[str, Any]]:
    """Read source and canonical vote counts without mutating either system."""
    identifiers = [str(congress) for congress in congresses]
    result = {identifier: {"congress": int(identifier)} for identifier in identifiers}
    with conn.cursor() as cur:
        cur.execute(
            _query("openstates_vote_snapshot_counts"), {"congresses": identifiers}
        )
        for row in cur.fetchall():
            result[row["congress"]].update(dict(row))
        for congress in identifiers:
            cur.execute(
                _query("openstates_person_vote_snapshot_count"), {"congress": congress}
            )
            result[congress]["source_person_votes"] = cur.fetchone()[
                "source_person_votes"
            ]
        cur.execute(_query("canonical_vote_counts"), {"congresses": identifiers})
        for row in cur.fetchall():
            result[row["congress"]].update(dict(row))
    return result


def get_resume_cursor(
    dataset_id: str, cursor_key: str, conn: Any | None = None
) -> dict[str, Any] | None:
    """Return one persisted ingestion checkpoint without changing it."""
    if conn is None:
        table = resume_cursor_table()
        with session() as active_session:
            row = active_session.execute(
                select(
                    table.c.cursor,
                    table.c.source_artifact_id,
                    table.c.last_run_id,
                    table.c.state,
                    table.c.updated_at,
                ).where(table.c.dataset_id == dataset_id, table.c.cursor_key == cursor_key)
            ).mappings().one_or_none()
        return dict(row) if row else None
    with conn.cursor() as cur:
        cur.execute(
            _query("get_resume_cursor"),
            {"dataset_id": dataset_id, "cursor_key": cursor_key},
        )
        row = cur.fetchone()
    return dict(row) if row else None


def save_resume_cursor(
    dataset_id: str,
    cursor_key: str,
    cursor: dict[str, Any],
    source_artifact_id: str,
    last_run_id: str,
    state: str,
    conn: Any | None = None,
) -> dict[str, Any]:
    """Persist a source-scoped checkpoint in the caller's transaction."""
    if conn is None:
        table = resume_cursor_table()
        statement = (
            insert(table)
            .values(
                dataset_id=dataset_id,
                cursor_key=cursor_key,
                cursor=cursor,
                source_artifact_id=source_artifact_id,
                last_run_id=last_run_id,
                state=state,
            )
            .on_conflict_do_update(
                index_elements=(table.c.dataset_id, table.c.cursor_key),
                set_={
                    "cursor": cursor,
                    "source_artifact_id": source_artifact_id,
                    "last_run_id": last_run_id,
                    "state": state,
                    "updated_at": func.now(),
                },
            )
            .returning(table.c.cursor, table.c.state)
        )
        with session() as active_session:
            return dict(active_session.execute(statement).mappings().one())
    with conn.cursor() as cur:
        cur.execute(
            _query("save_resume_cursor"),
            {
                "dataset_id": dataset_id,
                "cursor_key": cursor_key,
                "cursor": Jsonb(cursor),
                "source_artifact_id": source_artifact_id,
                "last_run_id": last_run_id,
                "state": state,
            },
        )
        row = cur.fetchone()
    return dict(row) if row else {}


def record_vote_identity_exceptions(
    congress: int,
    source_artifact_id: str,
    run_id: str,
    voter_ids: list[str | None],
    conn: Any | None = None,
) -> int:
    """Persist unresolved voter identifiers with source/run evidence."""
    if not voter_ids:
        return 0
    values = Counter(voter_id or "<missing>" for voter_id in voter_ids)
    if conn is None:
        table = identity_exception_table()
        with session() as active_session:
            for external_id, reference_count in values.items():
                active_session.execute(
                    insert(table)
                    .values(
                        dataset_id="openstates.legislation",
                        run_id=run_id,
                        source_artifact_id=source_artifact_id,
                        congress=congress,
                        kind="voter",
                        namespace="ocd",
                        external_id=external_id,
                        reason=(
                            "missing_ocd_voter_id"
                            if external_id == "<missing>"
                            else "no_canonical_person_identifier"
                        ),
                        reference_count=reference_count,
                    )
                    .on_conflict_do_update(
                        index_elements=(
                            table.c.run_id,
                            table.c.kind,
                            table.c.namespace,
                            table.c.external_id,
                            table.c.reason,
                        ),
                        set_={
                            "reference_count": table.c.reference_count + reference_count,
                            "last_seen_at": func.now(),
                        },
                    )
                )
        return len(values)
    with conn.cursor() as cur:
        for external_id, reference_count in values.items():
            cur.execute(
                _query("record_vote_identity_exception"),
                {
                    "dataset_id": "openstates.legislation",
                    "run_id": run_id,
                    "source_artifact_id": source_artifact_id,
                    "congress": congress,
                    "external_id": external_id,
                    "reason": (
                        "missing_ocd_voter_id"
                        if external_id == "<missing>"
                        else "no_canonical_person_identifier"
                    ),
                    "reference_count": reference_count,
                },
            )
    return len(values)


def _artifact_action(latest: Any, checksum: str | None, status: str, local_path: str) -> str:
    """Choose the same append, promotion, or retry operation for both DB routes."""
    if latest is None:
        return "append"
    if latest["checksum_sha256"] is None and latest["status"] in {
        "planned",
        "downloading",
        "failed",
    }:
        return "promote"
    if checksum == latest["checksum_sha256"]:
        if checksum is not None:
            if latest["local_path"].startswith("virtual://") and not local_path.startswith("virtual://"):
                return "append"
            try:
                validate_retained(latest["local_path"], checksum)
            except (ValueError, OSError):
                return "append"
        return (
            "retry" if status not in {"planned", "downloading", "failed"} else "append"
        )
    return "append"


def register_artifact(
    dataset_id: str,
    remote_url: str,
    local_path: str,
    artifact_key: str,
    status: str = "downloaded",
    checksum_sha256: str | None = None,
    bytes_downloaded: int | None = None,
    period_start: str | None = None,
    period_end: str | None = None,
    content_type: str | None = None,
    metadata: dict[str, Any] | None = None,
    conn: Any | None = None,
    error_message: str | None = None,
) -> dict[str, Any]:
    """Append or promote one artifact version without redefining prior evidence."""
    if checksum_sha256 is not None:
        validate_retained(local_path, checksum_sha256)
    params = {
        "dataset_id": dataset_id,
        "remote_url": remote_url,
        "local_path": local_path,
        "artifact_key": artifact_key,
        "period_start": period_start,
        "period_end": period_end,
        "content_type": content_type or "application/zip",
        "bytes_downloaded": bytes_downloaded,
        "checksum_sha256": checksum_sha256,
        "status": status,
        "error_message": error_message,
        "metadata": Jsonb(metadata or {}),
    }
    if conn is not None:
        # An explicit transaction keeps the lock alive for autocommit callers;
        # nested transactions preserve the caller's commit/rollback boundary.
        if not conn.autocommit and conn.info.transaction_status == TransactionStatus.IDLE:
            # Establish the normal implicit caller transaction before the savepoint.
            # Otherwise transaction() would commit an idle caller's work on exit.
            conn.execute("SELECT 1")
        with conn.transaction(), conn.cursor() as cur:
            cur.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                (dataset_id + "\x1f" + artifact_key,),
            )
            cur.execute(_query("get_artifact"), {**params, "version": None})
            latest = cur.fetchone()
            params["action"] = _artifact_action(latest, checksum_sha256, status, local_path)
            cur.execute(_query("register_artifact"), params)
            return dict(cur.fetchone())

    table = artifact_table()
    statement = insert(table).values(
        dataset_id=dataset_id,
        remote_url=remote_url,
        local_path=local_path,
        artifact_key=artifact_key,
        period_start=period_start,
        period_end=period_end,
        content_type=content_type or "application/zip",
        bytes_downloaded=bytes_downloaded,
        checksum_sha256=checksum_sha256,
        status=status,
        error_message=error_message,
        downloaded_at=func.now() if status == "downloaded" else None,
        metadata=metadata or {},
    )
    with session() as active_session:
        # Lock before looking for a row: row locks alone cannot serialize v1 creation.
        active_session.execute(
            select(
                func.pg_advisory_xact_lock(
                    func.hashtextextended(dataset_id + "\x1f" + artifact_key, 0)
                )
            )
        )
        latest = (
            active_session.execute(
                select(table)
                .where(
                    table.c.dataset_id == dataset_id,
                    table.c.artifact_key == artifact_key,
                )
                .order_by(table.c.artifact_version.desc())
                .limit(1)
                .with_for_update()
            )
            .mappings()
            .one_or_none()
        )
        action = _artifact_action(latest, checksum_sha256, status, local_path)
        if latest is None:
            row = (
                active_session.execute(
                    statement.values(artifact_version=1).returning(table)
                )
                .mappings()
                .one()
            )
        elif action == "promote":
            # A failed/planned attempt is provisional and may be promoted in place.
            row = (
                active_session.execute(
                    update(table)
                    .where(table.c.artifact_id == latest["artifact_id"])
                    .values(
                        remote_url=remote_url,
                        local_path=local_path,
                        period_start=period_start,
                        period_end=period_end,
                        content_type=content_type or latest["content_type"],
                        bytes_downloaded=bytes_downloaded,
                        checksum_sha256=checksum_sha256,
                        status=status,
                        error_message=error_message,
                        downloaded_at=func.now()
                        if status == "downloaded"
                        else latest["downloaded_at"],
                        metadata=(latest["metadata"] or {}) | (metadata or {}),
                    )
                    .returning(table)
                )
                .mappings()
                .one()
            )
        elif action == "retry":
            # A retry can update lifecycle metadata, never the retained bytes/path.
            row = (
                active_session.execute(
                    update(table)
                    .where(table.c.artifact_id == latest["artifact_id"])
                    .values(
                        remote_url=remote_url,
                        status=status,
                        error_message=error_message,
                        downloaded_at=func.now()
                        if status == "downloaded"
                        else latest["downloaded_at"],
                        metadata=(latest["metadata"] or {}) | (metadata or {}),
                    )
                    .returning(table)
                )
                .mappings()
                .one()
            )
        else:
            # Differing content (including A→B→A) is always a fresh version.
            row = (
                active_session.execute(
                    statement.values(
                        artifact_version=latest["artifact_version"] + 1
                    ).returning(table)
                )
                .mappings()
                .one()
            )
    return dict(row)


def get_artifact(
    dataset_id: str,
    artifact_key: str,
    conn: Any | None = None,
    *,
    version: int | None = None,
) -> dict[str, Any] | None:
    """Retrieve an existing artifact record by dataset_id and artifact_key."""
    if conn is not None:
        with conn.cursor() as cur:
            cur.execute(
                _query("get_artifact"),
                {"dataset_id": dataset_id, "artifact_key": artifact_key, "version": version},
            )
            row = cur.fetchone()
            return dict(row) if row else None

    table = artifact_table()
    with session() as active_session:
        row = active_session.execute(
            select(
                table.c.artifact_id,
                table.c.dataset_id,
                table.c.remote_url,
                table.c.local_path,
                table.c.artifact_key,
                table.c.artifact_version,
                table.c.status,
                table.c.checksum_sha256,
                table.c.metadata,
            ).where(
                table.c.dataset_id == dataset_id,
                table.c.artifact_key == artifact_key,
                table.c.artifact_version == version if version is not None else True,
            ).order_by(table.c.artifact_version.desc())
        ).mappings().first()
    return dict(row) if row else None


def loaded_artifact_members(artifact_id: str, conn: Any | None = None) -> set[str]:
    """Return fully persisted XML member names for a GovInfo archive artifact."""
    params = {"artifact_id": artifact_id}
    if conn is not None:
        with conn.cursor() as cur:
            cur.execute(_query("loaded_artifact_members"), params)
            return {row["source_member"] for row in cur.fetchall()}

    table = bill_identifier_table()
    with session() as active_session:
        return set(
            active_session.scalars(
                select(table.c.metadata["member_name"].astext).where(
                    table.c.namespace == "govinfo.package",
                    table.c.source_artifact_id == artifact_id,
                    table.c.metadata.op("?")("member_name"),
                )
            )
        )


def sync_openstates_federal_people(conn: Any) -> dict[str, int]:
    """Seed canonical people and identifiers from the read-only OpenStates baseline.

    A person is found by any identifier OpenStates asserts (its OCD id and the BioGuide
    and other ids it lists), so loading legislators first never creates a duplicate.
    """
    counts = {"people": 0, "people_created": 0, "identifiers": 0, "identifier_conflicts": 0}
    exceptions = load_same_person()
    with conn.cursor() as cur:
        cur.execute(_query("openstates_federal_people"))
        people = cur.fetchall()
        for person in people:
            cur.execute(_query("openstates_person_identifiers"), {"ocd_id": person["ocd_id"]})
            identifiers = [("ocd", person["ocd_id"])] + [
                (row["namespace"], row["external_id"])
                for row in cur.fetchall()
                if row["namespace"] != "ocd"
            ]
            result = resolve_person(
                cur,
                identifiers,
                dataset_id="openstates.legislation",
                subject=f"ocd:{person['ocd_id']}",
                new_person={
                    "full_name": person["name"],
                    "given_name": person["given_name"],
                    "family_name": person["family_name"],
                    "metadata": {
                        "canonical_baseline": "openstates",
                        "openstates_ocd_id": person["ocd_id"],
                        "openstates_extras": person["extras"] or {},
                    },
                },
                exceptions=exceptions,
            )
            if result["person_id"] is None:
                counts["identifier_conflicts"] += 1
                continue
            counts["people"] += 1
            counts["people_created"] += result["outcome"] == "created"
            counts["identifiers"] += result["attached"]
    return counts


def resolve_bill_sponsorship_people(conn: Any | None = None) -> int:
    """Link unresolved bill sponsorships to canonical people by stable identifier."""
    if conn is None:
        sponsorship = bill_sponsorship_table()
        identifier = person_identifier_table()
        person_id = (
            select(identifier.c.person_id)
            .where(
                identifier.c.namespace == sponsorship.c.member_namespace,
                identifier.c.external_id == sponsorship.c.member_external_id,
            )
            .scalar_subquery()
        )
        statement = (
            sponsorship.update()
            .where(
                sponsorship.c.person_id.is_(None),
                person_id.is_not(None),
            )
            .values(person_id=person_id)
            .returning(sponsorship.c.bill_sponsorship_id)
        )
        with session() as active_session:
            return len(active_session.execute(statement).all())
    with conn.cursor() as cur:
        cur.execute(_query("resolve_bill_sponsorship_people"))
        return len(cur.fetchall())


def upsert_congress_person(member: dict[str, Any], conn: Any | None = None) -> str | None:
    """Find or create a Congress.gov member by BioGuide id; ``None`` when it conflicts.

    Runs the same any-identifier resolution as the other person writers. A conflict is
    recorded in ``ingest.identity_conflict`` and nothing else is written.
    """
    bioguide_id = member.get("bioguideId")
    if not bioguide_id:
        raise ValueError("Congress.gov member is missing bioguideId")
    full_name = member.get("directOrderName") or member.get("name") or bioguide_id
    new_person = {
        "full_name": full_name,
        "given_name": member.get("firstName"),
        "family_name": member.get("lastName"),
        "metadata": {"congress_gov_member": member},
    }

    def resolve(active: Any) -> str | None:
        with active.cursor() as cur:
            result = resolve_person(
                cur,
                [("bioguide", bioguide_id)],
                dataset_id="congress.legislation",
                subject=f"bioguide:{bioguide_id}",
                new_person=new_person,
            )
        person_id = result["person_id"]
        return None if person_id is None else str(person_id)

    if conn is not None:
        return resolve(conn)
    with connect() as own:
        person_id = resolve(own)
        own.commit()
    return person_id


def sync_openstates_federal_organizations(conn: Any) -> int:
    """Seed canonical federal organizations from the read-only OpenStates baseline."""
    with conn.cursor() as cur:
        cur.execute(_query("openstates_federal_organizations"))
        organizations = cur.fetchall()
        for organization in organizations:
            cur.execute(
                _query("upsert_organization_by_ocd"),
                {
                    "ocd_id": organization["ocd_id"],
                    "organization_type": organization["classification"],
                    "name": organization["name"],
                    "metadata": Jsonb(
                        {
                            "canonical_baseline": "openstates",
                            "openstates_ocd_id": organization["ocd_id"],
                            "parent_ocd_id": organization["parent_id"],
                            "openstates_extras": organization["extras"] or {},
                        }
                    ),
                },
            )
            assert cur.fetchone() is not None
    return len(organizations)


def load_openstates_votes(
    congress: int,
    limit: int,
    artifact_id: str,
    conn: Any,
    after_ocd_id: str | None = None,
) -> dict[str, Any]:
    """Load a bounded OpenStates congressional vote batch using stable OCD keys."""
    counts: dict[str, Any] = {
        "roll_calls": 0,
        "member_votes": 0,
        "unresolved_people": 0,
        "unresolved_voter_ids": [],
        "last_ocd_id": after_ocd_id,
    }
    with conn.cursor() as cur:
        cur.execute(
            _query("openstates_vote_events"),
            {"congress": str(congress), "limit": limit, "after_ocd_id": after_ocd_id},
        )
        for vote in cur.fetchall():
            counts["last_ocd_id"] = vote["ocd_id"]
            cur.execute(
                _query("find_organization_by_identifier"),
                {"namespace": "ocd", "external_id": vote["organization_id"]},
            )
            organization = cur.fetchone()
            cur.execute(
                _query("upsert_openstates_roll_call"),
                {
                    "congress": str(congress),
                    "chamber": "house" if "lower" in vote["identifier"] else "senate",
                    "external_id": vote["identifier"],
                    "occurred_at": vote["start_date"],
                    "question": vote["motion_text"],
                    "result": vote["result"],
                    "metadata": Jsonb(
                        {
                            "source": "openstates",
                            "ocd_id": vote["ocd_id"],
                            "source_bill_ocd_id": vote["bill_id"],
                        }
                    ),
                    "ocd_id": vote["ocd_id"],
                    "organization_id": organization["organization_id"]
                    if organization
                    else None,
                },
            )
            roll_call = cur.fetchone()
            counts["roll_calls"] += 1
            cur.execute(
                _query("openstates_person_votes"), {"vote_ocd_id": vote["ocd_id"]}
            )
            for position in cur.fetchall():
                cur.execute(
                    _query("find_person_by_identifier"),
                    {"namespace": "ocd", "external_id": position["voter_id"]},
                )
                person = cur.fetchone()
                if not person:
                    counts["unresolved_people"] += 1
                    counts["unresolved_voter_ids"].append(position["voter_id"])
                    continue
                cur.execute(
                    _query("upsert_member_vote"),
                    {
                        "roll_call_id": roll_call["roll_call_id"],
                        "person_id": person["person_id"],
                        "position": position["option"],
                        "source_artifact_id": artifact_id,
                    },
                )
                counts["member_votes"] += 1
    return counts


def ensure_us_legislative_session(
    congress: int,
    source_artifact_id: str | None = None,
    source_payload_id: str | None = None,
    metadata: dict[str, Any] | None = None,
    conn: Any | None = None,
) -> str:
    """Ensure US jurisdiction and legislative session with explicit source lineage."""
    if source_artifact_id is None and source_payload_id is None:
        raise ValueError(
            "Legislative session requires source_artifact_id or source_payload_id lineage"
        )
    jurisdiction_id = "ocd-jurisdiction/country:us/government"
    identifier = str(congress)
    session_metadata = {"congress": congress, "country": "us"}
    if metadata:
        session_metadata.update(metadata)

    def _ensure(active_conn: Any) -> str:
        with active_conn.cursor() as cur:
            cur.execute(
                _query("ensure_jurisdiction"),
                {
                    "jurisdiction_id": jurisdiction_id,
                    "name": "United States Congress",
                    "classification": "government",
                    "metadata": Jsonb({"country": "us"}),
                },
            )
            cur.execute(
                _query("ensure_legislative_session"),
                {
                    "jurisdiction_id": jurisdiction_id,
                    "identifier": identifier,
                    "name": f"{congress}th Congress",
                    "classification": "congress",
                    "active": congress >= 119,
                    "source_artifact_id": source_artifact_id,
                    "source_payload_id": source_payload_id,
                    "metadata": Jsonb(session_metadata),
                },
            )
            row = cur.fetchone()
            assert row is not None
            return str(row["legislative_session_id"])

    if conn is not None:
        return _ensure(conn)

    jurisdiction = jurisdiction_table()
    legislative_session = legislative_session_table()
    jurisdiction_statement = insert(jurisdiction).values(
        jurisdiction_id=jurisdiction_id,
        name="United States Congress",
        classification="government",
        metadata={"country": "us"},
    )
    session_statement = insert(legislative_session).values(
        jurisdiction_id=jurisdiction_id,
        identifier=identifier,
        name=f"{congress}th Congress",
        classification="congress",
        active=congress >= 119,
        source_artifact_id=source_artifact_id,
        source_payload_id=source_payload_id,
        metadata=session_metadata,
    )
    with session() as active_session:
        active_session.execute(
            jurisdiction_statement.on_conflict_do_update(
                index_elements=(jurisdiction.c.jurisdiction_id,),
                set_={
                    "name": jurisdiction_statement.excluded.name,
                    "classification": jurisdiction_statement.excluded.classification,
                    "metadata": jurisdiction.c.metadata.op("||")(
                        jurisdiction_statement.excluded.metadata
                    ),
                },
            )
        )
        result = active_session.execute(
            session_statement.on_conflict_do_update(
                index_elements=(legislative_session.c.jurisdiction_id, legislative_session.c.identifier),
                set_={
                    "name": func.coalesce(session_statement.excluded.name, legislative_session.c.name),
                    "classification": func.coalesce(
                        session_statement.excluded.classification, legislative_session.c.classification
                    ),
                    "active": func.coalesce(session_statement.excluded.active, legislative_session.c.active),
                    "source_artifact_id": func.coalesce(
                        session_statement.excluded.source_artifact_id,
                        legislative_session.c.source_artifact_id,
                    ),
                    "source_payload_id": func.coalesce(
                        session_statement.excluded.source_payload_id,
                        legislative_session.c.source_payload_id,
                    ),
                    "metadata": legislative_session.c.metadata.op("||")(
                        session_statement.excluded.metadata
                    ),
                },
            ).returning(legislative_session.c.legislative_session_id)
        ).scalar_one()
    return str(result)


def bill_type_and_number(bill: ElementTree.Element) -> tuple[str | None, str | None]:
    """A ``<bill>``'s type and number text.

    Most GovInfo files spell them ``<type>`` and ``<number>``; a few (for example the
    House's reserved numbers, such as H.R. 9 in the 117th) use ``<billType>`` and
    ``<billNumber>`` and are otherwise identical.
    """
    return (
        bill.findtext("type") or bill.findtext("billType"),
        bill.findtext("number") or bill.findtext("billNumber"),
    )


def parse_billstatus_xml(
    content: bytes | str, member_name: str | None = None
) -> dict[str, Any]:
    """Parse one GovInfo BILLSTATUS XML member into structured dictionary representation."""
    if isinstance(content, str):
        content = content.encode("utf-8")
    root = ElementTree.fromstring(content)
    bill = root.find("bill") if root.tag == "billStatus" else root
    if bill is None:
        raise ValueError("Invalid BILLSTATUS XML: missing <bill> element")

    congress_text = bill.findtext("congress")
    raw_type, raw_number = bill_type_and_number(bill)
    bill_type = (raw_type or "").strip().lower()
    bill_number = (raw_number or "").strip()

    if not congress_text or not bill_type or not bill_number:
        raise ValueError("Missing core bill identity in BILLSTATUS XML")

    congress = int(congress_text)

    title = bill.findtext("title")
    if not title:
        for t_item in bill.findall("./titles/item"):
            t_val = t_item.findtext("title")
            if t_val:
                title = t_val
                break

    introduced_date = _text_or_none(bill.findtext("introducedDate"))
    latest = bill.find("latestAction")
    latest_action_date = (
        _text_or_none(latest.findtext("actionDate")) if latest is not None else None
    )
    latest_action = (
        _text_or_none(latest.findtext("text")) if latest is not None else None
    )

    identifiers = [
        {
            "namespace": "us.bill",
            "external_id": f"{congress}-{bill_type}-{bill_number}",
            "source_url": None,
            "metadata": {
                "congress": congress,
                "type": bill_type,
                "number": bill_number,
            },
        }
    ]
    if member_name:
        package_id = member_name.rsplit(".", 1)[0]
        identifiers.append(
            {
                "namespace": "govinfo.package",
                "external_id": package_id,
                "source_url": f"https://www.govinfo.gov/bulkdata/BILLSTATUS/{congress}/{bill_type}/{package_id}.xml",
                "metadata": {"member_name": member_name},
            }
        )

    sponsorships = []
    for sp in bill.findall("./sponsors/item"):
        bioguide = sp.findtext("bioguideId")
        if bioguide:
            sponsorships.append(
                {
                    "member_namespace": "bioguide",
                    "member_external_id": bioguide.strip(),
                    "role": "sponsor",
                    "source_member": member_name,
                    "metadata": {
                        "full_name": sp.findtext("fullName"),
                        "party": sp.findtext("party"),
                        "state": sp.findtext("state"),
                        "district": sp.findtext("district"),
                    },
                }
            )
    for cosp in bill.findall("./cosponsors/item"):
        bioguide = cosp.findtext("bioguideId")
        if bioguide:
            sponsorships.append(
                {
                    "member_namespace": "bioguide",
                    "member_external_id": bioguide.strip(),
                    "role": "cosponsor",
                    "source_member": member_name,
                    "metadata": {
                        "full_name": cosp.findtext("fullName"),
                        "sponsorship_date": cosp.findtext("sponsorshipDate"),
                        "is_original": cosp.findtext("isOriginalCosponsor"),
                    },
                }
            )

    actions = []
    for ordinal, act in enumerate(bill.findall("./actions/item"), start=1):
        action_date = _text_or_none(act.findtext("actionDate"))
        desc = act.findtext("text") or ""
        act_type = act.findtext("type")
        act_code = act.findtext("actionCode")
        classification = [c for c in (act_type, act_code) if c]
        actions.append(
            {
                "action_date": action_date,
                "description": desc,
                "classification": classification if classification else None,
                "source_ordinal": ordinal,
                "source_member": member_name,
                "metadata": {
                    "action_code": act_code,
                    "action_type": act_type,
                },
            }
        )

    committees = []
    for comm in bill.findall("./committees/item"):
        code = comm.findtext("systemCode")
        if code:
            committees.append(
                {
                    "namespace": "congress.gov.committee",
                    "external_id": code.strip().lower(),
                    "name": comm.findtext("name"),
                    "chamber": comm.findtext("chamber"),
                    "source_member": member_name,
                    "metadata": {"type": comm.findtext("type")},
                }
            )

    subjects = []
    policy = bill.findtext("./policyArea/name")
    if policy:
        subjects.append(
            {
                "namespace": "congress.gov.subject",
                "external_id": policy.strip().lower().replace(" ", "-"),
                "label": policy.strip(),
                "source_member": member_name,
                "metadata": {"kind": "policy_area"},
            }
        )
    for subj in bill.findall("./subjects/legislativeSubjects/item"):
        s_name = subj.findtext("name")
        if s_name:
            subjects.append(
                {
                    "namespace": "congress.gov.subject",
                    "external_id": s_name.strip().lower().replace(" ", "-"),
                    "label": s_name.strip(),
                    "source_member": member_name,
                    "metadata": {"kind": "legislative_subject"},
                }
            )

    documents = []
    for doc in bill.findall("./textVersions/item"):
        doc_type = doc.findtext("type") or "text_version"
        pub_date = _text_or_none(doc.findtext("date"))
        formats = doc.findall("./formats/item")
        url = formats[0].findtext("url") if formats else None
        if not url:
            url = f"https://www.govinfo.gov/bulkdata/BILLSTATUS/{congress}/{bill_type}/{member_name or 'doc'}"
        documents.append(
            {
                "document_type": doc_type,
                "version_code": doc_type,
                "title": doc_type,
                "published_at": pub_date,
                "source_url": url,
                "source_member": member_name,
                "metadata": {},
            }
        )

    return {
        "congress": congress,
        "bill_type": bill_type,
        "bill_number": bill_number,
        "title": title,
        "introduced_date": introduced_date,
        "latest_action_date": latest_action_date,
        "latest_action": latest_action,
        "identifiers": identifiers,
        "sponsorships": sponsorships,
        "actions": actions,
        "committees": committees,
        "subjects": subjects,
        "documents": documents,
        "summaries": billstatus_sections.summaries(bill, member_name),
        "laws": billstatus_sections.laws(bill, member_name),
        "related_bills": billstatus_sections.related_bills(bill, member_name),
        "amendments": billstatus_sections.amendments(bill, member_name),
        "cbo_cost_estimates": billstatus_sections.cbo_cost_estimates(bill, member_name),
        # everything the file says, so a field nobody has modelled yet is still stored
        "record": xml_to_record(root),
    }


def save_billstatus_bill(
    bill_data: dict[str, Any],
    legislative_session_id: str,
    source_artifact_id: str | None = None,
    source_payload_id: str | None = None,
    source_member: str | None = None,
    conn: Any | None = None,
    person_cache: dict[tuple[str, str], str | None] | None = None,
    source_name: str = "govinfo_billstatus",
) -> str:
    """Upsert core.bill plus identifiers, actions, sponsorships, committees, subjects, and documents.

    ``person_cache`` (connection path only) memoizes sponsor identifier lookups for a
    caller that loads many bills in one run: the same members sponsor thousands of them.
    The promoted sections and the full ``record`` are written on the connection path only.
    """
    if source_artifact_id is None and source_payload_id is None:
        raise ValueError(
            "Persistence requires source_artifact_id or source_payload_id lineage"
        )

    if conn is None:
        return _save_billstatus_bill_sqlalchemy(
            bill_data,
            legislative_session_id,
            source_artifact_id=source_artifact_id,
            source_payload_id=source_payload_id,
            source_member=source_member,
        )

    def _execute(c: Any) -> str:
        with c.cursor() as cur:
            cur.execute(
                _query("upsert_bill"),
                {
                    "jurisdiction": "us",
                    "legislative_session": str(bill_data["congress"]),
                    "bill_type": bill_data["bill_type"],
                    "bill_number": bill_data["bill_number"],
                    "title": bill_data.get("title"),
                    "introduced_date": bill_data.get("introduced_date"),
                    "latest_action_date": bill_data.get("latest_action_date"),
                    "latest_action": bill_data.get("latest_action"),
                    "metadata": Jsonb({"source": source_name}),
                    "legislative_session_id": legislative_session_id,
                    "ocd_id": None,
                },
            )
            row = cur.fetchone()
            assert row is not None
            bill_id = str(row["bill_id"])

            for item in bill_data.get("identifiers", []):
                cur.execute(
                    _query("upsert_bill_identifier"),
                    {
                        "bill_id": bill_id,
                        "namespace": item["namespace"],
                        "external_id": item["external_id"],
                        "source_artifact_id": source_artifact_id,
                        "source_payload_id": source_payload_id,
                        "source_url": item.get("source_url"),
                        "metadata": Jsonb(item.get("metadata", {})),
                    },
                )

            for act in bill_data.get("actions", []):
                cur.execute(
                    _query("upsert_bill_action"),
                    {
                        "bill_id": bill_id,
                        "action_date": act.get("action_date"),
                        "description": act["description"],
                        "classification": act.get("classification"),
                        "source_artifact_id": source_artifact_id,
                        "source_payload_id": source_payload_id,
                        "source_member": source_member or act.get("source_member"),
                        "source_ordinal": act.get("source_ordinal"),
                        "metadata": Jsonb(act.get("metadata", {})),
                    },
                )

            for sp in bill_data.get("sponsorships", []):
                lookup = (sp["member_namespace"], sp["member_external_id"])
                if person_cache is not None and lookup in person_cache:
                    person_id = person_cache[lookup]
                else:
                    cur.execute(
                        _query("find_person_by_identifier"),
                        {"namespace": lookup[0], "external_id": lookup[1]},
                    )
                    p_row = cur.fetchone()
                    person_id = str(p_row["person_id"]) if p_row else None
                    if person_cache is not None:
                        person_cache[lookup] = person_id

                cur.execute(
                    _query("upsert_bill_sponsorship"),
                    {
                        "bill_id": bill_id,
                        "person_id": person_id,
                        "member_namespace": sp["member_namespace"],
                        "member_external_id": sp["member_external_id"],
                        "role": sp["role"],
                        "source_artifact_id": source_artifact_id,
                        "source_payload_id": source_payload_id,
                        "source_member": source_member or sp.get("source_member"),
                        "metadata": Jsonb(sp.get("metadata", {})),
                    },
                )

            for comm in bill_data.get("committees", []):
                cur.execute(
                    _query("upsert_bill_committee"),
                    {
                        "bill_id": bill_id,
                        "namespace": comm.get("namespace", "congress.gov.committee"),
                        "external_id": comm["external_id"],
                        "name": comm.get("name"),
                        "chamber": comm.get("chamber"),
                        "source_artifact_id": source_artifact_id,
                        "source_payload_id": source_payload_id,
                        "source_member": source_member or comm.get("source_member"),
                        "metadata": Jsonb(comm.get("metadata", {})),
                    },
                )

            for subj in bill_data.get("subjects", []):
                cur.execute(
                    _query("upsert_bill_subject"),
                    {
                        "bill_id": bill_id,
                        "namespace": subj.get("namespace", "congress.gov.subject"),
                        "external_id": subj["external_id"],
                        "label": subj["label"],
                        "source_artifact_id": source_artifact_id,
                        "source_payload_id": source_payload_id,
                        "source_member": source_member or subj.get("source_member"),
                        "metadata": Jsonb(subj.get("metadata", {})),
                    },
                )

            for doc in bill_data.get("documents", []):
                cur.execute(
                    _query("upsert_document"),
                    {
                        "document_type": "bill_text_version",
                        "source_key": doc["source_url"],
                        "title": doc.get("title"),
                        "published_at": doc.get("published_at"),
                        "canonical_url": doc["source_url"],
                        "artifact_id": source_artifact_id,
                        "source_payload_id": source_payload_id,
                        "metadata": Jsonb(
                            {
                                **doc.get("metadata", {}),
                                "version_code": doc.get("version_code"),
                                "source_member": source_member
                                or doc.get("source_member"),
                            }
                        ),
                    },
                )
                document = cur.fetchone()
                assert document is not None
                cur.execute(
                    _query("upsert_bill_document"),
                    {
                        "bill_id": bill_id,
                        "document_id": document["document_id"],
                        "relation": "text_version",
                    },
                )

            if source_artifact_id is not None:
                _save_promoted_sections(cur, bill_id, bill_data, source_artifact_id, source_member)
            return bill_id

    return _execute(conn)


# Promoted section -> (bill_data key, upsert query, Jsonb columns).
_PROMOTED_SECTIONS = (
    ("summaries", "upsert_bill_summary", ()),
    ("laws", "upsert_bill_law", ()),
    ("related_bills", "upsert_bill_related_bill", ("relationships",)),
    ("amendments", "upsert_bill_amendment", ("metadata",)),
    ("cbo_cost_estimates", "upsert_bill_cbo_cost_estimate", ()),
)


def _save_promoted_sections(
    cur: Any,
    bill_id: str,
    bill_data: dict[str, Any],
    source_artifact_id: str,
    source_member: str | None,
) -> None:
    """Write the promoted sections and then the full record (Story 9.5b).

    The record row goes last: its presence marks the member as fully loaded, so a resume never
    treats a half-written bill as done. Callers that hand in no ``record`` (hand-built
    ``bill_data``) get the promoted rows only.
    """
    for key, query, json_columns in _PROMOTED_SECTIONS:
        for row in bill_data.get(key, []):
            params = {
                **row,
                "bill_id": bill_id,
                "source_artifact_id": source_artifact_id,
                "source_member": source_member or row.get("source_member"),
            }
            for column in json_columns:
                params[column] = Jsonb(params[column])
            cur.execute(_query(query), params)
    record = bill_data.get("record")
    if record is not None:
        cur.execute(
            _query("upsert_bill_source_record"),
            {
                "bill_id": bill_id,
                "source_artifact_id": source_artifact_id,
                "source_member": source_member,
                "record": Jsonb(record),
                "record_sha256": record_sha256(record),
            },
        )


def _save_billstatus_bill_sqlalchemy(
    bill_data: dict[str, Any],
    legislative_session_id: str,
    *,
    source_artifact_id: str | None,
    source_payload_id: str | None,
    source_member: str | None,
) -> str:
    """Persist a BILLSTATUS graph through typed legacy mappings in one transaction."""
    bill = bill_table()
    identifier = bill_identifier_table()
    action = bill_action_table()
    sponsorship = bill_sponsorship_table()
    committee = bill_committee_table()
    subject = bill_subject_table()
    person_identifier = person_identifier_table()
    document = document_table()
    bill_document = bill_document_table()

    bill_insert = insert(bill).values(
        jurisdiction="us",
        legislative_session=str(bill_data["congress"]),
        bill_type=bill_data["bill_type"],
        bill_number=bill_data["bill_number"],
        title=bill_data.get("title"),
        introduced_date=bill_data.get("introduced_date"),
        latest_action_date=bill_data.get("latest_action_date"),
        latest_action=bill_data.get("latest_action"),
        metadata={"source": "govinfo_billstatus"},
        legislative_session_id=legislative_session_id,
        ocd_id=None,
    )
    bill_statement = bill_insert.on_conflict_do_update(
        index_elements=(
            bill.c.jurisdiction,
            bill.c.legislative_session,
            bill.c.bill_type,
            bill.c.bill_number,
        ),
        set_={
            "title": func.coalesce(bill_insert.excluded.title, bill.c.title),
            "introduced_date": func.coalesce(
                bill_insert.excluded.introduced_date, bill.c.introduced_date
            ),
            "latest_action_date": func.coalesce(
                bill_insert.excluded.latest_action_date, bill.c.latest_action_date
            ),
            "latest_action": func.coalesce(
                bill_insert.excluded.latest_action, bill.c.latest_action
            ),
            "metadata": bill.c.metadata.op("||")(bill_insert.excluded.metadata),
            "legislative_session_id": func.coalesce(
                bill_insert.excluded.legislative_session_id, bill.c.legislative_session_id
            ),
            "ocd_id": func.coalesce(bill_insert.excluded.ocd_id, bill.c.ocd_id),
        },
    ).returning(bill.c.bill_id)

    with session() as active_session:
        bill_id = active_session.execute(bill_statement).scalar_one()
        for item in bill_data.get("identifiers", []):
            statement = insert(identifier).values(
                bill_id=bill_id,
                namespace=item["namespace"],
                external_id=item["external_id"],
                source_artifact_id=source_artifact_id,
                source_payload_id=source_payload_id,
                source_url=item.get("source_url"),
                metadata=item.get("metadata", {}),
            )
            active_session.execute(
                statement.on_conflict_do_update(
                    index_elements=(identifier.c.namespace, identifier.c.external_id),
                    set_={
                        "bill_id": bill_id,
                        "source_artifact_id": func.coalesce(
                            statement.excluded.source_artifact_id, identifier.c.source_artifact_id
                        ),
                        "source_payload_id": func.coalesce(
                            statement.excluded.source_payload_id, identifier.c.source_payload_id
                        ),
                        "source_url": func.coalesce(
                            statement.excluded.source_url, identifier.c.source_url
                        ),
                        "metadata": identifier.c.metadata.op("||")(statement.excluded.metadata),
                    },
                )
            )
        for item in bill_data.get("actions", []):
            member = source_member or item.get("source_member")
            statement = insert(action).values(
                bill_id=bill_id,
                action_date=item.get("action_date"),
                description=item["description"],
                classification=item.get("classification"),
                source_artifact_id=source_artifact_id,
                source_payload_id=source_payload_id,
                source_member=member,
                source_ordinal=item.get("source_ordinal"),
                metadata=item.get("metadata", {}),
            )
            active_session.execute(
                statement.on_conflict_do_update(
                    index_elements=(
                        action.c.bill_id,
                        action.c.source_artifact_id,
                        action.c.source_member,
                        action.c.source_ordinal,
                    ),
                    index_where=action.c.source_artifact_id.is_not(None),
                    set_={
                        "action_date": func.coalesce(statement.excluded.action_date, action.c.action_date),
                        "description": statement.excluded.description,
                        "classification": func.coalesce(statement.excluded.classification, action.c.classification),
                        "source_payload_id": func.coalesce(
                            statement.excluded.source_payload_id, action.c.source_payload_id
                        ),
                        "metadata": action.c.metadata.op("||")(statement.excluded.metadata),
                    },
                )
            )
        for item in bill_data.get("sponsorships", []):
            person_id = active_session.execute(
                select(person_identifier.c.person_id).where(
                    person_identifier.c.namespace == item["member_namespace"],
                    person_identifier.c.external_id == item["member_external_id"],
                ).limit(1)
            ).scalar_one_or_none()
            member = source_member or item.get("source_member")
            statement = insert(sponsorship).values(
                bill_id=bill_id,
                person_id=person_id,
                member_namespace=item["member_namespace"],
                member_external_id=item["member_external_id"],
                role=item["role"],
                source_artifact_id=source_artifact_id,
                source_payload_id=source_payload_id,
                source_member=member,
                metadata=item.get("metadata", {}),
            )
            active_session.execute(
                statement.on_conflict_do_update(
                    index_elements=(
                        sponsorship.c.bill_id,
                        sponsorship.c.member_namespace,
                        sponsorship.c.member_external_id,
                        sponsorship.c.role,
                        sponsorship.c.source_artifact_id,
                        sponsorship.c.source_member,
                    ),
                    set_={
                        "person_id": func.coalesce(statement.excluded.person_id, sponsorship.c.person_id),
                        "source_payload_id": func.coalesce(
                            statement.excluded.source_payload_id, sponsorship.c.source_payload_id
                        ),
                        "metadata": sponsorship.c.metadata.op("||")(statement.excluded.metadata),
                    },
                )
            )
        for item in bill_data.get("committees", []):
            member = source_member or item.get("source_member")
            statement = insert(committee).values(
                bill_id=bill_id,
                namespace=item.get("namespace", "congress.gov.committee"),
                external_id=item["external_id"],
                name=item.get("name"),
                chamber=item.get("chamber"),
                source_artifact_id=source_artifact_id,
                source_payload_id=source_payload_id,
                source_member=member,
                metadata=item.get("metadata", {}),
            )
            active_session.execute(
                statement.on_conflict_do_update(
                    index_elements=(
                        committee.c.bill_id,
                        committee.c.namespace,
                        committee.c.external_id,
                        committee.c.source_artifact_id,
                        committee.c.source_member,
                    ),
                    set_={
                        "name": func.coalesce(statement.excluded.name, committee.c.name),
                        "chamber": func.coalesce(statement.excluded.chamber, committee.c.chamber),
                        "source_payload_id": func.coalesce(
                            statement.excluded.source_payload_id, committee.c.source_payload_id
                        ),
                        "metadata": committee.c.metadata.op("||")(statement.excluded.metadata),
                    },
                )
            )
        for item in bill_data.get("subjects", []):
            member = source_member or item.get("source_member")
            statement = insert(subject).values(
                bill_id=bill_id,
                namespace=item.get("namespace", "congress.gov.subject"),
                external_id=item["external_id"],
                label=item["label"],
                source_artifact_id=source_artifact_id,
                source_payload_id=source_payload_id,
                source_member=member,
                metadata=item.get("metadata", {}),
            )
            active_session.execute(
                statement.on_conflict_do_update(
                    index_elements=(
                        subject.c.bill_id,
                        subject.c.namespace,
                        subject.c.external_id,
                        subject.c.source_artifact_id,
                        subject.c.source_member,
                    ),
                    set_={
                        "label": statement.excluded.label,
                        "source_payload_id": func.coalesce(
                            statement.excluded.source_payload_id, subject.c.source_payload_id
                        ),
                        "metadata": subject.c.metadata.op("||")(statement.excluded.metadata),
                    },
                )
            )
        for item in bill_data.get("documents", []):
            statement = insert(document).values(
                document_type="bill_text_version",
                source_key=item["source_url"],
                title=item.get("title"),
                published_at=item.get("published_at"),
                canonical_url=item["source_url"],
                artifact_id=source_artifact_id,
                source_payload_id=source_payload_id,
                metadata={
                    **item.get("metadata", {}),
                    "version_code": item.get("version_code"),
                    "source_member": source_member or item.get("source_member"),
                },
            )
            document_id = active_session.execute(
                statement.on_conflict_do_update(
                    index_elements=(document.c.document_type, document.c.source_key),
                    set_={
                        "title": func.coalesce(statement.excluded.title, document.c.title),
                        "published_at": func.coalesce(
                            statement.excluded.published_at, document.c.published_at
                        ),
                        "metadata": document.c.metadata.op("||")(statement.excluded.metadata),
                    },
                ).returning(document.c.document_id)
            ).scalar_one()
            active_session.execute(
                insert(bill_document)
                .values(bill_id=bill_id, document_id=document_id, relation="text_version")
                .on_conflict_do_nothing()
            )
    return str(bill_id)
