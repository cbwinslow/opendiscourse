"""Link political divisions to dated Census boundaries by identifier (Story 10.3, ADR-0006).

A division is who a member represents (an Open Civic Data id); a boundary is a TIGER shape of
one vintage. The only join key is the official code: state FIPS from the OCD state code plus the
district code equals the TIGER GEOID. Display names are never compared. The U.S. House uses the
119th-Congress plan and state legislatures the 2024 plan, as ``inventory/geography-vintages.yaml``
requires; a link to any other vintage is refused.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from datetime import date
from functools import cache
from pathlib import Path
from typing import Any

from ..db import connect
from .base import IngestionRun

_REPO_ROOT = Path(__file__).resolve().parents[3]
_QUERY_ROOT = _REPO_ROOT / "sql" / "query" / "geography"
#: Reviewed Census-to-OCD pairs for districts that share no code (built by
#: ``scripts/build_ocd_sld_crosswalk.py``; every pair passed its checks before it was written).
CROSSWALK_FILE = _REPO_ROOT / "inventory" / "geography" / "ocd-sld-crosswalk-2024.csv"

#: Official two-letter codes used in OCD ids and their Census state FIPS codes.
STATE_FIPS: dict[str, str] = {
    "al": "01", "ak": "02", "az": "04", "ar": "05", "ca": "06", "co": "08", "ct": "09", "de": "10",
    "dc": "11", "fl": "12", "ga": "13", "hi": "15", "id": "16", "il": "17", "in": "18", "ia": "19",
    "ks": "20", "ky": "21", "la": "22", "me": "23", "md": "24", "ma": "25", "mi": "26", "mn": "27",
    "ms": "28", "mo": "29", "mt": "30", "ne": "31", "nv": "32", "nh": "33", "nj": "34", "nm": "35",
    "ny": "36", "nc": "37", "nd": "38", "oh": "39", "ok": "40", "or": "41", "pa": "42", "ri": "44",
    "sc": "45", "sd": "46", "tn": "47", "tx": "48", "ut": "49", "vt": "50", "va": "51", "wa": "53",
    "wv": "54", "wi": "55", "wy": "56", "as": "60", "gu": "66", "mp": "69", "pr": "72", "vi": "78",
}  # fmt: skip

CONGRESS = 119
BOUNDARY_VINTAGE = 2024
LEGISLATIVE_YEAR = 2024
# The 119th Congress runs from the 3 January after the November 2024 election to the next 3 January.
CD_VALID_FROM = date(2025, 1, 3)
CD_VALID_TO = date(2027, 1, 3)


@cache
def _query(name: str) -> str:
    """Read a version-controlled geography query once per process."""
    return (_QUERY_ROOT / f"{name}.sql").read_text()


def load_crosswalk(path: Path = CROSSWALK_FILE) -> list[dict[str, str]]:
    """Read the reviewed pairs; refuse a file with a repeated district or division id."""
    with path.open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    districts = [(row["chamber"], row["census_geoid"]) for row in rows]
    divisions = [row["ocd_division_id"] for row in rows]
    if len(set(districts)) != len(districts) or len(set(divisions)) != len(divisions):
        raise ValueError(f"{path.name}: a district or division id is repeated")
    return rows


def _state_params() -> dict[str, list[str]]:
    return {"postals": list(STATE_FIPS), "fips": list(STATE_FIPS.values())}


def validate_vintage(congress: int, legislative_year: int, boundary_vintage: int) -> None:
    """Refuse a link request for a plan other than the one the geography calendar names."""
    if congress != CONGRESS:
        raise ValueError(f"congressional links are for the {CONGRESS}th Congress, not {congress}")
    if legislative_year != LEGISLATIVE_YEAR:
        raise ValueError(f"state legislative links are for the {LEGISLATIVE_YEAR} plan, not {legislative_year}")
    if boundary_vintage != BOUNDARY_VINTAGE:
        raise ValueError(
            f"boundary vintage {boundary_vintage} cannot back congress {congress} / "
            f"legislative year {legislative_year}; expected {BOUNDARY_VINTAGE}"
        )


@dataclass
class LinkReport:
    """What a linking run did, and what it could not link and why."""

    seeded_divisions: int = 0
    new_links: int = 0
    crosswalk_links: int = 0
    retired_divisions: int = 0
    families: list[dict[str, Any]] = field(default_factory=list)
    unlinked_divisions: list[dict[str, Any]] = field(default_factory=list)

    def unlinked_by_reason(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for row in self.unlinked_divisions:
            counts[row["reason"]] = counts.get(row["reason"], 0) + 1
        return counts


def link_division_boundaries(
    *,
    congress: int = CONGRESS,
    legislative_year: int = LEGISLATIVE_YEAR,
    boundary_vintage: int = BOUNDARY_VINTAGE,
) -> LinkReport:
    """Seed state-legislative divisions, link every division it can, and report the rest.

    Idempotent: a second run inserts nothing. Raises ``ValueError`` before touching the
    database when the requested plan is not the one this story links, and after the load when
    any stored link points at the wrong vintage or boundary family.
    """
    validate_vintage(congress, legislative_year, boundary_vintage)
    report = LinkReport()
    states = _state_params()
    parameters = {
        "action": "link_division_boundaries",
        "congress": congress,
        "legislative_year": legislative_year,
        "boundary_vintage": boundary_vintage,
    }
    with IngestionRun("census.tiger", parameters, mode="manual") as run:
        pairs = load_crosswalk()
        keys = [f"{row['chamber']}:{row['census_geoid']}" for row in pairs]
        with connect() as conn, conn.cursor() as cur:
            cur.execute(
                _query("retire_phantom_divisions"),
                {"keys": keys, "ocd_ids": [row["ocd_division_id"] for row in pairs]},
            )
            report.retired_divisions = len(cur.fetchall())
            crosswalk_params = {
                "geoids": [row["census_geoid"] for row in pairs],
                "chambers": [row["chamber"] for row in pairs],
                "ocd_ids": [row["ocd_division_id"] for row in pairs],
                "names": [row["census_name"] for row in pairs],
                "vintage": boundary_vintage,
                "legislative_year": legislative_year,
            }
            cur.execute(_query("create_crosswalk_divisions"), crosswalk_params)
            report.seeded_divisions += len(cur.fetchall())
            cur.execute(_query("link_crosswalk_divisions"), crosswalk_params)
            report.crosswalk_links = len(cur.fetchall())
            cur.execute(_query("seed_sld_divisions"), {**states, "vintage": boundary_vintage, "skip_keys": keys})
            report.seeded_divisions = len(cur.fetchall())
            cur.execute(
                _query("link_divisions"),
                {
                    **states,
                    "vintage": boundary_vintage,
                    "congress": congress,
                    "legislative_year": legislative_year,
                    "cd_valid_from": CD_VALID_FROM,
                    "cd_valid_to": CD_VALID_TO,
                },
            )
            report.new_links = len(cur.fetchall())
            check = {"vintage": boundary_vintage, "congress": congress, "legislative_year": legislative_year}
            cur.execute(_query("wrong_vintage_links"), check)
            wrong = cur.fetchall()
            if wrong:
                pairs = ", ".join(f"{r['ocd_division_id']}->{r['geography_type']}@{r['boundary_vintage']}" for r in wrong)
                raise ValueError(f"division links point at the wrong boundary vintage: {pairs}")
            cur.execute(_query("link_report"), {"vintage": boundary_vintage})
            report.families = list(cur.fetchall())
            cur.execute(_query("unlinked_divisions"))
            report.unlinked_divisions = list(cur.fetchall())
            conn.commit()
        run.record_count = report.new_links + report.seeded_divisions + report.crosswalk_links
    return report
