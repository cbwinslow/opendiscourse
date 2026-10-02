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


def semantic_mapping(relation: dict, column: dict, owned: list[dict]) -> dict:
    """Propose explicit source-ID, reference and date semantics; never infer by matching names."""
    table = relation["source_table"]
    name = column["source_path"]
    target = relation["owned_target"]
    target_fields = {
        c["source_path"]: c["source_type"]
        for c in owned
        if f"{c['source_schema']}.{c['source_table']}" == target
    }
    retain = {
        "disposition": "retained_source_detail",
        "owned_target": None,
        "transform": "retain original value/type in immutable source record keyed by OpenStates primary key",
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
    ):
        return {
            **retain,
            "transform": "validate calendar and retain original year/month/day precision; no artificial missing month/day; promote only lossless dates after target constraint review",
        }
    proposals = {
        ("opencivicdata_bill", "identifier"): (
            "identifier",
            "preserve official identifier verbatim with session/source key; do not derive federal Congress/type/number from state bill label",
        ),
        ("opencivicdata_bill", "title"): (
            "title",
            "preserve source title verbatim, Unicode-safe text; source keyed, no name inference",
        ),
        ("opencivicdata_legislativesession", "identifier"): (
            "identifier",
            "retain upstream session identifier within its source jurisdiction; do not interpret as federal Congress number",
        ),
        ("opencivicdata_jurisdiction", "name"): (
            "name",
            "retain official jurisdiction name as display attribute; identity uses OCD/source ID",
        ),
        ("opencivicdata_organization", "name"): (
            "name",
            "retain organization display name; source organization ID anchors identity/hierarchy",
        ),
        ("opencivicdata_membership", "role"): (
            "role",
            "retain source role text and dated membership evidence; do not collapse office-holder identity",
        ),
        ("opencivicdata_voteevent", "motion_text"): (
            "question",
            "retain source motion wording; source vote-event identifier and bill/session references define grain",
        ),
        ("opencivicdata_personvote", "option"): (
            "vote",
            "map documented source vote-option vocabulary explicitly to owned option constraint; preserve original option and unresolved voter source reference",
        ),
    }
    proposal = proposals.get((table, name))
    if proposal and proposal[0] in target_fields:
        return {
            "disposition": "typed_searchable",
            "owned_target": f"{target}.{proposal[0]}",
            "transform": proposal[1]
            + f"; target type {target_fields[proposal[0]]}; retain raw source value and provenance; proposal pending semantic/constraint review",
        }
    return retain


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
            "Next: review the relation/field matrices, establish restored-artifact lineage, resolve listed gaps, and approve the baseline before the separate schema/reader and bounded-pilot stories. Issue #100 remains open.",
        ]
    )
    with (destination / "report.md").open("x") as stream:
        stream.write("\n".join(lines) + "\n")


def audit(
    source: Reader, warehouse: Reader, schemas: list[str], checkpoint=None
) -> dict:
    """Measure each database through one exported snapshot; reader probes are availability only."""
    with ExitStack() as contexts:
        for reader in (source, warehouse):
            contexts.enter_context(reader.snapshot())
        report = _audit(source, warehouse, schemas, checkpoint)
    report["snapshot_consistency"] = (
        "independent exported repeatable-read source/warehouse snapshots; FDW probes measure readability only"
    )
    return report


def _audit(
    source: Reader, warehouse: Reader, schemas: list[str], checkpoint=None
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
    owned = (
        measure(
            "owned columns", lambda: warehouse.query("columns", (["core", "fact"],))
        )
        or []
    )
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
            group_columns = [
                c["source_path"]
                for c in fields
                if c["source_path"] in ("jurisdiction_id", "legislative_session_id")
            ]
            sample_columns = [
                c["source_path"]
                for c in fields
                if c["source_path"] in SAFE_SAMPLE_COLUMNS
            ]
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
                not public
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
                column["sample_count"] = (
                    len(samples or []) if path in sample_columns else 0
                )
                column.update(semantic_mapping(relation, column, owned))
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
            if public and group_columns:
                observed = measure(
                    f"{schema}.{table}: coverage",
                    partial(source.coverage, schema, table, group_columns),
                )
                coverage.append(
                    {
                        "source_schema": schema,
                        "source_table": table,
                        "observed_groups": observed,
                        "publisher_availability": "unresolved",
                        "absent_groups": "not_supplied_or_unknown",
                        "snapshot_status": "present_in_snapshot",
                        "fdw_status": relation["fdw_status"],
                        "mapping_status": "proposed",
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
                        "reuse_allowed": False,
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
                references.append(
                    {
                        **key,
                        "measurement": measure(
                            key["constraint_name"], partial(source.references, key)
                        ),
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
                            "reuse_allowed": False,
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
    existing = {f"{c['source_schema']}.{c['source_table']}" for c in owned}
    deltas = [
        {
            "source_table": r["source_table"],
            "proposed_target": r["owned_target"],
            "status": "exists: field compatibility review required"
            if r["owned_target"] in existing
            else "target absent or undecided: separate schema story",
        }
        for r in relations
        if r["disposition"] in ("promote_typed", "retain_source_only")
    ]
    report = {
        "mapping_version": MAPPING_VERSION,
        "mapping_reviewed": False,
        "errors": errors,
        **structural,
        "coverage": coverage,
        "identity": identity,
        "references": references,
        "owned_columns": owned,
        "schema_deltas": deltas,
        "source_version": measure("source version", source.version),
        "registered_candidate_artifacts": artifacts,
        "fdw_columns": fdw_columns,
        "approval_evidence": {},
        "completion_gaps": [
            "parent-derived jurisdiction/session coverage incomplete; direct groups alone cannot approve source-wide baseline"
        ],
        "completion_status": "incomplete",
        "resume_policy": "resume unavailable: rerun in fresh directory; never reuse partial/unverified evidence or expired exported snapshots",
        "reconciliation": "Each future pilot reconciles source key/count, accepted/rejected/deferred/promoted, all foreign references and every retained field to immutable artifact/payload/run evidence.",
    }
    report["fingerprint"] = fingerprint(report)
    return report


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

    report = audit(
        Reader(os.environ[args.source_dsn_env], args.timeout_ms),
        Reader(os.environ[args.warehouse_dsn_env], args.timeout_ms),
        args.source_schema or ["public"],
        checkpoint=checkpoint,
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
