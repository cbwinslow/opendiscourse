"""Reproducible evidence inventory; run with explicit source/warehouse DSNs.

This audit never promotes data or enables identity links. Conservative proposed
dispositions require human mapping review before a baseline can be approved.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from contextlib import ExitStack
from datetime import date, datetime
from decimal import Decimal
from functools import partial
from pathlib import Path
from typing import Any
from uuid import UUID

import psycopg
from psycopg import sql

from .feedback import spinner
from .openstatessnapshot import checksum
from .repositories.openstates_audit import SAFE_SAMPLE_COLUMNS, Reader

MAPPING_VERSION = "openstates-audit-1"
TARGETS = {
    "jurisdiction": "core.jurisdiction",
    "legislativesession": "core.legislative_session",
    "organization": "core.organization",
    "organizationidentifier": "core.organization_identifier",
    "person": "core.person",
    "personidentifier": "core.person_identifier",
    "post": "core.post",
    "membership": "core.membership",
    "bill": "core.bill",
    "billaction": "core.bill_action",
    "billsponsorship": "core.bill_sponsorship",
    "billdocument": "core.bill_document",
    "voteevent": "core.roll_call",
    "personvote": "fact.member_vote",
}


def canonical(value: Any) -> str:
    """Serialize stable evidence, with no clocks, credentials or private samples."""

    def encode(item):
        if isinstance(item, (date, datetime)):
            return item.isoformat()
        if isinstance(item, Decimal):
            return str(item)
        if isinstance(item, UUID):
            return str(item)
        raise TypeError(type(item).__name__)

    return (
        json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2, default=encode)
        + "\n"
    )


def digest(value: Any) -> str:
    """Hash canonical evidence rather than database credentials or local paths."""
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def disposition(relation: dict) -> dict:
    """Propose conservative handling using the approved civic mapping boundary."""
    name = relation["source_table"]
    concept = name.removeprefix("opencivicdata_")
    if relation["relkind"] == "S":
        return {
            "disposition": "implementation_only",
            "owned_target": None,
            "reason": "Sequence allocates application keys; catalog-only.",
        }
    if name.startswith("opencivicdata_") or name == "openstates_personoffice":
        target = TARGETS.get(concept)
        return {
            "disposition": "promote_typed" if target else "retain_source_only",
            "owned_target": target,
            "reason": "Public civic source evidence; retain every field pending reviewed typed mapping.",
        }
    if (
        relation["extension"]
        or name.startswith("boundaries_")
        or name == "v1_legacybillmapping"
    ):
        return {
            "disposition": "reference_only",
            "owned_target": None,
            "reason": "Geographic/legacy identifier reference or extension metadata; no person promotion.",
        }
    if name.startswith(
        (
            "auth_",
            "account_",
            "django_",
            "socialaccount_",
            "users_",
            "api_",
            "authtoken_",
            "reversion_",
            "pupa_",
            "profiles_",
            "people_admin_",
            "simplekeys_",
            "bundles_",
            "widgets_",
            "dashboards_",
            "dataquality_",
            "bulk_",
        )
    ):
        return {
            "disposition": "implementation_only",
            "owned_target": None,
            "reason": f"Upstream {name.split('_')[0]} application/account operation; catalog-only, no values inspected.",
        }
    return {
        "disposition": "unresolved",
        "owned_target": None,
        "reason": "Unknown public status: no values inspected; classification review required.",
    }


DIMENSION_COLUMNS = {
    "jurisdiction_id": "jurisdiction",
    "legislative_session_id": "legislative_session",
    "current_jurisdiction_id": "current_jurisdiction",
}
FIELD_RULES = {
    ("opencivicdata_jurisdiction", "id"): {
        "owned": "jurisdiction_id",
        "transform": "store the OpenStates/OCD jurisdiction id in core.jurisdiction.jurisdiction_id; do not mint a second key",
        "loss_risk": "none for the identifier",
        "blocked": "owned jurisdiction key is absent",
    },
    ("opencivicdata_jurisdiction", "name"): {
        "owned": "name",
        "transform": "copy the official jurisdiction name; the OCD id remains the identity",
        "loss_risk": "display text only",
        "blocked": "owned name column is absent",
    },
    ("opencivicdata_jurisdiction", "classification"): {
        "owned": "classification",
        "transform": "copy the source classification verbatim",
        "loss_risk": "none",
        "blocked": "owned classification column is absent",
    },
    ("opencivicdata_legislativesession", "identifier"): {
        "owned": "identifier",
        "transform": "keep the source session identifier inside its jurisdiction; do not read it as a federal Congress number",
        "loss_risk": "none",
        "blocked": "owned session identifier column is absent",
    },
    ("opencivicdata_legislativesession", "name"): {
        "owned": "name",
        "transform": "copy the source session name as display text",
        "loss_risk": "display text only",
        "blocked": "owned session name column is absent",
    },
    ("opencivicdata_legislativesession", "classification"): {
        "owned": "classification",
        "transform": "copy the source session classification verbatim",
        "loss_risk": "none",
        "blocked": "owned session classification column is absent",
    },
    ("opencivicdata_legislativesession", "active"): {
        "owned": "active",
        "transform": "copy the source boolean; do not infer active status from dates",
        "loss_risk": "none",
        "blocked": "owned active column is absent",
    },
    ("opencivicdata_legislativesession", "jurisdiction_id"): {
        "owned": "jurisdiction_id",
        "transform": "point at the owned jurisdiction row whose key is this same OCD id; never match by name",
        "loss_risk": "unresolved when that jurisdiction row is not promoted",
        "blocked": "owned jurisdiction reference is absent",
    },
    ("opencivicdata_legislativesession", "start_date"): {
        "owned": "starts_on",
        "transform": "write core.legislative_session.starts_on only for precision=day text; keep year or month text beside it and do not invent a month or day",
        "loss_risk": "partial dates are excluded from the date column",
        "blocked": "owned starts_on date column is absent",
    },
    ("opencivicdata_legislativesession", "end_date"): {
        "owned": "ends_on",
        "transform": "write core.legislative_session.ends_on only for precision=day text; keep year or month text beside it and do not invent a month or day",
        "loss_risk": "partial dates are excluded from the date column",
        "blocked": "owned ends_on date column is absent",
    },
    ("opencivicdata_organization", "name"): {
        "owned": "name",
        "transform": "copy the organization display name; the OpenStates organization id anchors identity",
        "loss_risk": "display text only",
        "blocked": "owned organization name column is absent",
    },
    ("opencivicdata_organization", "classification"): {
        "owned": "organization_type",
        "transform": "copy classification into organization_type without renaming values in this audit",
        "loss_risk": "source vocabulary may be wider than a later check constraint",
        "blocked": "owned organization_type column is absent",
    },
    ("opencivicdata_person", "name"): {
        "owned": "full_name",
        "transform": "copy the source display name into full_name; this value never matches another provider",
        "loss_risk": "display text only",
        "blocked": "owned full_name column is absent",
    },
    ("opencivicdata_person", "given_name"): {
        "owned": "given_name",
        "transform": "copy given_name verbatim",
        "loss_risk": "display text only",
        "blocked": "owned given_name column is absent",
    },
    ("opencivicdata_person", "family_name"): {
        "owned": "family_name",
        "transform": "copy family_name verbatim",
        "loss_risk": "display text only",
        "blocked": "owned family_name column is absent",
    },
    ("opencivicdata_person", "gender"): {
        "owned": "gender",
        "transform": "copy source gender text verbatim; do not infer it from a name",
        "loss_risk": "display text only",
        "blocked": "owned gender column is absent",
    },
    ("opencivicdata_person", "birth_date"): {
        "owned": "birthday",
        "transform": "write core.person.birthday only for precision=day text; do not invent a month or day",
        "loss_risk": "partial dates stay in source detail",
        "blocked": "owned birthday column is absent",
    },
    ("opencivicdata_post", "id"): {
        "owned": "ocd_id",
        "transform": "store the OpenStates post id in ocd_id; post_id remains an owned uuid",
        "loss_risk": "none for the identifier",
        "blocked": "owned ocd_id column is absent",
    },
    ("opencivicdata_post", "label"): {
        "owned": "label",
        "transform": "copy the source post label; do not match an office by title",
        "loss_risk": "display text only",
        "blocked": "owned label column is absent",
    },
    ("opencivicdata_post", "role"): {
        "owned": "role",
        "transform": "copy the source post role text",
        "loss_risk": "display text only",
        "blocked": "owned role column is absent",
    },
    ("opencivicdata_personidentifier", "scheme"): {
        "owned": "namespace",
        "transform": "copy scheme into person_identifier.namespace; BioGuide stays one namespace among others",
        "loss_risk": "none",
        "blocked": "owned namespace column is absent",
    },
    ("opencivicdata_personidentifier", "identifier"): {
        "owned": "external_id",
        "transform": "copy the identifier into external_id under its scheme; do not collapse duplicate assertions in this audit",
        "loss_risk": "duplicate source assertions stay visible",
        "blocked": "owned external_id column is absent",
    },
    ("opencivicdata_membership", "role"): {
        "owned": "role",
        "transform": "copy membership role text; an empty role cannot satisfy the owned NOT NULL role until a reviewed placeholder policy exists",
        "loss_risk": "blank roles remain unresolved",
        "blocked": "owned membership role column is absent",
    },
    ("opencivicdata_membership", "start_date"): {
        "owned": "start_date",
        "transform": "write the date column only for precision=day text; do not invent a month or day",
        "loss_risk": "partial dates stay in source detail",
        "blocked": "owned membership start_date column is absent",
    },
    ("opencivicdata_membership", "end_date"): {
        "owned": "end_date",
        "transform": "write the date column only for precision=day text; do not invent a month or day",
        "loss_risk": "partial dates stay in source detail",
        "blocked": "owned membership end_date column is absent",
    },
    ("opencivicdata_bill", "id"): {
        "owned": "ocd_id",
        "transform": "store the OpenStates bill id in ocd_id; do not parse it or the state bill label into bill_type and bill_number",
        "loss_risk": "federal type/number columns remain unfilled",
        "blocked": "owned ocd_id column is absent",
    },
    ("opencivicdata_bill", "title"): {
        "owned": "title",
        "transform": "copy the source title verbatim",
        "loss_risk": "none",
        "blocked": "owned title column is absent",
    },
    ("opencivicdata_bill", "latest_action_description"): {
        "owned": "latest_action",
        "transform": "copy the source action description; do not treat it as a federal action code",
        "loss_risk": "display text only",
        "blocked": "owned latest_action column is absent",
    },
    ("opencivicdata_billaction", "description"): {
        "owned": "description",
        "transform": "copy action description verbatim",
        "loss_risk": "a null description cannot satisfy NOT NULL description",
        "blocked": "owned description column is absent",
    },
    ("opencivicdata_billaction", "order"): {
        "owned": "source_ordinal",
        "transform": "copy the source action order into source_ordinal",
        "loss_risk": "none",
        "blocked": "owned source_ordinal column is absent",
    },
    ("opencivicdata_voteevent", "motion_text"): {
        "owned": "question",
        "transform": "copy motion wording into question; the source vote-event id defines the row",
        "loss_risk": "wording only",
        "blocked": "owned question column is absent",
    },
    ("opencivicdata_voteevent", "result"): {
        "owned": "result",
        "transform": "copy the source result text without translating it",
        "loss_risk": "source vocabulary is not constrained to a federal result list",
        "blocked": "owned result column is absent",
    },
    ("opencivicdata_voteevent", "id"): {
        "owned": "ocd_id",
        "transform": "store the OpenStates vote-event id in ocd_id",
        "loss_risk": "none",
        "blocked": "owned ocd_id column is absent",
    },
    ("opencivicdata_personvote", "option"): {
        "owned": "position",
        "transform": "copy option text into position; do not translate yea/nay without a reviewed vocabulary map",
        "loss_risk": "source option words may not match a later controlled list",
        "blocked": "owned position column is absent",
    },
}
SCHEMA_DECISIONS = {
    "opencivicdata_jurisdiction": {
        "needed_changes": [],
        "constraint_decisions": [
            "Use the OCD id as core.jurisdiction.jurisdiction_id.",
            "Keep url, division_id, extras and upstream timestamps in metadata or source detail; division_id is not core.geography.geoid.",
        ],
        "unresolved": [
            "No owned column yet says which artifact/payload supplied the jurisdiction row.",
        ],
    },
    "opencivicdata_legislativesession": {
        "needed_changes": [
            "Decide whether the source session uuid is reused as core.legislative_session.legislative_session_id after a collision check, or stored beside a new uuid. The owned table has no separate source-key column.",
        ],
        "constraint_decisions": [
            "starts_on and ends_on are dates; source start_date and end_date are text and may be year or month only.",
            "jurisdiction_id must be the promoted OCD jurisdiction id.",
            "The owned evidence check requires source_artifact_id or source_payload_id before insert.",
        ],
        "unresolved": ["Session primary-key collision policy is not approved."],
    },
    "opencivicdata_organization": {
        "needed_changes": [
            "Do not store the OCD jurisdiction id in jurisdiction_geoid.",
            "core.organization has no parent column; parent_id cannot be dropped into metadata without an explicit hierarchy decision.",
        ],
        "constraint_decisions": [
            "Owned organization_id is a generated uuid, so the OpenStates id needs an organization_identifier row in namespace openstates.",
            "classification maps to organization_type only as verbatim text.",
        ],
        "unresolved": ["Parent organization representation is undecided."],
    },
    "opencivicdata_person": {
        "needed_changes": [],
        "constraint_decisions": [
            "Owned person_id is a generated uuid. The OpenStates id is an identifier assertion, not a display-name match.",
            "biography, gender, birth_date, death_date, party, email, image and current role/jurisdiction stay in source detail. Email is never sampled or used as a join.",
        ],
        "unresolved": [
            "current_jurisdiction_id is a current attribute, not historical membership coverage.",
        ],
    },
    "opencivicdata_personidentifier": {
        "needed_changes": [],
        "constraint_decisions": [
            "scheme and identifier map to namespace and external_id.",
            "The source has no valid_from or valid_to; leave those owned dates null rather than inventing them.",
        ],
        "unresolved": [],
    },
    "opencivicdata_post": {
        "needed_changes": [],
        "constraint_decisions": [
            "core.post exists. Its post_id is a generated uuid; store the OpenStates id in ocd_id.",
            "organization_id is a uuid and NOT NULL, so it needs an organization identifier bridge. Do not copy the source text id into that uuid.",
            "Owned division_id is a uuid. The source division id is text and is not a geography geoid; keep it in source detail.",
            "label and role map verbatim. maximum_memberships stays in metadata. Do not match a post by its title.",
        ],
        "unresolved": [
            "A dated link from the source division id to owned division_id is not approved.",
        ],
    },
    "opencivicdata_membership": {
        "needed_changes": [],
        "constraint_decisions": [
            "person_id, organization_id and post_id are owned uuids. Source ids are text and need identifier bridges; do not copy them into the uuid columns.",
            "person_name must not fill person_id.",
            "start_date and end_date are dates; source values are text and may be partial.",
            "role is NOT NULL. legislative_session_id stays null when the source membership has no session.",
        ],
        "unresolved": [
            "Membership rows cannot be inserted until the person, organization and optional post bridges exist.",
        ],
    },
    "opencivicdata_bill": {
        "needed_changes": [
            "core.bill.bill_type and bill_number are NOT NULL and mean a federal bill. State labels must not be parsed into those columns. A later migration must allow a non-federal bill grain or make those columns nullable. No sentinel value is proposed.",
        ],
        "constraint_decisions": [
            "Store the OpenStates id in ocd_id and the official identifier verbatim in source detail.",
            "legislative_session_id must resolve through the owned session row, not by assuming the source uuid is already that row.",
            "first_action_date and latest_action_date are text; introduced_date and latest_action_date are dates and accept only full days.",
            "classification, subject, citations and extras stay in metadata jsonb.",
        ],
        "unresolved": [
            "The federal NOT NULL type/number constraint blocks state bill promotion until the schema story decides.",
        ],
    },
    "opencivicdata_billaction": {
        "needed_changes": [],
        "constraint_decisions": [
            "description maps to description and order maps to source_ordinal.",
            "date is text, while action_date is a timestamp; promote only a full day or timestamp and do not invent a time.",
            "classification is a text array in both models, but the owned insert also requires artifact or payload evidence.",
            "bill_id and organization_id resolve through source identifiers, not names.",
        ],
        "unresolved": ["Partial action dates remain unpromotable as timestamps."],
    },
    "opencivicdata_billsponsorship": {
        "needed_changes": [
            "member_namespace defaults to bioguide and member_external_id is NOT NULL. OpenStates sponsorships need an explicit namespace and must allow a missing person id.",
            "role allows only sponsor or cosponsor. Other source classification values need a wider check or must stay in source detail.",
        ],
        "constraint_decisions": [
            "Never fill member_external_id or person_id from the sponsorship name.",
            "A null person_id stays an unresolved source reference.",
        ],
        "unresolved": [
            "The owned sponsorship constraints reject a faithful state sponsorship row today.",
        ],
    },
    "opencivicdata_billdocument": {
        "needed_changes": [
            "core.bill_document only links a bill to core.document. Document note, date, classification and links need a core.document row plus retained link evidence, not a copy of this table.",
        ],
        "constraint_decisions": [
            "The link row has no place for the source document date or note.",
        ],
        "unresolved": ["The core.document source-key grain for OpenStates documents is not approved."],
    },
    "opencivicdata_voteevent": {
        "needed_changes": [
            "core.roll_call.external_id has no namespace. Do not write the OpenStates identifier there until a prefix or namespace is approved, because federal roll-call ids share that column.",
            "jurisdiction and legislative_session are NOT NULL text. Fill them only from the resolved owned jurisdiction and session, not from a guessed label.",
        ],
        "constraint_decisions": [
            "motion_text maps to question, result maps to result, and the OpenStates id maps to ocd_id.",
            "start_date is text and occurred_at is a timestamp; do not invent a clock time.",
        ],
        "unresolved": ["Namespacing of roll_call.external_id is not approved."],
    },
    "opencivicdata_personvote": {
        "needed_changes": [
            "fact.member_vote has no voter-name column and person_id is NOT NULL. An unresolved voter cannot be inserted as a member vote.",
        ],
        "constraint_decisions": [
            "option maps to position only as original text.",
            "voter_name never creates or matches a person.",
            "The owned evidence check requires an artifact or payload.",
        ],
        "unresolved": [
            "Rows with no resolved voter remain source-native until a nullable or unresolved-voter design is approved.",
        ],
    },
}


def _target_fields(owned: list[dict], target: str | None) -> dict[str, str]:
    if not target:
        return {}
    return {
        column["source_path"]: column["source_type"]
        for column in owned
        if f"{column['source_schema']}.{column['source_table']}" == target
    }


def semantic_mapping(relation: dict, column: dict, owned: list[dict]) -> dict:
    """Propose explicit source-ID, reference and date semantics; never infer by matching names."""
    table = relation["source_table"]
    name = column["source_path"]
    target = relation["owned_target"]
    target_fields = _target_fields(owned, target)
    retain = {
        "disposition": "retained_source_detail",
        "owned_target": None,
        "transform": "retain original value/type in immutable source record keyed by OpenStates primary key",
        "loss_risk": "none when verbatim evidence is retained",
    }
    rule = FIELD_RULES.get((table, name))
    if rule and rule["owned"] in target_fields:
        return {
            "disposition": "typed_searchable",
            "owned_target": f"{target}.{rule['owned']}",
            "transform": rule["transform"]
            + f"; owned column type {target_fields[rule['owned']]}; raw source value remains in source evidence; no cross-provider name join",
            "loss_risk": rule["loss_risk"],
        }
    if rule and target:
        return {
            **retain,
            "transform": rule["blocked"]
            + "; "
            + rule["transform"]
            + "; raw source value remains retained",
            "loss_risk": rule["loss_risk"],
        }
    if name == "id":
        return {
            **retain,
            "transform": "preserve source-native ID with OpenStates namespace; use source-record/identifier assertion, never overwrite owned generated primary key",
        }
    if name in (
        "person_id",
        "organization_id",
        "post_id",
        "bill_id",
        "legislative_session_id",
        "jurisdiction_id",
        "voter_id",
        "vote_event_id",
    ):
        return {
            **retain,
            "transform": f"retain source reference {name}; resolve only through reviewed OpenStates source-ID assertion bridge; record unresolved keys without a name join",
        }
    if name in (
        "date",
        "start_date",
        "end_date",
        "first_action_date",
        "last_action_date",
        "latest_action_date",
        "latest_passage_date",
        "birth_date",
        "death_date",
    ) or name.endswith("_date"):
        return {
            **retain,
            "transform": "validate calendar and retain original year/month/day precision; no artificial missing month/day; promote only lossless dates after target constraint review",
            "loss_risk": "partial or invalid text dates are not coerced",
        }
    return retain


def _coverage_edges(keys: list[dict], public_tables: set[tuple[str, str]]) -> dict:
    """Single-column foreign keys between public relations, excluding self links."""
    edges = {}
    for key in keys:
        source = (key["source_schema"], key["source_table"])
        target = (key.get("target_schema"), key.get("target_table"))
        columns = list(key.get("columns") or [])
        targets = list(key.get("target_columns") or [])
        if (
            key.get("kind") != "f"
            or source not in public_tables
            or target not in public_tables
            or source == target
            or len(columns) != 1
            or len(targets) != 1
        ):
            continue
        edges.setdefault(source, []).append(
            {
                "constraint_name": key["constraint_name"],
                "column": columns[0],
                "target_schema": target[0],
                "target_table": target[1],
                "target_column": targets[0],
            }
        )
    for source_edges in edges.values():
        source_edges.sort(
            key=lambda edge: (
                edge["column"],
                edge["target_table"],
                edge["constraint_name"],
            )
        )
    return edges


def _dimension_locations(start, columns_by_table, edges):
    """Shortest declared parent path to each table that carries a coverage column."""
    discovered = []
    queue = [(start, ())]
    seen = {start}
    while queue:
        node, hops = queue.pop(0)
        for column, dimension in DIMENSION_COLUMNS.items():
            if column in columns_by_table.get(node, ()):
                discovered.append(
                    {
                        "dimension": dimension,
                        "column": column,
                        "schema": node[0],
                        "table": node[1],
                        "hops": hops,
                        "alias_index": len(hops),
                    }
                )
        if len(hops) >= 4:
            continue
        for edge in edges.get(node, ()):
            nxt = (edge["target_schema"], edge["target_table"])
            if nxt in seen:
                continue
            seen.add(nxt)
            queue.append((nxt, hops + (edge,)))
    return discovered


def _path_signature(hops) -> tuple:
    return tuple(hop["constraint_name"] for hop in hops)


def coverage_plans(schema, table, columns_by_table, edges) -> list[dict]:
    """Choose one parent path that preserves session, then jurisdiction.

    Other declared routes stay visible as unmeasured alternates. A missing route
    is unavailable coverage, not a zero count. current_jurisdiction_id is never
    treated as historical jurisdiction coverage.
    """
    if table == "opencivicdata_jurisdiction":
        return [
            {
                "method": "direct",
                "hops": [],
                "dimensions": [{"name": "id", "column": "id", "alias_index": 0}],
                "session_coverage": "not_supplied",
                "jurisdiction_coverage": "own_source_key",
                "note": "each jurisdiction row is its own coverage key; a session is not supplied and is not zero",
                "alternate_paths": [],
            }
        ]
    if table == "opencivicdata_legislativesession":
        return [
            {
                "method": "direct",
                "hops": [],
                "dimensions": [
                    {"name": "id", "column": "id", "alias_index": 0},
                    {"name": "jurisdiction_id", "column": "jurisdiction_id", "alias_index": 0},
                ],
                "session_coverage": "own_source_key",
                "jurisdiction_coverage": "direct_column",
                "note": "the session primary key is the coverage key; it is not a federal Congress number",
                "alternate_paths": [],
            }
        ]
    start = (schema, table)
    discovered = _dimension_locations(start, columns_by_table, edges)
    session_options = [
        item for item in discovered if item["dimension"] == "legislative_session"
    ]
    plans = []
    chosen_signature = None
    if session_options:
        session = min(session_options, key=lambda item: (len(item["hops"]), _path_signature(item["hops"])))
        hops = list(session["hops"])
        holder = (session["schema"], session["table"])
        jurisdiction = None
        if "jurisdiction_id" in columns_by_table.get(holder, ()):
            jurisdiction = {
                "dimension": "jurisdiction",
                "column": "jurisdiction_id",
                "schema": holder[0],
                "table": holder[1],
                "alias_index": len(hops),
            }
        else:
            for edge in edges.get(holder, ()):
                nxt = (edge["target_schema"], edge["target_table"])
                if edge["column"] == "legislative_session_id" and "jurisdiction_id" in columns_by_table.get(nxt, ()):
                    hops.append(edge)
                    jurisdiction = {
                        "dimension": "jurisdiction",
                        "column": "jurisdiction_id",
                        "schema": nxt[0],
                        "table": nxt[1],
                        "alias_index": len(hops),
                    }
                    break
        dimensions = [
            {
                "name": "legislative_session_id",
                "column": session["column"],
                "alias_index": session["alias_index"],
            }
        ]
        if jurisdiction:
            dimensions.append(
                {
                    "name": "jurisdiction_id",
                    "column": jurisdiction["column"],
                    "alias_index": jurisdiction["alias_index"],
                }
            )
        chosen_signature = _path_signature(hops)
        plans.append(
            {
                "method": "parent_derived" if hops else "direct",
                "hops": hops,
                "dimensions": dimensions,
                "session_coverage": "parent_path" if hops else "direct_column",
                "jurisdiction_coverage": "parent_path" if jurisdiction and hops else "direct_column" if jurisdiction else "not_supplied",
                "note": None if jurisdiction else "session path has no declared jurisdiction column; jurisdiction is not_supplied, not zero",
            }
        )
    else:
        historical = [
            item for item in discovered if item["dimension"] == "jurisdiction"
        ]
        if historical:
            chosen = min(historical, key=lambda item: (len(item["hops"]), _path_signature(item["hops"])))
            chosen_signature = _path_signature(chosen["hops"])
            plans.append(
                {
                    "method": "parent_derived" if chosen["hops"] else "direct",
                    "hops": list(chosen["hops"]),
                    "dimensions": [
                        {
                            "name": "jurisdiction_id",
                            "column": chosen["column"],
                            "alias_index": chosen["alias_index"],
                        }
                    ],
                    "session_coverage": "not_supplied",
                    "jurisdiction_coverage": "parent_path" if chosen["hops"] else "direct_column",
                    "note": "no declared legislative-session path; session absence is not an observed zero",
                }
            )
    current = next(
        (item for item in discovered if item["dimension"] == "current_jurisdiction"),
        None,
    )
    if current and _path_signature(current["hops"]) != chosen_signature:
        plans.append(
            {
                "method": "parent_derived" if current["hops"] else "direct",
                "hops": list(current["hops"]),
                "dimensions": [
                    {
                        "name": "current_jurisdiction_id",
                        "column": current["column"],
                        "alias_index": current["alias_index"],
                    }
                ],
                "session_coverage": "not_supplied",
                "jurisdiction_coverage": "current_attribute_not_historical",
                "note": "current_jurisdiction_id is not historical membership or session coverage",
            }
        )
    alternates = []
    for item in discovered:
        if item["dimension"] == "current_jurisdiction":
            continue
        signature = _path_signature(item["hops"])
        if chosen_signature is not None and chosen_signature[: len(signature)] == signature:
            continue
        alternates.append(
            {
                "measured": False,
                "dimension": item["dimension"],
                "path": [
                    f"{hop['column']}->{hop['target_table']}.{hop['target_column']}"
                    for hop in item["hops"]
                ],
                "reason": "alternate declared parent route was not used for the count",
            }
        )
    if not plans:
        plans.append(
            {
                "method": "unavailable",
                "hops": [],
                "dimensions": [],
                "session_coverage": "not_supplied",
                "jurisdiction_coverage": "not_supplied",
                "note": "no declared jurisdiction or legislative-session path",
            }
        )
    for plan in plans:
        plan["alternate_paths"] = alternates
    return plans


def schema_review(relations: list[dict], owned: list[dict] | None) -> list[dict]:
    """State owned-schema constraints without proposing a copy of a source table."""
    owned_known = owned is not None
    existing = set()
    owned_fields = {}
    for column in owned or []:
        name = f"{column['source_schema']}.{column['source_table']}"
        existing.add(name)
        owned_fields.setdefault(name, set()).add(column["source_path"])
    reviews = []
    for relation in relations:
        if relation["disposition"] not in ("promote_typed", "retain_source_only"):
            continue
        target = relation.get("owned_target")
        specific = SCHEMA_DECISIONS.get(relation["source_table"], {})
        if not owned_known:
            target_status = "unresolved"
        elif not target or target not in existing:
            target_status = "absent"
        else:
            target_status = "present"
        reviews.append(
            {
                "source_schema": relation["source_schema"],
                "source_table": relation["source_table"],
                "disposition": relation["disposition"],
                "proposed_target": target,
                "table_copy": False,
                "target_status": target_status,
                "fdw_status": relation.get("fdw_status"),
                "reader_change": relation.get("reader_change"),
                "needed_changes": specific.get("needed_changes", []) if specific else [],
                "constraint_decisions": specific.get(
                    "constraint_decisions",
                    [
                        "No owned table is proposed. Retain the source primary key and original values until a reviewed typed target exists."
                    ],
                ),
                "unresolved": specific.get(
                    "unresolved",
                    ["Typed promotion is not proposed for this relation."],
                ),
                "owned_fields_present": sorted(owned_fields.get(target, []))
                if target and owned_known
                else [],
            }
        )
    return reviews


def _scope_failed(errors: list[dict], schema: str, table: str) -> bool:
    prefix = f"{schema}.{table}"
    return any(str(item.get("scope", "")).startswith(prefix) for item in errors)


def structural_manifest(report: dict) -> dict:
    """Rebuild structural identity from recorded source/reader shapes, never counts."""

    def project(rows, names):
        return sorted(({k: row.get(k) for k in names} for row in rows), key=canonical)

    return {
        "relations": project(
            report["relations"],
            ("source_schema", "source_table", "relkind", "extension", "row_security"),
        ),
        "columns": project(
            report["columns"],
            (
                "source_schema",
                "source_table",
                "source_path",
                "source_type",
                "position",
                "not_null",
            ),
        ),
        "nested_fields": project(
            report["nested_fields"],
            ("source_schema", "source_table", "source_path", "source_type"),
        ),
        "keys": project(
            report["keys"],
            (
                "source_schema",
                "source_table",
                "constraint_name",
                "kind",
                "columns",
                "target_schema",
                "target_table",
                "target_columns",
                "validated",
            ),
        ),
        "fdw": project(
            report["fdw"],
            ("source_schema", "source_table", "reader_schema", "reader_table"),
        ),
        "fdw_columns": project(
            report.get("fdw_columns", []),
            (
                "source_schema",
                "source_table",
                "source_path",
                "source_type",
                "position",
                "not_null",
            ),
        ),
    }


def mapping_manifest(report: dict) -> dict:
    """Bind a review to concrete proposed field transformations and relation treatment."""
    names = (
        "source_schema",
        "source_table",
        "source_path",
        "disposition",
        "owned_target",
        "transform",
        "source_key",
        "mapping_version",
        "loss_risk",
    )
    return {
        "version": report["mapping_version"],
        "relations": sorted(
            (
                {
                    k: r.get(k)
                    for k in (
                        "source_schema",
                        "source_table",
                        "disposition",
                        "owned_target",
                        "reason",
                    )
                }
                for r in report["relations"]
            ),
            key=canonical,
        ),
        "fields": sorted(
            ({k: c.get(k) for k in names} for c in report["columns"]), key=canonical
        ),
    }


def fingerprint(report: dict) -> dict:
    """Separate structural drift, proposed mapping, measurements and restore evidence."""
    return {
        "schema": 2,
        "structural_sha256": digest(structural_manifest(report)),
        "mapping_sha256": digest(mapping_manifest(report)),
        "measurements_sha256": digest(
            {
                "counts": [
                    {
                        k: r.get(k)
                        for k in ("source_schema", "source_table", "row_count")
                    }
                    for r in report["relations"]
                ],
                "coverage": report.get("coverage", []),
                "identity": report.get("identity", {}),
                "references": report.get("references", []),
            }
        ),
        "source_version": report.get("source_version"),
        "mapping_version": report["mapping_version"],
        "evidence": report.get("approval_evidence", {}),
        "registered_candidate_artifacts": report.get("registered_candidate_artifacts"),
        "restore_lineage_verified": bool(
            report.get("approval_evidence", {}).get("restore")
        ),
    }


def approval_inputs(report: dict, mapping: dict | None, restore: dict | None) -> dict:
    """Validate explicit reviewer assertions against this exact recorded structure.

    These are operator-supplied attestations, not invented or inferred restore
    proof. A referenced restore record is separately checksum-validated at input.
    """
    current = fingerprint(report)
    evidence = {}
    if mapping is not None:
        if (
            mapping.get("schema") != 1
            or mapping.get("kind") != "mapping_review"
            or mapping.get("decision") != "approved"
            or mapping.get("mapping_version") != report["mapping_version"]
            or mapping.get("structural_sha256") != current["structural_sha256"]
            or mapping.get("mapping_sha256") != current["mapping_sha256"]
            or not mapping.get("reviewer")
            or not mapping.get("reviewed_at")
        ):
            raise ValueError(
                "mapping review does not approve this exact structural/mapping manifest"
            )
        if datetime.fromisoformat(mapping["reviewed_at"]).tzinfo is None:
            raise ValueError("mapping review timestamp needs explicit timezone")
        evidence["mapping"] = mapping
    if restore is not None:
        candidate = next(
            (
                a
                for a in report.get("registered_candidate_artifacts") or []
                if all(
                    a.get(k) == restore.get(k)
                    for k in (
                        "artifact_id",
                        "artifact_key",
                        "checksum_sha256",
                        "bytes_downloaded",
                    )
                )
            ),
            None,
        )
        if (
            restore.get("schema") != 1
            or restore.get("kind") != "restore_attestation"
            or restore.get("decision") != "verified"
            or restore.get("structural_sha256") != current["structural_sha256"]
            or candidate is None
            or not restore.get("attested_by")
            or not restore.get("restored_at")
            or not restore.get("record_sha256")
            or not restore.get("record_validated")
        ):
            raise ValueError(
                "restore attestation does not bind reviewed restore evidence to this source/artifact"
            )
        if datetime.fromisoformat(restore["restored_at"]).tzinfo is None:
            raise ValueError("restore timestamp needs explicit timezone")
        evidence["restore"] = restore
    return evidence


def load_approval(path: Path, *, restore=False) -> dict:
    """Read supplied review evidence; checksum referenced restore records using existing helper."""
    payload = json.loads(path.read_text())
    if restore:
        record = path.parent / payload.pop("record_file")
        if not record.is_file() or checksum(record) != payload.get("record_sha256"):
            raise ValueError("restore record checksum mismatch")
        payload["record_validated"] = True
    return payload


def validate(report: dict, baseline: dict | None = None) -> None:
    """Fail closed on gaps, unreviewed mapping, unproven lineage or drift."""
    computed = fingerprint(report)
    if report["fingerprint"] != computed:
        raise ValueError(
            "fingerprint does not match recomputed recorded structures/measurements"
        )
    evidence = report.get("approval_evidence", {})
    approval_inputs(report, evidence.get("mapping"), evidence.get("restore"))
    if any(
        not isinstance(step, dict)
        for n in report["nested_fields"]
        for step in n["source_path"]
    ):
        raise ValueError("legacy untagged nested paths cannot approve a drift baseline")
    if (
        report["errors"]
        or report.get("completion_gaps")
        or not computed["restore_lineage_verified"]
    ):
        raise ValueError(
            "audit incomplete: unresolved measurements or restored-artifact lineage"
        )
    if not evidence.get("mapping"):
        raise ValueError("mapping needs independent review")
    if baseline is not None:
        validate(baseline)
        if (
            computed["structural_sha256"]
            != baseline["fingerprint"]["structural_sha256"]
            or computed["mapping_sha256"] != baseline["fingerprint"]["mapping_sha256"]
        ):
            raise ValueError("snapshot drift: reviewed baseline update required")


def permitted_identity(namespace: str, identifier: str) -> tuple[str, str] | None:
    """Describe permitted identifiers only; display names never resolve people."""
    if namespace in ("openstates", "ocd-person", "bioguide") and identifier:
        return namespace, identifier
    return None


def nested_dispositions(fields: list[dict], columns: list[dict]) -> list[dict]:
    """Derive exact present-path null rates from exhaustive occurrence evidence.

    JSON arrays can contain multiple occurrences per source row; missing paths
    are not observed JSON nulls. Retain the separate SQL-column null rate.
    """
    totals, nulls = {}, {}
    column_rates = {
        (c["source_schema"], c["source_table"], c["source_path"]): c["null_rate"]
        for c in columns
    }
    for field in fields:
        key = (
            field["source_schema"],
            field["source_table"],
            canonical(field["source_path"]),
        )
        count = field["occurrence_count"]
        totals[key] = totals.get(key, 0) + count
        if field["source_type"] == "null":
            nulls[key] = nulls.get(key, 0) + count
    derived = []
    for field in fields:
        key = (
            field["source_schema"],
            field["source_table"],
            canonical(field["source_path"]),
        )
        derived.append(
            {
                **field,
                "source_column_sql_null_rate": column_rates.get(
                    (
                        *key[:2],
                        field["source_path"][0].get("value")
                        if isinstance(field["source_path"][0], dict)
                        else field["source_path"][0],
                    )
                ),
                "null_rate": nulls.get(key, 0) / totals[key] if totals[key] else None,
                "null_rate_scope": "present_path_occurrences; absent paths are not nulls",
                "measurement_method": "derived from exhaustive per-path/type occurrence counts; no source rescan",
            }
        )
    return derived


def write_outputs(report: dict, destination: Path) -> None:
    """Save reviewable output matrices without overwriting existing evidence."""
    matrices = {
        "relation-inventory": report["relations"],
        "field-dispositions": report["columns"],
        "nested-field-inventory": report["nested_fields"],
        "fdw-coverage": report["fdw"],
        "coverage": report["coverage"],
        "snapshot-fingerprint": report["fingerprint"],
        "identity-audit": report["identity"],
        "reconciliation-baseline": {
            "keys": report["keys"],
            "references": report["references"],
            "source_counts": [
                {k: r.get(k) for k in ("source_schema", "source_table", "row_count")}
                for r in report["relations"]
            ],
            "requirements": report["reconciliation"],
        },
        "schema-deltas": report["schema_deltas"],
    }
    for name, value in matrices.items():
        with (destination / f"{name}.json").open("x") as stream:
            stream.write(canonical(value))
    public = [
        r
        for r in report["relations"]
        if r["disposition"] in ("promote_typed", "retain_source_only")
    ]
    lines = [
        "# OpenStates snapshot evidence audit",
        "",
        "Status: incomplete. Restore lineage and mapping approval remain unresolved.",
        "",
        f"Inventoried {len(report['relations'])} relations (including sequences), {len(report['columns'])} scalar columns and {len(report['nested_fields'])} nested path/type entries.",
        f"Proposed civic research relations: {len(public)}. FDW catalog relations: {len(report['fdw'])}.",
        "",
        "A missing FDW relation is present-but-unreadable, not excluded. Actual remote probes are recorded in relation-inventory.json.",
        "",
        "Publisher historical availability cannot be inferred from this dump. Missing groups and query failures are unknown, not zero.",
        "",
        "Proposed mapping targets require independent semantic/type review. No schema, reader, promotion or cross-provider identity writes occurred.",
        "",
        "## Unresolved measurements",
        "",
    ]
    lines.extend(
        f"- {e['scope']}: {e['status']} ({e.get('sqlstate', 'no SQLSTATE')})"
        for e in report["errors"]
    )
    if not report["errors"]:
        lines.append(
            "No SQL measurement failures were recorded; lineage and mapping review still block completion."
        )
    lines.extend(
        [
            "",
            "Parent-derived coverage follows declared foreign keys toward a legislative session, then that session's jurisdiction. Alternate parent routes are named but not counted. A missing path or null key is not supplied, not a publisher zero. Successful checkpoints can be reused only when the catalog baseline matches; failed scopes stay visible and are measured again. Database snapshot exports are never reused.",
        "",
        "Next: review the relation/field matrices, establish restored-artifact lineage, resolve listed gaps, and approve the baseline before the separate schema/reader and bounded-pilot stories. Issue #100 remains open.",
        ]
    )
    with (destination / "report.md").open("x") as stream:
        stream.write("\n".join(lines) + "\n")


def _usable_prior(prior, catalog_baseline):
    """Reuse finished measurements only for this exact catalog baseline."""
    relations, references = {}, {}
    rejected = False
    for phase, evidence in prior or []:
        if evidence.get("catalog_baseline") != catalog_baseline:
            rejected = True
            continue
        if not evidence.get("reuse_allowed"):
            continue
        if phase == "relation":
            nested_fields = evidence.get("nested_fields") or []
            tagged = all(
                isinstance(item.get("source_path"), list)
                and all(
                    isinstance(step, dict) and "kind" in step
                    for step in item["source_path"]
                )
                for item in nested_fields
            )
            coverage_rows = evidence.get("coverage")
            if tagged and coverage_rows is not None and all(
                "method" in row for row in coverage_rows
            ):
                relation = evidence["relation"]
                relations[(relation["source_schema"], relation["source_table"])] = (
                    evidence
                )
        elif phase == "reference" and evidence.get("reference", {}).get("measurement") is not None:
            references[evidence["reference"]["constraint_name"]] = evidence["reference"]
    return relations, references, rejected


def audit(
    source: Reader,
    warehouse: Reader,
    schemas: list[str],
    checkpoint=None,
    prior=None,
) -> dict:
    """Measure each database through one exported snapshot; reader probes are availability only."""
    with ExitStack() as contexts:
        for reader in (source, warehouse):
            contexts.enter_context(reader.snapshot())
        report = _audit(source, warehouse, schemas, checkpoint, prior)
    report["snapshot_consistency"] = (
        "independent exported repeatable-read source/warehouse snapshots; FDW probes measure readability only"
    )
    return report


def _audit(
    source: Reader,
    warehouse: Reader,
    schemas: list[str],
    checkpoint=None,
    prior=None,
) -> dict:
    """Inventory public evidence exhaustively or record each unavailable query."""
    errors = []

    def measure(scope, operation):
        try:
            return operation()
        except psycopg.Error as exc:
            errors.append(
                {"scope": scope, "sqlstate": exc.sqlstate, "status": "unresolved"}
            )
            return None

    relations = (
        measure("source catalog", lambda: source.query("catalog", (schemas,))) or []
    )
    columns = (
        measure("source columns", lambda: source.query("columns", (schemas,))) or []
    )
    keys = measure("source keys", lambda: source.query("keys", (schemas,))) or []
    fdw = (
        measure("FDW catalog", lambda: warehouse.query("fdw", ("openstates_source",)))
        or []
    )
    owned_measured = measure(
        "owned columns", lambda: warehouse.query("columns", (["core", "fact"],))
    )
    owned = owned_measured or []
    artifacts = measure(
        "registered candidate artifacts", lambda: warehouse.query("artifacts")
    )
    nested, coverage, references = [], [], []
    fdw_columns = (
        measure(
            "FDW columns", lambda: warehouse.query("columns", (["openstates_source"],))
        )
        or []
    )
    fdw_by_source = {}
    for exposure in fdw:
        fdw_by_source.setdefault(
            (exposure["source_schema"], exposure["source_table"]), []
        ).append(exposure)
    catalog_baseline = digest(
        {"relations": relations, "columns": columns, "keys": keys, "fdw": fdw}
    )
    if checkpoint:
        checkpoint(
            "catalog",
            {
                "catalog_baseline": catalog_baseline,
                "relations": relations,
                "columns": columns,
                "keys": keys,
                "fdw": fdw,
                "errors": list(errors),
                "status": "incomplete",
                "reuse_allowed": False,
            },
        )
    columns_by_table = {}
    for column in columns:
        columns_by_table.setdefault(
            (column["source_schema"], column["source_table"]), set()
        ).add(column["source_path"])
    planned_public = {
        (relation["source_schema"], relation["source_table"])
        for relation in relations
        if disposition(relation)["disposition"]
        in ("promote_typed", "retain_source_only")
    }
    edges = _coverage_edges(keys, planned_public)
    reusable_relations, reusable_references, resume_rejected = _usable_prior(
        prior, catalog_baseline
    )
    with spinner("Auditing read-only OpenStates evidence") as phase:
        for relation in relations:
            schema, table = relation["source_schema"], relation["source_table"]
            relation.update(disposition(relation))
            exposures = fdw_by_source.get((schema, table), [])
            relation["fdw_aliases"] = exposures
            relation["fdw_status"] = (
                "present_but_unreadable" if not exposures else "catalog_exposed"
            )
            relation["reader_change"] = (
                "separate reviewed approval required" if not exposures else None
            )
            public = relation["disposition"] in (
                "promote_typed",
                "retain_source_only",
            ) or (
                relation["disposition"] == "reference_only"
                and not relation["extension"]
            )
            if relation["disposition"] == "unresolved":
                errors.append(
                    {
                        "scope": f"{schema}.{table}",
                        "status": "classification_unresolved",
                    }
                )
            fields = [
                c
                for c in columns
                if (c["source_schema"], c["source_table"]) == (schema, table)
            ]
            saved = reusable_relations.get((schema, table))
            saved_columns = {
                column["source_path"]: column for column in (saved or {}).get("columns", [])
            }
            sample_columns = [
                c["source_path"]
                for c in fields
                if c["source_path"] in SAFE_SAMPLE_COLUMNS
            ]
            if saved:
                relation["safe_samples"] = saved["relation"].get("safe_samples")
                relation["row_count"] = saved["relation"].get("row_count")
                if saved["relation"].get("count_status"):
                    relation["count_status"] = saved["relation"]["count_status"]
                relation["measurement_reuse"] = "same_catalog_baseline"
                profile = None
            else:
                samples = (
                    measure(
                        f"{schema}.{table}: bounded safe public example",
                        partial(source.samples, schema, table, sample_columns),
                    )
                    if public and sample_columns
                    else None
                )
                relation["safe_samples"] = samples
                profile = (
                    measure(
                        f"{schema}.{table}: whole table profile",
                        partial(source.table_profile, schema, table, fields),
                    )
                    if public and fields
                    else None
                )
                relation["row_count"] = profile["row_count"] if profile else None
            if (
                not saved
                and not public
                and relation["relkind"] != "S"
                and relation["disposition"] != "unresolved"
            ):
                counted = measure(
                    f"{schema}.{table}: aggregate count only",
                    partial(
                        source.query, "count", relation=sql.Identifier(schema, table)
                    ),
                )
                relation["row_count"] = counted[0]["row_count"] if counted else None
            if relation["relkind"] == "S":
                relation["count_status"] = (
                    "not_applicable: sequence is key allocator, not rows"
                )
            for exposure in exposures if public else []:
                readable = measure(
                    f"{schema}.{table}: FDW read probe",
                    partial(
                        warehouse.query,
                        "readable",
                        relation=sql.Identifier(
                            exposure["reader_schema"], exposure["reader_table"]
                        ),
                    ),
                )
                exposure["read_status"] = (
                    "readable_via_fdw"
                    if readable is not None
                    else "present_but_unreadable"
                )
                if readable is not None:
                    relation["fdw_status"] = "readable_via_fdw"
                exposed_fields = {
                    c["source_path"]: c["source_type"]
                    for c in fdw_columns
                    if (c["source_schema"], c["source_table"])
                    == (exposure["reader_schema"], exposure["reader_table"])
                }
                exposure["column_diff"] = [
                    {
                        "source_path": c["source_path"],
                        "source_type": c["source_type"],
                        "reader_type": exposed_fields.get(c["source_path"]),
                        "status": "absent"
                        if c["source_path"] not in exposed_fields
                        else "type_mismatch"
                        if exposed_fields[c["source_path"]] != c["source_type"]
                        else "same",
                    }
                    for c in fields
                ]
                exposure["reader_only_columns"] = sorted(
                    set(exposed_fields) - {c["source_path"] for c in fields}
                )
            for index, column in enumerate(fields):
                path = column["source_path"]
                phase(f"{schema}.{table}.{path}")
                column.update(
                    disposition="retained_source_detail" if public else "excluded",
                    owned_target=None,
                    transform="verbatim" if public else None,
                    source_key=[
                        k["columns"]
                        for k in keys
                        if k["source_schema"] == schema
                        and k["source_table"] == table
                        and k["kind"] == "p"
                    ],
                    loss_risk="none when verbatim evidence is retained"
                    if public
                    else "not public research evidence",
                    reason=relation["reason"],
                    mapping_version=MAPPING_VERSION,
                    reviewed_at=None,
                    null_rate=None,
                    sample_count=0,
                )
                if not public:
                    continue
                column.update(semantic_mapping(relation, column, owned))
                saved_column = saved_columns.get(path)
                if saved_column:
                    column["sample_count"] = saved_column.get("sample_count", 0)
                    column["null_rate"] = saved_column.get("null_rate")
                    column["date_range"] = saved_column.get("date_range")
                    column["text_date_precision"] = saved_column.get(
                        "text_date_precision"
                    )
                    column["nested_complete"] = saved_column.get("nested_complete")
                    if column.get("nested_complete"):
                        for item in saved.get("nested_fields") or []:
                            source_path = item.get("source_path")
                            if source_path[:1] != [
                                {"kind": "column", "value": path}
                            ]:
                                continue
                            nested.append(
                                {
                                    **column,
                                    "path": item.get("path"),
                                    "source_type": item.get("source_type"),
                                    "occurrence_count": item.get("occurrence_count"),
                                    "null_rate": item.get("null_rate"),
                                    "null_rate_scope": item.get("null_rate_scope"),
                                    "source_path": source_path,
                                }
                            )
                    continue
                column["sample_count"] = (
                    len(relation.get("safe_samples") or [])
                    if path in sample_columns
                    else 0
                )
                if profile:
                    column["null_rate"] = (
                        profile[f"null_{index}"] / profile["row_count"]
                        if profile["row_count"]
                        else None
                    )
                    column["date_range"] = (
                        {"min": profile[f"min_{index}"], "max": profile[f"max_{index}"]}
                        if f"min_{index}" in profile
                        else None
                    )
                if (path == "date" or path.endswith("_date")) and column[
                    "source_type"
                ].startswith(("text", "character varying", "character(")):
                    column["text_date_precision"] = measure(
                        f"{schema}.{table}.{path}: text date precision",
                        partial(source.text_dates, schema, table, path),
                    )
                if column["source_type"] in ("json", "jsonb") or column[
                    "source_type"
                ].endswith("[]"):
                    paths = measure(
                        f"{schema}.{table}.{path}: exhaustive nested paths",
                        partial(source.nested, schema, table, path),
                    )
                    column["nested_complete"] = paths is not None
                    for item in paths or []:
                        nested.append(
                            {
                                **column,
                                **item,
                                "source_path": [
                                    {"kind": "column", "value": path},
                                    *item["path"],
                                ],
                            }
                        )
                if checkpoint:
                    checkpoint(
                        "field",
                        {
                            "catalog_baseline": catalog_baseline,
                            "column": column,
                            "nested_fields": [
                                n
                                for n in nested
                                if n["source_schema"] == schema
                                and n["source_table"] == table
                                and n["source_path"][0]
                                == {"kind": "column", "value": path}
                            ],
                            "errors": list(errors),
                            "status": "incomplete",
                            "reuse_allowed": False,
                        },
                    )
            if saved and relation["disposition"] in (
                "promote_typed",
                "retain_source_only",
            ):
                for item in saved.get("coverage") or []:
                    coverage.append(
                        {
                            **item,
                            "fdw_status": relation["fdw_status"],
                            "reused_measurement": True,
                        }
                    )
            elif relation["disposition"] in ("promote_typed", "retain_source_only"):
                for plan in coverage_plans(schema, table, columns_by_table, edges):
                    if plan["method"] == "direct":
                        observed = measure(
                            f"{schema}.{table}: direct coverage",
                            partial(
                                source.coverage,
                                schema,
                                table,
                                [item["name"] for item in plan["dimensions"]],
                            ),
                        )
                    elif plan["method"] == "parent_derived":
                        observed = measure(
                            f"{schema}.{table}: parent coverage",
                            partial(
                                source.derived_coverage,
                                schema,
                                table,
                                plan["hops"],
                                plan["dimensions"],
                            ),
                        )
                    else:
                        observed = None
                    coverage.append(
                        {
                            "source_schema": schema,
                            "source_table": table,
                            "method": plan["method"],
                            "hops": plan["hops"],
                            "dimensions": [item["name"] for item in plan["dimensions"]],
                            "session_coverage": plan["session_coverage"],
                            "jurisdiction_coverage": plan["jurisdiction_coverage"],
                            "note": plan["note"],
                            "alternate_paths": plan["alternate_paths"],
                            "observed_groups": None
                            if plan["method"] == "unavailable"
                            else observed,
                            "measurement_status": "not_supplied"
                            if plan["method"] == "unavailable"
                            else "measured"
                            if observed is not None
                            else "unresolved",
                            "publisher_availability": "unresolved",
                            "absent_groups": "not_supplied_or_unknown",
                            "null_group_means": "a null jurisdiction or session is unresolved or not supplied, not a publisher zero",
                            "snapshot_status": "present_in_snapshot",
                            "fdw_status": relation["fdw_status"],
                            "mapping_status": "proposed",
                            "table_row_count": relation.get("row_count"),
                        }
                    )
            if checkpoint:
                checkpoint(
                    "relation",
                    {
                        "catalog_baseline": catalog_baseline,
                        "relation": relation,
                        "columns": fields,
                        "nested_fields": [
                            n
                            for n in nested
                            if n["source_schema"] == schema
                            and n["source_table"] == table
                        ],
                        "coverage": [
                            c
                            for c in coverage
                            if c["source_schema"] == schema
                            and c["source_table"] == table
                        ],
                        "errors": list(errors),
                        "status": "incomplete",
                        "reuse_allowed": not _scope_failed(errors, schema, table)
                        and relation["disposition"] != "unresolved",
                    },
                )
        public_names = {
            (r["source_schema"], r["source_table"])
            for r in relations
            if r["disposition"] in ("promote_typed", "retain_source_only")
        }
        for key in keys:
            if (
                key["kind"] == "f"
                and (key["source_schema"], key["source_table"]) in public_names
                and (key["target_schema"], key["target_table"]) in public_names
            ):
                saved_reference = reusable_references.get(key["constraint_name"])
                measurement = (
                    saved_reference["measurement"]
                    if saved_reference
                    else measure(
                        key["constraint_name"], partial(source.references, key)
                    )
                )
                references.append(
                    {
                        **key,
                        "measurement": measurement,
                        "reused_measurement": bool(saved_reference),
                    }
                )
                if checkpoint:
                    checkpoint(
                        "reference",
                        {
                            "catalog_baseline": catalog_baseline,
                            "reference": references[-1],
                            "errors": list(errors),
                            "status": "incomplete",
                            "reuse_allowed": measurement is not None,
                        },
                    )
    identity = {
        "namespaces": measure(
            "identifier namespaces", partial(source.namespaces, schemas[0])
        ),
        "bioguide": measure(
            "BioGuide and name collision counts",
            partial(source.identity_counts, schemas[0]),
        ),
        "cross_provider_links_created": 0,
        "name_join_permitted": False,
    }
    structural = {
        "relations": [
            {k: v for k, v in r.items() if k not in ("reason",)} for r in relations
        ],
        "columns": columns,
        "nested_fields": nested,
        "keys": keys,
        "fdw": fdw,
    }
    gaps = [
        f"{row['source_schema']}.{row['source_table']}: {row['method']} coverage unresolved"
        for row in coverage
        if row.get("measurement_status") == "unresolved"
    ]
    if reusable_relations or reusable_references:
        resume_status = "reused_same_snapshot_baseline"
    elif resume_rejected:
        resume_status = "rejected_different_snapshot_baseline"
    elif prior:
        resume_status = "no_reusable_success"
    else:
        resume_status = "not_requested"
    report = {
        "mapping_version": MAPPING_VERSION,
        "mapping_reviewed": False,
        "errors": errors,
        **structural,
        "coverage": coverage,
        "identity": identity,
        "references": references,
        "owned_columns": owned,
        "schema_deltas": schema_review(relations, owned_measured),
        "source_version": measure("source version", source.version),
        "registered_candidate_artifacts": artifacts,
        "fdw_columns": fdw_columns,
        "approval_evidence": {},
        "completion_gaps": gaps,
        "completion_status": "incomplete"
        if errors or gaps
        else "measurements_recorded_approval_still_required",
        "resume_status": resume_status,
        "resume_policy": "successful relation and reference measurements are reusable only when catalog_baseline matches; incomplete scopes stay visible and are measured again; exported database snapshots are never reused",
        "reconciliation": "Each future pilot reconciles source key/count, accepted/rejected/deferred/promoted, all foreign references and every retained field to immutable artifact/payload/run evidence.",
    }
    report["fingerprint"] = fingerprint(report)
    return report


def load_checkpoints(directory: Path) -> list[tuple[str, dict]]:
    """Read prior checkpoint files. They are evidence, not a database snapshot."""
    if not directory.is_dir():
        raise ValueError("resume directory does not exist")
    loaded = []
    for path in sorted(directory.glob("checkpoint-*.json")):
        phase = path.name.split("-", 2)[2].removesuffix(".json")
        loaded.append((phase, json.loads(path.read_text())))
    return loaded


def main(argv=None) -> int:
    """Write incomplete evidence too; exit nonzero until all acceptance gates pass."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source-dsn-env",
        required=True,
        help="Name of environment variable holding operator-supplied source DSN",
    )
    parser.add_argument(
        "--warehouse-dsn-env",
        required=True,
        help="Name of environment variable holding operator-supplied warehouse DSN",
    )
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--source-schema", action="append", default=None)
    parser.add_argument("--timeout-ms", type=int, default=60000)
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--mapping-review", type=Path)
    parser.add_argument("--restore-attestation", type=Path)
    parser.add_argument("--resume-from", type=Path)
    args = parser.parse_args(argv)
    if args.source_schema is not None and args.source_schema != ["public"]:
        parser.error(
            "This reviewed snapshot audit supports only --source-schema public; identity SQL is public-scoped"
        )
    if args.output.exists() and any(args.output.iterdir()):
        raise ValueError(
            "output already contains evidence; choose a new output directory"
        )
    args.output.mkdir(parents=True, exist_ok=True)
    checkpoint_number = 0

    def checkpoint(phase, evidence):
        """Retain immutable completed evidence; never reuse an unverified partial run."""
        nonlocal checkpoint_number
        checkpoint_number += 1
        serialized = canonical(evidence)
        with (args.output / f"checkpoint-{checkpoint_number:04d}-{phase}.json").open(
            "x"
        ) as stream:
            stream.write(serialized)

    prior = load_checkpoints(args.resume_from) if args.resume_from else None
    report = audit(
        Reader(os.environ[args.source_dsn_env], args.timeout_ms),
        Reader(os.environ[args.warehouse_dsn_env], args.timeout_ms),
        args.source_schema or ["public"],
        checkpoint=checkpoint,
        prior=prior,
    )
    report["approval_evidence"] = approval_inputs(
        report,
        load_approval(args.mapping_review) if args.mapping_review else None,
        load_approval(args.restore_attestation, restore=True)
        if args.restore_attestation
        else None,
    )
    report["fingerprint"] = fingerprint(report)
    destination = args.output / "audit.json"
    if destination.exists():
        raise ValueError(
            "output already contains evidence; choose a new output directory"
        )
    destination.write_text(canonical(report))
    write_outputs(report, args.output)
    try:
        validate(
            report, json.loads(args.baseline.read_text()) if args.baseline else None
        )
    except ValueError:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
