"""Canonical people seeding from the approved OpenStates reference snapshot."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from .config import settings
from .ingestion.base import IngestionRun
from .repositories.legislation import (
    resolve_bill_sponsorship_people,
    sync_openstates_federal_people,
)


def load_openstates_federal_people() -> dict[str, Any]:
    """Load the federal OpenStates people baseline without modifying its source snapshot."""
    parameters = {
        "source": "openstates_source.opencivicdata_person",
        "jurisdiction": "ocd-jurisdiction/country:us/government",
        "role": "canonical_baseline",
    }
    with IngestionRun("openstates.legislation", parameters, mode="backfill") as run:
        assert run.conn is not None
        counts = sync_openstates_federal_people(run.conn)
        counts["sponsorship_links_resolved"] = resolve_bill_sponsorship_people(run.conn)
        run.record_count = counts["people"]
        run.conn.commit()

    result = {
        "schema": 1,
        "kind": "openstates_people_load",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        **counts,
        "next": "Enrich people from Congress.gov without replacing OpenStates baseline identities.",
    }
    target = (
        Path(settings.data_root).expanduser().resolve().parent
        / "meta"
        / "load"
        / "openstates-people.json"
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    result["report"] = str(target)
    return result
