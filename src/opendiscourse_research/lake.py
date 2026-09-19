"""Lake registry: logical roots, path locators and per-directory dispositions.

Where data lives is configuration, not code. ``inventory/lake_layout.yaml``
names logical roots (``active``, ``legacy``, ``project``), *locations* (path
templates tried in order) and *areas* (every directory or file the inventory
should recognise, with a disposition). Roots are resolved from settings, so a
different machine, or a folder that moved, changes a setting or one YAML line.

The scan is read-only: it never hashes, never follows symlinks, and does not
descend into ``hold`` (sensitive) areas.
"""

from __future__ import annotations

import fnmatch
import os
from collections import defaultdict
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .config import settings

LAYOUT_FILE = Path(__file__).resolve().parents[2] / "inventory" / "lake_layout.yaml"
DISPOSITIONS = ("adopt", "keep", "hold", "review", "prune")
KINDS = (
    "raw",
    "derived",
    "upstream_checkout",
    "code",
    "database",
    "scratch",
    "link",
)


class LakeError(RuntimeError):
    """A location could not be resolved; the message says how to fix it."""


class LayoutError(ValueError):
    """The layout file is malformed."""


@dataclass(frozen=True)
class Candidate:
    """One place a location may live: a root name and a relative path template."""

    root: str
    path: str


@dataclass(frozen=True)
class Location:
    """A named locator: the first existing candidate wins."""

    name: str
    dataset_id: str | None
    trust: str | None
    candidates: tuple[Candidate, ...]


@dataclass(frozen=True)
class Area:
    """A recognised directory or file (wildcards per path segment) and its disposition."""

    root: str
    path: str
    dataset_id: str | None
    kind: str
    disposition: str
    trust: str | None
    reason: str

    @property
    def segments(self) -> tuple[str, ...]:
        return tuple(self.path.split("/"))


@dataclass(frozen=True)
class Layout:
    """The parsed, validated layout file."""

    roots: dict[str, str]
    locations: dict[str, Location]
    areas: tuple[Area, ...]


def _relative(path: str, where: str) -> str:
    """Reject absolute or escaping paths so the layout stays machine-independent."""
    parts = path.split("/")
    if not path or path.startswith(("/", "~")) or ".." in parts or ":" in parts[0]:
        raise LayoutError(f"{where}: path must be relative and inside its root: {path!r}")
    return path


def load_layout(path: Path | None = None) -> Layout:
    """Load and validate the layout file."""
    source = Path(path or LAYOUT_FILE)
    raw = yaml.safe_load(source.read_text())
    if not isinstance(raw, dict) or raw.get("version") != 1:
        raise LayoutError(f"{source}: expected a mapping with version: 1")
    roots = dict(raw.get("roots") or {})
    if not roots:
        raise LayoutError(f"{source}: no roots defined")
    locations: dict[str, Location] = {}
    for name, item in (raw.get("locations") or {}).items():
        candidates = []
        for candidate in item.get("candidates") or []:
            if candidate["root"] not in roots:
                raise LayoutError(f"location {name}: unknown root {candidate['root']!r}")
            candidates.append(
                Candidate(candidate["root"], _relative(candidate["path"], f"location {name}"))
            )
        if not candidates:
            raise LayoutError(f"location {name}: no candidates")
        locations[name] = Location(
            name, item.get("dataset_id"), item.get("trust"), tuple(candidates)
        )
    areas = []
    for item in raw.get("areas") or []:
        where = f"area {item.get('root')}:{item.get('path')}"
        if item.get("root") not in roots:
            raise LayoutError(f"{where}: unknown root")
        if item.get("disposition") not in DISPOSITIONS:
            raise LayoutError(f"{where}: disposition must be one of {DISPOSITIONS}")
        if item.get("kind") not in KINDS:
            raise LayoutError(f"{where}: kind must be one of {KINDS}")
        if not item.get("reason"):
            raise LayoutError(f"{where}: a reason is required")
        areas.append(
            Area(
                item["root"],
                _relative(item["path"], where),
                item.get("dataset_id"),
                item["kind"],
                item["disposition"],
                item.get("trust"),
                item["reason"],
            )
        )
    return Layout(roots, locations, tuple(areas))


def _optional(value: str | None) -> Path | None:
    return Path(value).expanduser().resolve() if value else None


def resolve_roots() -> dict[str, Path | None]:
    """Map logical root names to directories from settings; unset roots are None."""
    return {
        "active": Path(settings.data_root).expanduser().resolve().parent,
        "legacy": _optional(settings.legacy_lake_root),
        "project": _optional(settings.legacy_project_root),
    }


def locate(
    name: str,
    *,
    roots: Mapping[str, Path | None] | None = None,
    layout: Layout | None = None,
    **keys: object,
) -> Path | None:
    """Return the first existing candidate of a named location, or None."""
    layout = layout or load_layout()
    roots = resolve_roots() if roots is None else roots
    try:
        location = layout.locations[name]
    except KeyError:
        raise LakeError(f"Unknown lake location {name!r}") from None
    for value in keys.values():
        if os.sep in str(value) or ".." in str(value):
            raise LakeError(f"Unsafe value for a path template: {value!r}")
    for candidate in location.candidates:
        base = roots.get(candidate.root)
        if base is None:
            continue
        try:
            relative = candidate.path.format(**keys)
        except KeyError as exc:
            raise LakeError(f"Location {name!r} needs a value for {exc}") from exc
        found = base / relative
        if found.exists() or found.is_symlink():
            return found
    return None


def require_location(name: str, **keys: object) -> Path:
    """Like :func:`locate` but raise an actionable error when nothing exists."""
    found = locate(name, **keys)
    if found is not None:
        return found
    layout = load_layout()
    tried = ", ".join(f"{c.root}:{c.path}" for c in layout.locations[name].candidates)
    raise LakeError(
        f"Lake location {name!r} not found (tried {tried}). Set LEGACY_LAKE_ROOT / "
        "LEGACY_PROJECT_ROOT, or edit inventory/lake_layout.yaml."
    )


def _segment_match(pattern: Sequence[str], parts: Sequence[str]) -> bool:
    return all(fnmatch.fnmatchcase(p, pat) for p, pat in zip(parts, pattern, strict=False))


def _exact(area: Area, parts: Sequence[str]) -> bool:
    return len(area.segments) == len(parts) and _segment_match(area.segments, parts)


def _could_contain(area: Area, parts: Sequence[str]) -> bool:
    return len(area.segments) > len(parts) and _segment_match(area.segments, parts)


def measure(path: Path) -> dict[str, Any]:
    """Size, file count and newest mtime of a file or tree; symlinks are not followed."""
    size = files = 0
    newest = 0.0
    errors = 0
    stack = [path]
    while stack:
        current = stack.pop()
        try:
            info = current.lstat()
            if not os.path.isdir(current) or current.is_symlink():
                size += info.st_size
                files += 1
                newest = max(newest, info.st_mtime)
                continue
            with os.scandir(current) as entries:
                stack.extend(Path(entry.path) for entry in entries)
        except OSError:
            errors += 1
    return {"size_bytes": size, "files": files, "newest_mtime": newest or None, "errors": errors}


def _entry_kind(path: Path) -> str:
    if path.is_symlink():
        return "link"
    return "dir" if path.is_dir() else "file"


def _registered(path: Path, registered: Sequence[str]) -> int:
    prefix = str(path) + os.sep
    return sum(1 for item in registered if item == str(path) or item.startswith(prefix))


def scan_root(
    root_name: str,
    base: Path,
    layout: Layout,
    *,
    registered: Sequence[str] = (),
    measure_hold: bool = False,
    progress: Callable[[str], None] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Classify everything under one root; returns (areas, unclassified)."""
    areas = [a for a in layout.areas if a.root == root_name]
    found: list[dict[str, Any]] = []
    unclassified: list[dict[str, Any]] = []

    def record(parts: tuple[str, ...], area: Area | None) -> None:
        path = base.joinpath(*parts)
        kind = _entry_kind(path)
        held = area is not None and area.disposition == "hold" and not measure_hold
        if kind == "link" or held:
            stats: dict[str, Any] = {"size_bytes": None, "files": None, "newest_mtime": None}
        else:
            stats = measure(path)
        row = {
            "root": root_name,
            "path": "/".join(parts),
            "fs_kind": kind,
            "registered_artifacts": _registered(path, registered),
            **stats,
        }
        if kind == "link":
            row["link_target"] = os.readlink(path)
        if progress:
            progress(f"Inventory {root_name}: {row['path']}")
        if area is None:
            unclassified.append(row)
        else:
            found.append(
                {
                    **row,
                    "disposition": area.disposition,
                    "kind": area.kind,
                    "dataset_id": area.dataset_id,
                    "trust": area.trust,
                    "reason": area.reason,
                }
            )

    def walk(parts: tuple[str, ...]) -> None:
        try:
            names = sorted(os.listdir(base.joinpath(*parts)))
        except OSError:
            return
        for name in names:
            child = (*parts, name)
            area = next((a for a in areas if _exact(a, child)), None)
            descend = any(_could_contain(a, child) for a in areas) and not (
                base.joinpath(*child).is_symlink() or not base.joinpath(*child).is_dir()
            )
            if descend:
                walk(child)
            else:
                record(child, area)

    walk(())
    return found, unclassified


def inventory(
    *,
    layout: Layout | None = None,
    roots: Mapping[str, Path | None] | None = None,
    registered: Sequence[str] = (),
    measure_hold: bool = False,
    only_root: str | None = None,
    progress: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    """Report every configured root against the layout, without changing anything."""
    layout = layout or load_layout()
    roots = resolve_roots() if roots is None else roots
    report_roots: dict[str, Any] = {}
    all_areas: list[dict[str, Any]] = []
    unclassified: list[dict[str, Any]] = []
    for name in layout.roots:
        if only_root and name != only_root:
            continue
        base = roots.get(name)
        if base is None:
            report_roots[name] = {"status": "not_configured", "path": None}
            continue
        if not base.is_dir():
            report_roots[name] = {"status": "missing", "path": str(base)}
            continue
        report_roots[name] = {"status": "present", "path": str(base)}
        areas, loose = scan_root(
            name,
            base,
            layout,
            registered=registered,
            measure_hold=measure_hold,
            progress=progress,
        )
        all_areas.extend(areas)
        unclassified.extend(loose)
    summary: dict[str, dict[str, int]] = defaultdict(lambda: {"areas": 0, "bytes": 0})
    for row in all_areas:
        bucket = summary[row["disposition"]]
        bucket["areas"] += 1
        bucket["bytes"] += row["size_bytes"] or 0
    conflicts = [
        row for row in all_areas
        if row["disposition"] == "prune" and row["registered_artifacts"]
    ]
    return {
        "schema": 1,
        "kind": "lake_inventory",
        "roots": report_roots,
        "areas": sorted(all_areas, key=lambda r: (r["root"], r["path"])),
        "unclassified": unclassified,
        "summary": dict(summary),
        "prune_conflicts": conflicts,
    }


def _human(size: int | None) -> str:
    if size is None:
        return "-"
    value = float(size)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            return f"{value:,.0f} {unit}" if unit == "B" else f"{value:,.1f} {unit}"
        value /= 1024
    return f"{value:.1f} TB"


def format_inventory(result: dict[str, Any], dispositions: Iterable[str] | None = None) -> str:
    """Render the inventory grouped by disposition, biggest first."""
    lines = []
    for name, info in result["roots"].items():
        lines.append(f"root {name}: {info['status']} {info['path'] or ''}".rstrip())
    wanted = set(dispositions or DISPOSITIONS)
    for disposition in DISPOSITIONS:
        rows = [r for r in result["areas"] if r["disposition"] == disposition]
        if disposition not in wanted or not rows:
            continue
        bucket = result["summary"][disposition]
        lines.append(f"\n{disposition.upper()}  {bucket['areas']} areas, {_human(bucket['bytes'])}")
        for row in sorted(rows, key=lambda r: -(r["size_bytes"] or 0)):
            flag = f" [{row['registered_artifacts']} registered]" if row["registered_artifacts"] else ""
            lines.append(
                f"  {_human(row['size_bytes']):>10}  {row['files'] if row['files'] is not None else '-':>8} files  "
                f"{row['root']}:{row['path']}{flag}\n{'':>34}{row['reason']}"
            )
    if result["unclassified"]:
        lines.append(f"\nUNCLASSIFIED  {len(result['unclassified'])}")
        for row in sorted(result["unclassified"], key=lambda r: -(r["size_bytes"] or 0)):
            lines.append(f"  {_human(row['size_bytes']):>10}  {row['root']}:{row['path']}")
    if result["prune_conflicts"]:
        lines.append("\nPRUNE CONFLICTS (contain registered artifacts; do not delete):")
        for row in result["prune_conflicts"]:
            lines.append(f"  {row['root']}:{row['path']} ({row['registered_artifacts']})")
    return "\n".join(lines)
