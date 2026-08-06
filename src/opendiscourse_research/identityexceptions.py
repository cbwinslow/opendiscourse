"""Read-only reporting for unresolved congressional identities."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .config import settings
from .db import connect
from .repositories.legislation import _query


def unresolved_congressional_identities() -> dict[str, Any]:
    """Write unresolved sponsor and voter identifiers without assigning them."""
    with connect() as conn, conn.cursor() as cur:
        cur.execute(_query("unresolved_identity_exceptions"))
        rows = [dict(row) for row in cur.fetchall()]
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
