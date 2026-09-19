"""Coverage comparator: official expected counts versus loaded rows, per Congress.

Warehouse read-only (it writes only metadata caches under the lake). "Expected" comes from an official manifest or index where one exists
(GovInfo BILLSTATUS, Senate.gov vote menus, House Clerk roll index). Actions and
members have no official manifest, so their expectation carries a named
lower-trust basis (``lake_archive``, ``legislators_yaml``) and is never presented
as official. An official fetch that fails yields ``None`` (unknown), never zero.
"""

from __future__ import annotations

import json
import os
import tempfile
import zipfile
import zlib
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

import yaml
from sqlalchemy import select

from .config import settings
from .db import session
from .lake import locate
from .legreconcile import _bill_details
from .providers.official_counts import OfficialCountError, OfficialCounts
from .repositories.artifacts import current_artifact_table
from .repositories.coverage import loaded_counts

FIRST_CONGRESS = 108
LAST_CONGRESS = 119
BILL_TYPES = ("hconres", "hjres", "hr", "hres", "s", "sconres", "sjres", "sres")
SENATE_SESSIONS = (1, 2)
VOLATILE_MAX_AGE = timedelta(days=1)
_YAML_LOADER = getattr(yaml, "CSafeLoader", yaml.SafeLoader)


def congress_years(congress: int) -> tuple[int, int]:
    """Return the two calendar years a Congress sits (108th = 2003-2004)."""
    first = 2003 + 2 * (congress - FIRST_CONGRESS)
    return first, first + 1


def congress_span(congress: int) -> tuple[date, date]:
    """Return the first day and the day after the last day of a Congress."""
    first, _ = congress_years(congress)
    return date(first, 1, 3), date(first + 2, 1, 3)


def cell(expected: int | None, loaded: int, basis: str) -> dict[str, Any]:
    """Compare one expected/loaded pair; unknown expectation is not zero."""
    if expected is None:
        return {
            "expected": None,
            "loaded": loaded,
            "missing": None,
            "surplus": None,
            "status": "unknown",
            "basis": basis,
        }
    return {
        "expected": expected,
        "loaded": loaded,
        "missing": max(expected - loaded, 0),
        "surplus": max(loaded - expected, 0),
        "status": "complete" if loaded >= expected else "incomplete",
        "basis": basis,
    }


def _meta_dir() -> Path:
    """Return the metadata-only directory for coverage caches."""
    return Path(settings.data_root).expanduser().resolve().parent / "meta" / "coverage"


def _read_json(path: Path) -> dict[str, Any]:
    """Read a cache file; a missing or corrupt cache is simply empty."""
    try:
        payload = json.loads(path.read_text())
    except (OSError, ValueError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    """Atomically write a metadata cache."""
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, name = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    with os.fdopen(handle, "w") as stream:
        stream.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    Path(name).replace(path)


@dataclass
class OfficialCache:
    """Persistent cache of successful official counts, with a list of failures."""

    path: Path
    refresh: bool = False
    now: Callable[[], datetime] = lambda: datetime.now(UTC)

    def __post_init__(self) -> None:
        raw = _read_json(self.path).get("entries", {})
        self.entries: dict[str, Any] = {}
        for key, entry in (raw.items() if isinstance(raw, dict) else ()):
            try:
                datetime.fromisoformat(entry["fetched_at"])
                int(entry["value"])
            except (KeyError, TypeError, ValueError):
                continue  # a malformed entry is refetched, never trusted
            self.entries[key] = entry
        self.errors: list[str] = []
        self.requests = 0

    def get(self, key: str, fetch: Callable[[], int], volatile: bool = False) -> int | None:
        """Return a cached count, fetching once when absent, stale, or refreshed.

        An entry cached while its source was still changing (``volatile``) is
        refetched after a day, and once more after the source stops changing.
        A failed refetch falls back to the stale value rather than to unknown.
        """
        entry = self.entries.get(key)
        if entry is not None and not self.refresh:
            age = self.now() - datetime.fromisoformat(entry["fetched_at"])
            if not (volatile or entry.get("volatile")) or (
                volatile and age < VOLATILE_MAX_AGE
            ):
                return entry["value"]
        self.requests += 1
        try:
            value = fetch()
        except OfficialCountError as exc:
            self.errors.append(f"{key}: {exc}")
            return entry["value"] if entry is not None else None
        self.entries[key] = {
            "value": value,
            "fetched_at": self.now().isoformat(),
            "volatile": volatile,
        }
        return value

    def save(self) -> None:
        """Persist successful entries."""
        _write_json(self.path, {"schema": 1, "entries": self.entries})


def _locate_zip(congress: int, bill_type: str) -> Path | None:
    """Find one BILLSTATUS zip through the lake registry (any configured root)."""
    return locate("govinfo.billstatus.zip", congress=congress, bill_type=bill_type)


def scan_lake(
    congress: int,
    cache_path: Path,
    locate_zip: Callable[[int, str], Path | None] = _locate_zip,
) -> dict[str, Any] | None:
    """Count XML bills and actions per type in the (unverified) BILLSTATUS zips.

    Results are cached per archive keyed by path, size and mtime, so reruns are
    instant. An unreadable archive is reported (``unreadable``), never fatal.
    """
    cache = _read_json(cache_path).get("archives", {})
    by_type: dict[str, dict[str, Any]] = {}
    for bill_type in BILL_TYPES:
        archive = locate_zip(congress, bill_type)
        if archive is None or not archive.is_file():
            continue
        stat = archive.stat()
        key = f"{archive}:{stat.st_size}:{int(stat.st_mtime)}"
        if key not in cache:
            bills = actions = malformed = 0
            try:
                with zipfile.ZipFile(archive) as bundle:
                    for member in bundle.namelist():
                        if not member.endswith(".xml"):
                            continue
                        try:
                            detail = _bill_details(bundle.read(member))
                        except (ElementTree.ParseError, ValueError):
                            detail = None
                        if detail is None:
                            malformed += 1
                            continue
                        bills += 1
                        actions += detail["actions"]
                entry: dict[str, Any] = {
                    "bills": bills,
                    "actions": actions,
                    "malformed": malformed,
                }
            except (zipfile.BadZipFile, OSError, zlib.error) as exc:
                entry = {"bills": 0, "actions": 0, "malformed": 0, "unreadable": str(exc)}
            cache[key] = entry
            _write_json(cache_path, {"schema": 1, "archives": cache})
        by_type[bill_type] = cache[key]
    return by_type or None


def _as_date(value: Any) -> date | None:
    """Coerce a YAML date or ISO string; anything else is None."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return None


def expected_members(
    paths: Iterable[Path], congresses: Iterable[int]
) -> dict[int, set[str]]:
    """BioGuide ids with a term overlapping each Congress, from legislators YAML."""
    spans = {c: congress_span(c) for c in congresses}
    result: dict[int, set[str]] = {c: set() for c in spans}
    for path in paths:
        for record in yaml.load(path.read_bytes(), Loader=_YAML_LOADER) or []:
            if not isinstance(record, dict) or not isinstance(record.get("id") or {}, dict):
                continue
            bioguide = str((record.get("id") or {}).get("bioguide") or "").strip()
            if not bioguide:
                continue
            for term in record.get("terms") or []:
                if not isinstance(term, dict):
                    continue
                start, end = _as_date(term.get("start")), _as_date(term.get("end"))
                if start is None or end is None:
                    continue
                for congress, (first, after) in spans.items():
                    if start < after and end > first:
                        result[congress].add(bioguide)
    return result


def _bills_section(
    congress: int,
    official: dict[str, int | None],
    loaded: dict[str, int],
    lake: dict[str, dict[str, int]] | None,
) -> dict[str, Any]:
    """Bills per type and in total, with the lake shown as a separate column."""
    by_type: dict[str, Any] = {}
    for bill_type in BILL_TYPES:
        row = cell(official[bill_type], loaded.get(bill_type, 0), "govinfo_manifest")
        on_disk = (lake or {}).get(bill_type, {}).get("bills")
        row["on_disk"] = on_disk
        row["missing_on_disk"] = (
            None
            if official[bill_type] is None or lake is None
            else max(official[bill_type] - (on_disk or 0), 0)
        )
        by_type[bill_type] = row
    known = all(v is not None for v in official.values())
    total = cell(
        sum(v for v in official.values() if v is not None) if known else None,
        sum(loaded.get(t, 0) for t in BILL_TYPES),
        "govinfo_manifest",
    )
    if any(row["status"] == "incomplete" for row in by_type.values()):
        total["status"] = "incomplete"  # a surplus elsewhere must not hide a gap
    total["on_disk"] = (
        None if lake is None else sum(v["bills"] for v in lake.values())
    )
    total["loaded_other_types"] = {
        t: n for t, n in loaded.items() if t not in BILL_TYPES
    }
    return {**total, "by_type": by_type}


def build_report(
    congresses: list[int],
    *,
    official: OfficialCounts,
    cache: OfficialCache,
    loaded: dict[str, Any],
    lake: Callable[[int], dict[str, dict[str, int]] | None],
    members: dict[int, set[str]],
    today: date | None = None,
    progress: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    """Assemble the coverage report from injected sources (no globals, no writes)."""
    today = today or datetime.now(UTC).date()
    first_official = cache.get("billstatus:first_congress", official.first_billstatus_congress)
    confirmed: bool | str = (
        "unknown" if first_official is None else first_official == FIRST_CONGRESS
    )
    rows: list[dict[str, Any]] = []
    for congress in congresses:
        years = congress_years(congress)
        in_progress = congress_span(congress)[1] > today
        volatile_year = {y: y >= today.year for y in years}
        bills_official = {
            t: cache.get(
                f"billstatus:{congress}:{t}",
                lambda t=t, c=congress: official.billstatus(c, t),
                volatile=in_progress,
            )
            for t in BILL_TYPES
        }
        senate_parts = [
            cache.get(
                f"senate:{congress}:{s}",
                lambda s=s, c=congress: official.senate_votes(c, s),
                volatile=in_progress,
            )
            for s in SENATE_SESSIONS
        ]
        house_parts = [
            cache.get(
                f"house:{y}",
                lambda y=y: official.house_rolls(y),
                volatile=volatile_year[y],
            )
            for y in years
        ]

        def total(parts: list[int | None]) -> int | None:
            return None if None in parts else sum(p for p in parts if p is not None)

        lake_types = lake(congress)
        bills_loaded = loaded["bills"].get(congress, {})
        bills = _bills_section(congress, bills_official, bills_loaded, lake_types)

        lake_verified = (
            lake_types is not None
            and all(v is not None for v in bills_official.values())
            and all(
                lake_types.get(t, {}).get("bills", 0) == bills_official[t]
                and not lake_types.get(t, {}).get("malformed")
                and not lake_types.get(t, {}).get("unreadable")
                for t in BILL_TYPES
            )
        )
        actions = cell(
            None
            if lake_types is None
            else sum(v["actions"] for v in lake_types.values()),
            loaded["actions"].get(congress, 0),
            "lake_archive" if lake_verified else "lake_archive_unverified",
        )

        chambers = loaded["roll_calls"].get(congress, {})
        house = chambers.get("house", {})
        senate = chambers.get("senate", {})
        votes = {
            "house": cell(total(house_parts), house.get("roll_calls", 0), "house_clerk_index"),
            "senate": cell(total(senate_parts), senate.get("roll_calls", 0), "senate_vote_menu"),
            "member_votes_loaded": {
                "house": house.get("member_votes", 0),
                "senate": senate.get("member_votes", 0),
            },
            "roll_calls_without_votes": {
                "house": house.get("without_votes", 0),
                "senate": senate.get("without_votes", 0),
            },
        }
        expected_people = members.get(congress) or set()
        known_members = bool(expected_people)  # no legislators file means unknown, not 0
        people = cell(
            len(expected_people) if known_members else None,
            len(expected_people & loaded["bioguide_ids"]),
            "legislators_yaml",
        )
        memberships = cell(
            len(expected_people) if known_members else None,
            len(expected_people & loaded["memberships"].get(congress, set())),
            "legislators_yaml",
        )
        rows.append(
            {
                "congress": congress,
                "years": list(years),
                "in_progress": in_progress,
                "bills": bills,
                "actions": actions,
                "votes": votes,
                "members": {"people": people, "memberships": memberships},
            }
        )
        if progress:
            progress(f"Coverage: Congress {congress}")
    return {
        "schema": 1,
        "kind": "coverage",
        "generated_at": datetime.now(UTC).isoformat(),
        "warehouse_read_only": True,
        "start_confirmed": {
            "first_official_congress": first_official,
            "confirmed": confirmed,
        },
        "congresses": rows,
        "unattributed": {
            "runs_without_code_version": loaded["runs_unattributed"],
            "runs_total": loaded["runs_total"],
            "fec_stage_rows_estimate": (
                loaded["fec_stage_rows_estimate"]
                if (loaded["fec_stage_rows_estimate"] or -1) >= 0
                else None  # never analysed or absent: unknown, not zero
            ),
        },
        "official_requests": cache.requests,
        "errors": cache.errors,
    }


def legislators_paths() -> list[Path]:
    """Current legislators YAML files, from the artifact registry."""
    view = current_artifact_table()
    with session() as active:
        rows = active.execute(
            select(view.c.local_path).where(view.c.dataset_id == "congress.legislators")
        ).all()
    return [Path(r[0]) for r in rows if r[0] and Path(r[0]).is_file()]


def normalize_congresses(congresses: list[int] | None) -> list[int]:
    """Validate, de-duplicate and sort a Congress selection (default: all 108-119)."""
    selected = sorted(set(congresses or range(FIRST_CONGRESS, LAST_CONGRESS + 1)))
    bad = [c for c in selected if not FIRST_CONGRESS <= c <= LAST_CONGRESS]
    if bad:
        raise ValueError(
            f"Congress must be {FIRST_CONGRESS}-{LAST_CONGRESS}: {', '.join(map(str, bad))}"
        )
    return selected


def coverage_report(
    congresses: list[int] | None = None,
    refresh_official: bool = False,
    report: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    """Build the live coverage report and persist it under the metadata lake."""
    selected = normalize_congresses(congresses)
    meta = _meta_dir()
    cache = OfficialCache(meta / "official.json", refresh=refresh_official)
    paths = legislators_paths()
    if not paths:
        cache.errors.append("legislators: no congress.legislators artifact file found")
    try:
        result = build_report(
            selected,
            official=OfficialCounts(),
            cache=cache,
            loaded=loaded_counts(),
            lake=lambda c: scan_lake(c, meta / "lake.json"),
            members=expected_members(paths, selected) if paths else {},
            progress=report,
        )
    finally:
        cache.save()  # keep paced fetches even when a later step fails
    _write_json(meta / "latest.json", result)
    return result


def format_table(result: dict[str, Any]) -> str:
    """Render the report as a compact fixed-width table."""

    def fmt(section: dict[str, Any]) -> str:
        exp = "?" if section["expected"] is None else f"{section['expected']:,}"
        return f"{section['loaded']:,}/{exp}"

    start = result["start_confirmed"]
    lines = [
        (
            "First Congress with official BILLSTATUS: "
            f"{start['first_official_congress']} (confirmed: {start['confirmed']})"
        ),
        (
            "loaded/expected   bills      actions(lake)   house rc    senate rc"
            "   memberships(yaml)"
        ),
    ]
    for row in result["congresses"]:
        mark = "*" if row["in_progress"] else " "
        lines.append(
            f"{row['congress']}{mark:<2}"
            f"{fmt(row['bills']):>17}{fmt(row['actions']):>16}"
            f"{fmt(row['votes']['house']):>12}{fmt(row['votes']['senate']):>13}"
            f"{fmt(row['members']['memberships']):>14}"
        )
    unattributed = result["unattributed"]
    lines.append(
        f"Unattributed runs: {unattributed['runs_without_code_version']}/"
        f"{unattributed['runs_total']}; FEC stage rows (estimate): "
        f"{'?' if unattributed['fec_stage_rows_estimate'] is None else format(unattributed['fec_stage_rows_estimate'], ',')}"
    )
    if result["errors"]:
        lines.append(f"{len(result['errors'])} official fetches failed (cells are '?').")
    lines.append("* Congress in progress: expected counts grow.")
    return "\n".join(lines)
