"""``inventory/precedence.yaml``: which source wins each displayed name (ADR-0005, Decision 3).

The file is tracked configuration. :func:`sync_precedence` copies it into
``catalog.name_display`` and ``catalog.attribute_precedence`` (a keyed sync: rows the file
dropped are removed) and :func:`validate_precedence` checks it against ``sources.yaml``.
``research-db resolve`` reads only the synced tables.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .db import connect
from .repositories.names import query

PRECEDENCE_PATH = Path(__file__).resolve().parents[2] / "inventory" / "precedence.yaml"

KINDS = {"person": ("official", "common"), "geography": ("short", "full")}


def load_precedence(path: Path | None = None) -> dict[str, Any]:
    """The parsed precedence file."""
    return yaml.safe_load((path or PRECEDENCE_PATH).read_text()) or {}


def _entries(document: dict[str, Any]) -> list[tuple[str, str, str, int, str, str]]:
    """``(entity, kind, geography_type, rank, dataset, field)`` in file order; type is '' for person."""
    rows: list[tuple[str, str, str, int, str, str]] = []
    for entity in KINDS:
        for kind, scope in ((document.get(entity) or {}).get("kinds") or {}).items():
            typed = scope.items() if entity == "geography" and isinstance(scope, dict) else [("", scope)]
            for geography_type, sources in typed:
                for rank, source in enumerate(sources or [], start=1):
                    rows.append((entity, str(kind), str(geography_type), rank, str(source.get("dataset")), str(source.get("field"))))
    return rows


def _display(document: dict[str, Any]) -> list[tuple[str, str, int]]:
    """``(entity, kind, position)``, position 1 first."""
    return [
        (entity, str(kind), position)
        for entity in KINDS
        for position, kind in enumerate((document.get(entity) or {}).get("display") or [], start=1)
    ]


def validate_precedence(document: dict[str, Any], dataset_ids: set[str]) -> list[str]:
    """Problems in the file: unknown datasets, kinds or types, gaps, duplicates."""
    errors: list[str] = []
    if not isinstance(document, dict) or not document:
        return ["precedence.yaml: the document is empty or not a mapping"]
    if document.get("version") != 1:
        errors.append("precedence.yaml: version must be 1")
    for entity, allowed in KINDS.items():
        section = document.get(entity)
        if not isinstance(section, dict):
            errors.append(f"precedence.yaml: {entity} section is missing")
            continue
        display = section.get("display") or []
        if not isinstance(display, list) or not display or len(set(display)) != len(display):
            display = []
            errors.append(f"precedence.yaml: {entity}.display must list each name kind once")
        errors += [f"precedence.yaml: {entity} display kind {kind!r} is not one of {allowed}" for kind in display if kind not in allowed]
        kinds = section.get("kinds")
        if not isinstance(kinds, dict) or not kinds:
            errors.append(f"precedence.yaml: {entity}.kinds is missing")
            continue
        for kind, scope in kinds.items():
            if kind not in allowed:
                errors.append(f"precedence.yaml: {entity} kind {kind!r} is not one of {allowed}")
            if kind not in display:
                errors.append(f"precedence.yaml: {entity} kind {kind!r} is ranked but never displayed")
            if entity == "geography":
                if not isinstance(scope, dict) or not scope:
                    errors.append(f"precedence.yaml: geography kind {kind!r} needs one list per geography type")
                    continue
                lists = {f"{kind}/{geography_type}": sources for geography_type, sources in scope.items()}
            else:
                lists = {kind: scope}
            for label, sources in lists.items():
                if not isinstance(sources, list) or not sources:
                    errors.append(f"precedence.yaml: {entity} {label} needs an ordered list of sources")
                    continue
                datasets = [source.get("dataset") if isinstance(source, dict) else None for source in sources]
                errors += [f"precedence.yaml: {entity} {label}: {dataset!r} is not a dataset in sources.yaml" for dataset in datasets if dataset not in dataset_ids]
                if len(set(datasets)) != len(datasets):
                    errors.append(f"precedence.yaml: {entity} {label} lists a dataset twice")
                errors += [f"precedence.yaml: {entity} {label} entry {source!r} needs a field" for source in sources if not isinstance(source, dict) or not source.get("field")]
    for entity in sorted(set(document) - set(KINDS) - {"version", "description"}):
        errors.append(f"precedence.yaml: unknown top-level key {entity!r}")
    return errors


def sync_precedence(document: dict[str, Any] | None = None, *, dry_run: bool = False) -> dict[str, int]:
    """Copy the file into the catalog and remove what it dropped, in one transaction.

    The document is validated against ``sources.yaml`` first; an invalid one raises ``ValueError``
    listing every problem before anything is opened, so an empty file can never prune the ranking.
    Datasets must already be synced (foreign key). Returns counts of rows written and removed;
    a rerun with an unchanged file writes and removes nothing. ``dry_run`` does everything and rolls
    back, returning the same counts.
    """
    from .catalog import load_inventory  # imported late: catalog imports this module

    document = load_precedence() if document is None else document
    inventory = load_inventory()
    errors = validate_precedence(
        document, {d["id"] for p in inventory["providers"] for d in p["datasets"]}
    )
    if errors:
        raise ValueError("precedence not synced: " + "; ".join(errors))
    display, entries = _display(document), _entries(document)
    display_arrays = {
        "entities": [row[0] for row in display],
        "kinds": [row[1] for row in display],
        "positions": [row[2] for row in display],
    }
    entry_arrays = {
        "entities": [row[0] for row in entries],
        "kinds": [row[1] for row in entries],
        "types": [row[2] for row in entries],
        "datasets": [row[4] for row in entries],
        "ranks": [row[3] for row in entries],
        "fields": [row[5] for row in entries],
    }
    counts: dict[str, int] = {}
    with connect() as conn, conn.transaction(force_rollback=dry_run):
        cur = conn.cursor()
        cur.execute(query("sync_name_display"), display_arrays)
        counts["display_written"] = len(cur.fetchall())
        cur.execute(query("sync_attribute_precedence"), entry_arrays)
        counts["ranks_written"] = len(cur.fetchall())
        cur.execute(
            query("prune_attribute_precedence"),
            {key: entry_arrays[key] for key in ("entities", "kinds", "types", "datasets")},
        )
        counts["ranks_removed"] = len(cur.fetchall())
        cur.execute(query("prune_name_display"), {key: display_arrays[key] for key in ("entities", "kinds")})
        counts["display_removed"] = len(cur.fetchall())
    return counts


def precedence_differs() -> dict[str, int] | None:
    """What syncing the file would change in the catalog, or None when the catalog already matches it."""
    counts = sync_precedence(dry_run=True)
    return counts if any(counts.values()) else None
