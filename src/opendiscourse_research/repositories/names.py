"""Name assertions and the one resolver that turns them into displayed names (ADR-0005).

Loaders record what each source says with :func:`upsert_person_name_sources` and
:func:`upsert_geography_name_sources` and never write ``core.person`` names or
``core.geography.name``. :func:`resolve_names` is the only writer of those columns: it
shows the winning assertion per row, deterministically, and points ``name_source_id`` at
it. SQL only; the statements live in ``sql/query/names/``.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from functools import cache
from pathlib import Path
from typing import Any

import psycopg
from psycopg.types.json import Jsonb

_QUERY_ROOT = Path(__file__).resolve().parents[3] / "sql" / "query" / "names"

ENTITIES = ("person", "geography")

# The setting the write guard trigger looks for; the resolver sets it, locally to its transaction.
RESOLVER_SETTING = "opendiscourse.resolver"

PERSON_ROW = ("person_id", "name_kind", "full_name", "given_name", "family_name")
GEOGRAPHY_ROW = ("geography_id", "name_kind", "name")
EVIDENCE = ("dataset_id", "source_vintage", "artifact_id", "payload_id", "run_id")

# Vintages sort as text, so only zero-padded ISO forms are allowed (the tables check the same regex).
VINTAGE_PATTERN = re.compile(r"^[0-9]{4}(-[0-9]{2}(-[0-9]{2})?)?$")


class UnrankedSource(RuntimeError):
    """Assertions exist that ``inventory/precedence.yaml`` does not rank; resolve fails closed."""


@cache
def query(name: str) -> str:
    """Read a named, version-controlled names query (once per process)."""
    return (_QUERY_ROOT / f"{name}.sql").read_text()


def _json_rows(rows: Iterable[dict[str, Any]], columns: tuple[str, ...]) -> Jsonb:
    """Rows as the JSON array the upsert reads.

    Refuses a row that lacks evidence, has a blank name or a vintage that is not zero-padded ISO,
    and a batch that gives one natural key two different values. Identical duplicates collapse.
    """
    by_key: dict[tuple[str, ...], dict[str, str | None]] = {}
    for row in rows:
        missing = [key for key in (*columns, *EVIDENCE) if key not in row]
        if missing:
            raise ValueError(f"name assertion is missing {', '.join(missing)}")
        if row["artifact_id"] is None and row["payload_id"] is None:
            raise ValueError("a name assertion needs an artifact or a payload as evidence (ADR-0002)")
        if not str(row[columns[2]] or "").strip():
            raise ValueError(f"a name assertion needs a non-blank {columns[2]} (entity {row[columns[0]]})")
        if not VINTAGE_PATTERN.match(str(row["source_vintage"])):
            raise ValueError(
                f"source_vintage {row['source_vintage']!r} must be zero-padded ISO text such as 2024 or 2024-09"
            )
        prepared = {key: None if row[key] is None else str(row[key]) for key in (*columns, *EVIDENCE)}
        key = tuple(str(prepared[name]) for name in (columns[0], "name_kind", "dataset_id", "source_vintage"))
        if by_key.setdefault(key, prepared) != prepared:
            raise ValueError(
                f"one batch gives {columns[0]}/name_kind/dataset_id/source_vintage {key} two different values"
            )
    return Jsonb(list(by_key.values()))


def _upsert(cur: psycopg.Cursor, statement: str, rows: Jsonb) -> dict[str, int]:
    cur.execute(query(statement), {"rows": rows})
    outcomes = [row["inserted"] for row in cur.fetchall()]
    inserted = sum(outcomes)
    return {"inserted": inserted, "updated": len(outcomes) - inserted}


def upsert_person_name_sources(cur: psycopg.Cursor, rows: Iterable[dict[str, Any]]) -> dict[str, int]:
    """Record person name assertions; a rerun with the same evidence changes nothing.

    Each row carries ``PERSON_ROW`` and ``EVIDENCE`` keys. The full, given and family name
    travel together from one assertion. A dataset with a ``person_join`` gate (FEC, disclosures,
    elections) must have its gate open: ``identitygate.require_person_join`` is called for each
    such dataset before anything is written and raises while it is blocked.
    """
    prepared = _json_rows(rows, PERSON_ROW)
    if not prepared.obj:
        return {"inserted": 0, "updated": 0}
    from .. import (
        identitygate,  # imported late: identitygate reaches this module through catalog
    )

    for dataset_id in sorted({row["dataset_id"] for row in prepared.obj} & set(identitygate.PERSON_JOIN_DATASETS)):
        identitygate.require_person_join(dataset_id)
    return _upsert(cur, "upsert_person_name_sources", prepared)


def upsert_geography_name_sources(cur: psycopg.Cursor, rows: Iterable[dict[str, Any]]) -> dict[str, int]:
    """Record geography name assertions (never ZCTA: its name equals its geoid).

    Each row carries ``GEOGRAPHY_ROW`` and ``EVIDENCE`` keys.
    """
    prepared = _json_rows(rows, GEOGRAPHY_ROW)
    if not prepared.obj:
        return {"inserted": 0, "updated": 0}
    return _upsert(cur, "upsert_geography_name_sources", prepared)


def unranked_sources(cur: psycopg.Cursor, entity: str) -> list[dict[str, Any]]:
    """Assertions with no precedence row, one entry per dataset, kind and type."""
    _require_entity(entity)
    cur.execute(query(f"unranked_{entity}"))
    return list(cur.fetchall())


def require_ranked(cur: psycopg.Cursor, entity: str) -> None:
    """Fail closed: raise :class:`UnrankedSource` naming every dataset, kind or type left unranked."""
    problems = []
    for row in unranked_sources(cur, entity):
        dataset, kind, geography_type = row["dataset_id"], row["name_kind"], row["geography_type"]
        reason = row["reason"]
        if reason == "dataset":
            problems.append(f"dataset {dataset!r} has {entity} name assertions and no row in inventory/precedence.yaml")
        elif reason == "name_kind":
            problems.append(f"{entity} name kind {kind!r} (dataset {dataset!r}) is not ranked or not displayed")
        elif reason == "geography_type":
            problems.append(f"geography type {geography_type!r} (dataset {dataset!r}) has no precedence row")
        else:
            scope = f" for geography type {geography_type!r}" if geography_type else ""
            problems.append(f"dataset {dataset!r} has no precedence row for {entity} name kind {kind!r}{scope}")
    if problems:
        unique = list(dict.fromkeys(problems))
        raise UnrankedSource(
            f"resolve {entity} refused: " + "; ".join(unique) + ". Add the source to inventory/precedence.yaml "
            "and run `research-db init-db`."
        )


def apply_resolution(cur: psycopg.Cursor, entity: str) -> list[dict[str, Any]]:
    """Write the winners for one entity on the caller's cursor and return the changed rows.

    No lock, no transaction: :func:`resolve_names` supplies both. Rows come back with their
    old and new values, from ``RETURNING``.
    """
    _require_entity(entity)
    cur.execute("SELECT set_config(%s, 'on', true)", (RESOLVER_SETTING,))
    cur.execute(query(f"resolve_{entity}"))
    changes = sorted(cur.fetchall(), key=lambda row: str(row[f"{entity}_id"]))
    # Local to the transaction, but a caller's transaction may go on: leave no open door behind.
    # A failure rolls the setting back with the statement.
    cur.execute("SELECT set_config(%s, '', true)", (RESOLVER_SETTING,))
    return changes


def resolve_names(conn: psycopg.Connection, entity: str, *, dry_run: bool = False) -> dict[str, Any]:
    """Resolve one entity's displayed names in its own short transaction.

    Takes ``pg_advisory_xact_lock(hashtextextended('resolve:<entity>', 0))`` so two resolvers
    serialise and the second sees nothing left to change. ``dry_run`` does everything and rolls
    back. A pure function of the assertions committed when it runs; a rerun changes nothing.
    Pass a connection with no open transaction.
    """
    _require_entity(entity)
    with conn.transaction(force_rollback=dry_run):
        cur = conn.cursor()
        cur.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))", (f"resolve:{entity}",))
        require_ranked(cur, entity)
        changes = apply_resolution(cur, entity)
    return {"entity": entity, "dry_run": dry_run, "changed": len(changes), "rows": changes}


def _require_entity(entity: str) -> None:
    if entity not in ENTITIES:
        raise ValueError(f"unknown entity {entity!r}; choose from {', '.join(ENTITIES)}")
