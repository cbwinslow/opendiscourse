"""Repository queries and persistence for deterministic federal legislation."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from xml.etree import ElementTree

from psycopg.types.json import Jsonb

from ..db import connect


_QUERY_ROOT = Path(__file__).resolve().parents[3] / "sql" / "query" / "legislation"


def _text_or_none(value: str | None) -> str | None:
    """Normalize optional XML text so blank values become database NULLs."""
    return value.strip() if value and value.strip() else None


def _query(name: str) -> str:
    """Read a named, version-controlled legislation query template."""
    return (_QUERY_ROOT / f"{name}.sql").read_text()


def bill_keys(congress: int, bill_type: str) -> set[str]:
    """Return OpenStates-compatible bill numbers for one Congress and bill type."""
    query = _query("bill_keys")
    with connect() as conn, conn.cursor() as cur:
        cur.execute(query, {"congress": str(congress), "bill_type": bill_type.lower()})
        return {row["bill_number"] for row in cur.fetchall()}


def openstates_vote_snapshot_counts(
    congresses: list[int], conn: Any
) -> dict[str, dict[str, Any]]:
    """Read source and canonical vote counts without mutating either system."""
    identifiers = [str(congress) for congress in congresses]
    result = {identifier: {"congress": int(identifier)} for identifier in identifiers}
    with conn.cursor() as cur:
        cur.execute(_query("openstates_vote_snapshot_counts"), {"congresses": identifiers})
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
) -> dict[str, Any]:
    """Register or update a local bulk artifact safely in ingest.artifact."""
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
        "metadata": Jsonb(metadata or {}),
    }
    if conn is not None:
        with conn.cursor() as cur:
            cur.execute(_query("register_artifact"), params)
            row = cur.fetchone()
            return dict(row) if row else {}

    with connect() as active_conn, active_conn.cursor() as cur:
        cur.execute(_query("register_artifact"), params)
        row = cur.fetchone()
        active_conn.commit()
        return dict(row) if row else {}


def get_artifact(
    dataset_id: str,
    artifact_key: str,
    conn: Any | None = None,
) -> dict[str, Any] | None:
    """Retrieve an existing artifact record by dataset_id and artifact_key."""
    if conn is not None:
        with conn.cursor() as cur:
            cur.execute(
                _query("get_artifact"),
                {"dataset_id": dataset_id, "artifact_key": artifact_key},
            )
            row = cur.fetchone()
            return dict(row) if row else None

    with connect() as active_conn, active_conn.cursor() as cur:
        cur.execute(
            _query("get_artifact"),
            {"dataset_id": dataset_id, "artifact_key": artifact_key},
        )
        row = cur.fetchone()
        return dict(row) if row else None


def loaded_artifact_members(artifact_id: str, conn: Any | None = None) -> set[str]:
    """Return fully persisted XML member names for a GovInfo archive artifact."""
    params = {"artifact_id": artifact_id}
    if conn is not None:
        with conn.cursor() as cur:
            cur.execute(_query("loaded_artifact_members"), params)
            return {row["source_member"] for row in cur.fetchall()}

    with connect() as active_conn, active_conn.cursor() as cur:
        cur.execute(_query("loaded_artifact_members"), params)
        return {row["source_member"] for row in cur.fetchall()}


def sync_openstates_federal_people(conn: Any) -> dict[str, int]:
    """Seed canonical people and identifiers from the read-only OpenStates baseline."""
    counts = {"people": 0, "identifiers": 0, "identifier_conflicts": 0}
    with conn.cursor() as cur:
        cur.execute(_query("openstates_federal_people"))
        people = cur.fetchall()
        for person in people:
            cur.execute(
                _query("upsert_person_by_ocd"),
                {
                    "ocd_id": person["ocd_id"],
                    "full_name": person["name"],
                    "given_name": person["given_name"],
                    "family_name": person["family_name"],
                    "metadata": Jsonb(
                        {
                            "canonical_baseline": "openstates",
                            "openstates_ocd_id": person["ocd_id"],
                            "openstates_extras": person["extras"] or {},
                        }
                    ),
                },
            )
            target = cur.fetchone()
            assert target is not None
            person_id = str(target["person_id"])
            counts["people"] += 1
            cur.execute(
                _query("openstates_person_identifiers"), {"ocd_id": person["ocd_id"]}
            )
            for identifier in cur.fetchall():
                if identifier["namespace"] == "ocd":
                    continue
                cur.execute(
                    _query("insert_person_identifier"),
                    {"person_id": person_id, **identifier},
                )
                result = cur.fetchone()
                if result is None or str(result["person_id"]) != person_id:
                    counts["identifier_conflicts"] += 1
                else:
                    counts["identifiers"] += 1
    return counts


def resolve_bill_sponsorship_people(conn: Any) -> int:
    """Link unresolved bill sponsorships to canonical people by stable identifier."""
    with conn.cursor() as cur:
        cur.execute(_query("resolve_bill_sponsorship_people"))
        return len(cur.fetchall())


def upsert_congress_person(member: dict[str, Any], conn: Any) -> str:
    """Upsert a Congress.gov member by BioGuide ID with primary-source metadata."""
    bioguide_id = member.get("bioguideId")
    if not bioguide_id:
        raise ValueError("Congress.gov member is missing bioguideId")
    full_name = member.get("directOrderName") or member.get("name") or bioguide_id
    with conn.cursor() as cur:
        cur.execute(_query("upsert_person_by_bioguide"), {
            "bioguide_id": bioguide_id,
            "full_name": full_name,
            "given_name": member.get("firstName"),
            "family_name": member.get("lastName"),
            "metadata": Jsonb({"congress_gov_member": member}),
        })
        row = cur.fetchone()
        assert row is not None
        return str(row["person_id"])


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


def load_openstates_votes(congress: int, limit: int, artifact_id: str, conn: Any, after_ocd_id: str | None = None) -> dict[str, Any]:
    """Load a bounded OpenStates congressional vote batch using stable OCD keys."""
    counts: dict[str, Any] = {"roll_calls": 0, "member_votes": 0, "unresolved_people": 0, "last_ocd_id": after_ocd_id}
    with conn.cursor() as cur:
        cur.execute(_query("openstates_vote_events"), {"congress": str(congress), "limit": limit, "after_ocd_id": after_ocd_id})
        for vote in cur.fetchall():
            counts["last_ocd_id"] = vote["ocd_id"]
            cur.execute(_query("find_organization_by_identifier"), {"namespace": "ocd", "external_id": vote["organization_id"]})
            organization = cur.fetchone()
            cur.execute(_query("upsert_openstates_roll_call"), {"congress": str(congress), "chamber": "house" if "lower" in vote["identifier"] else "senate", "external_id": vote["identifier"], "occurred_at": vote["start_date"], "question": vote["motion_text"], "result": vote["result"], "metadata": Jsonb({"source": "openstates", "ocd_id": vote["ocd_id"], "source_bill_ocd_id": vote["bill_id"]}), "ocd_id": vote["ocd_id"], "organization_id": organization["organization_id"] if organization else None})
            roll_call = cur.fetchone()
            counts["roll_calls"] += 1
            cur.execute(_query("openstates_person_votes"), {"vote_ocd_id": vote["ocd_id"]})
            for position in cur.fetchall():
                cur.execute(_query("find_person_by_identifier"), {"namespace": "ocd", "external_id": position["voter_id"]})
                person = cur.fetchone()
                if not person:
                    counts["unresolved_people"] += 1
                    continue
                cur.execute(_query("upsert_member_vote"), {"roll_call_id": roll_call["roll_call_id"], "person_id": person["person_id"], "position": position["option"], "source_artifact_id": artifact_id})
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

    with connect() as active_conn:
        result = _ensure(active_conn)
        active_conn.commit()
        return result


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
    bill_type = (bill.findtext("type") or "").strip().lower()
    bill_number = (bill.findtext("number") or "").strip()

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
    }


def save_billstatus_bill(
    bill_data: dict[str, Any],
    legislative_session_id: str,
    source_artifact_id: str | None = None,
    source_payload_id: str | None = None,
    source_member: str | None = None,
    conn: Any | None = None,
) -> str:
    """Upsert core.bill plus identifiers, actions, sponsorships, committees, subjects, and documents."""
    if source_artifact_id is None and source_payload_id is None:
        raise ValueError(
            "Persistence requires source_artifact_id or source_payload_id lineage"
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
                    "metadata": Jsonb({"source": "govinfo_billstatus"}),
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
                cur.execute(
                    _query("find_person_by_identifier"),
                    {
                        "namespace": sp["member_namespace"],
                        "external_id": sp["member_external_id"],
                    },
                )
                p_row = cur.fetchone()
                person_id = str(p_row["person_id"]) if p_row else None

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

            return bill_id

    if conn is not None:
        return _execute(conn)

    with connect() as active_conn:
        res = _execute(active_conn)
        active_conn.commit()
        return res
