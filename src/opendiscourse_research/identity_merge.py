"""Reviewed same-person decisions and the merge that applies them (ADR-0005, Decision 1).

``inventory/identity_exceptions.yaml`` holds human decisions that no shared identifier
can make. A ``same_person`` entry names two identifiers, never a name. Loaders read it
through :func:`linked_identifiers` so a rebuild in any order never creates the duplicate;
:func:`merge_person` (``research-db merge-people``) applies it to a warehouse that
already holds both people.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

EXCEPTIONS_PATH = Path(__file__).resolve().parents[2] / "inventory" / "identity_exceptions.yaml"

Identifier = tuple[str, str]


@dataclass(frozen=True)
class SamePerson:
    """One reviewed decision that ``duplicate`` and ``survivor`` are the same person."""

    id: str
    survivor: Identifier
    duplicate: Identifier


def _identifier(entry: dict[str, Any], key: str, exception_id: str) -> Identifier:
    value = entry.get(key) or {}
    namespace, external_id = value.get("namespace"), value.get("external_id")
    if not namespace or not external_id:
        raise ValueError(f"identity exception {exception_id}: {key} needs namespace and external_id")
    return str(namespace), str(external_id)


def load_same_person(path: Path | None = None) -> list[SamePerson]:
    """The ``same_person`` decisions. ``different_person`` entries are review records only:
    nothing merges without a ``same_person`` entry, so nothing reads them."""
    document = yaml.safe_load((path or EXCEPTIONS_PATH).read_text()) or {}
    result = []
    for entry in document.get("exceptions") or []:
        if entry.get("decision") != "same_person":
            continue
        exception_id = str(entry.get("id") or "")
        if not exception_id:
            raise ValueError("identity exception without an id")
        survivor = _identifier(entry, "survivor", exception_id)
        duplicate = _identifier(entry, "duplicate", exception_id)
        if survivor == duplicate:
            raise ValueError(f"identity exception {exception_id}: survivor and duplicate are equal")
        result.append(SamePerson(exception_id, survivor, duplicate))
    return result


def linked_identifiers(
    identifiers: list[Identifier], exceptions: list[SamePerson] | None = None
) -> list[Identifier]:
    """The asserted identifiers plus the survivor of every reviewed duplicate among them."""
    exceptions = load_same_person() if exceptions is None else exceptions
    linked = list(dict.fromkeys(identifiers))
    grew = True
    while grew:  # follow chains: A is a duplicate of B, B of C
        grew = False
        for exception in exceptions:
            if exception.duplicate in linked and exception.survivor not in linked:
                linked.append(exception.survivor)
                grew = True
    return linked
