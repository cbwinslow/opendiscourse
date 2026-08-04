"""Read-only reporting for unresolved congressional identities."""
from __future__ import annotations

from datetime import datetime, timezone
import json
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
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "exceptions": rows,
        "voter_audit": "Use the recorded unresolved_people totals from vote ingestion runs; a source-wide voter scan is intentionally opt-in because the FDW cannot efficiently join every person-vote row.",
    }
    target = Path(settings.data_root).expanduser().resolve().parent / "meta" / "exceptions" / "congressional-identities.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    result["report"] = str(target)
    return result
