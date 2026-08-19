"""Read-only reporting for unresolved congressional identities."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .config import settings
from sqlalchemy import exists, func, literal, select, union_all

from .db import session
from .models.core import bill_sponsorship_table, person_identifier_table
from .models.ingest import identity_exception_table


def unresolved_congressional_identities() -> dict[str, Any]:
    """Write unresolved sponsor and voter identifiers without assigning them."""
    sponsorship = bill_sponsorship_table()
    identity_exception = identity_exception_table()
    person_identifier = person_identifier_table()
    unresolved_sponsors = (
        select(
            literal("sponsor").label("kind"),
            sponsorship.c.member_namespace.label("namespace"),
            sponsorship.c.member_external_id.label("external_id"),
            literal("no_canonical_person_identifier").label("reason"),
            func.count().label("references"),
        )
        .where(sponsorship.c.person_id.is_(None))
        .group_by(sponsorship.c.member_namespace, sponsorship.c.member_external_id)
    )
    unresolved_voters = (
        select(
            literal("voter").label("kind"),
            identity_exception.c.namespace,
            identity_exception.c.external_id,
            identity_exception.c.reason,
            func.sum(identity_exception.c.reference_count).label("references"),
        )
        .where(
            ~exists(
                select(person_identifier.c.person_id).where(
                    person_identifier.c.namespace == identity_exception.c.namespace,
                    person_identifier.c.external_id == identity_exception.c.external_id,
                )
            )
        )
        .group_by(
            identity_exception.c.namespace,
            identity_exception.c.external_id,
            identity_exception.c.reason,
        )
    )
    with session() as active_session:
        rows = [
            dict(row)
            for row in active_session.execute(union_all(unresolved_sponsors, unresolved_voters)).mappings()
        ]
    result = {
        "schema": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "exceptions": rows,
        "voter_audit": "Voter exceptions are recorded per committed OpenStates vote page with source artifact and ingestion-run lineage. A source-wide FDW voter scan remains intentionally opt-in.",
    }
    target = (
        Path(settings.data_root).expanduser().resolve().parent
        / "meta"
        / "exceptions"
        / "congressional-identities.json"
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    result["report"] = str(target)
    return result
