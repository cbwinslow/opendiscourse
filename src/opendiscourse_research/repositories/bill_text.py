"""SQL for the GovInfo BILLS text Connector: resume, join, replace-on-refresh."""

from __future__ import annotations

from functools import cache
from hashlib import sha256
from pathlib import Path
from typing import Any
from uuid import UUID

from psycopg.types.json import Jsonb

from ..ingestion.bill_text_parse import BillText

_QUERY_ROOT = Path(__file__).resolve().parents[3] / "sql" / "query" / "billtext"
# Distinct from BILLSTATUS ``bill_text_version`` (textVersions links): this grain is one
# GovInfo BILLS XML member (congress × session × type × number × version code).
DOCUMENT_TYPE = "govinfo_bill_text"
RELATION = "text"
JURISDICTION = "us"


def document_source_key(session: int, source_member: str) -> str:
    """``core.document`` unique key: session plus filename, so two sessions cannot collide."""
    return f"{session}/{Path(source_member).name}"


@cache
def _query(name: str) -> str:
    """Read a named, version-controlled query template (once per process)."""
    return (_QUERY_ROOT / f"{name}.sql").read_text()


def loaded_members(conn: Any, artifact_id: UUID | str) -> set[str]:
    """Members of this artifact version that are loaded and attached to a ``core.bill``.

    Unknown bills (``bill_id`` NULL) are left out so a later sync can attach them.
    """
    with conn.cursor() as cur:
        cur.execute(_query("loaded_members"), {"artifact_id": artifact_id})
        return {row["source_member"] for row in cur.fetchall()}


def find_bill(conn: Any, congress: int, bill_type: str, bill_number: str) -> str | None:
    """The existing ``core.bill`` for this identity, or None. Never creates one."""
    with conn.cursor() as cur:
        cur.execute(
            _query("find_bill"),
            {
                "jurisdiction": JURISDICTION,
                "legislative_session": str(congress),
                "bill_type": bill_type,
                "bill_number": bill_number,
            },
        )
        row = cur.fetchone()
    return str(row["bill_id"]) if row else None


def supersede_records(conn: Any, members: list[str], old_artifact_ids: list[UUID]) -> int:
    """Delete older artifact versions' records for ``members``; return the count.

    The caller passes members it has just rewritten from the newer version, inside the
    same transaction, so a failure leaves the older rows in place.
    """
    if not members or not old_artifact_ids:
        return 0
    with conn.cursor() as cur:
        cur.execute(
            _query("supersede_records"),
            {"source_members": members, "old_artifact_ids": old_artifact_ids},
        )
        return cur.rowcount


def save_bill_text(
    parsed: BillText,
    *,
    session: int,
    source_artifact_id: str,
    source_member: str,
    canonical_url: str | None,
    xml_bytes: bytes,
    conn: Any,
) -> dict[str, Any]:
    """Write the lossless record and, when we hold the bill, attach the typed version.

    The record row is written last so its presence means the member is fully loaded.
    An unknown bill is stored as a record with ``bill_id`` NULL and is not attached.
    """
    bill_id = find_bill(conn, parsed.congress, parsed.bill_type, parsed.bill_number)
    document_id = None
    with conn.cursor() as cur:
        if bill_id is not None:
            cur.execute(
                _query("upsert_document"),
                {
                    "document_type": DOCUMENT_TYPE,
                    "source_key": document_source_key(session, source_member),
                    "title": parsed.title,
                    "published_at": parsed.published_at,
                    "canonical_url": canonical_url,
                    "checksum_sha256": sha256(xml_bytes).hexdigest(),
                    "artifact_id": source_artifact_id,
                    "version_code": parsed.version_code,
                    "congress": parsed.congress,
                    "session": session,
                    "bill_type": parsed.bill_type,
                    "bill_number": parsed.bill_number,
                    "source_member": source_member,
                    "metadata": Jsonb(
                        {
                            "bill_stage": parsed.bill_stage,
                            "root_tag": parsed.root_tag,
                        }
                    ),
                },
            )
            document = cur.fetchone()
            assert document is not None
            document_id = str(document["document_id"])
            cur.execute(
                _query("upsert_bill_document"),
                {"bill_id": bill_id, "document_id": document_id, "relation": RELATION},
            )
        cur.execute(
            _query("upsert_record"),
            {
                "bill_id": bill_id,
                "source_artifact_id": source_artifact_id,
                "source_member": source_member,
                "congress": parsed.congress,
                "session": session,
                "bill_type": parsed.bill_type,
                "bill_number": parsed.bill_number,
                "version_code": parsed.version_code,
                "record": Jsonb(parsed.record),
                "record_sha256": parsed.record_sha256,
            },
        )
    return {"bill_id": bill_id, "document_id": document_id, "unknown": bill_id is None}
