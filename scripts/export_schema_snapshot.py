"""Export a reviewable live-schema snapshot. This is not a migration path."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row
from sqlalchemy.engine import make_url

from opendiscourse_research.config import settings

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_DIR = ROOT / "docs" / "schema-snapshot"
RESTRICT_KEY = "opendiscourseschemasnapshot"
PASSWORD_OPTION = re.compile(r"(?i)(\bpassword\s+)('[^']*'|\"[^\"]*\")")
RELATED_GLOBS = (
    ("Bootstrap SQL (legacy reference, not a second migration path)", ("sql/*.sql",)),
    ("Runtime SQL", ("sql/query/**/*.sql",)),
    ("Alembic revisions", ("migrations/versions/*.py",)),
    ("Alembic baseline DDL", ("migrations/baseline/*.sql",)),
    ("SQLModel contracts", ("src/opendiscourse_research/models/*.py",)),
    ("SQL repositories", ("src/opendiscourse_research/repositories/*.py",)),
    ("dbt models", ("dbt/models/**/*.sql",)),
    ("dbt model YAML", ("dbt/models/**/*.yml",)),
    ("Inventory and contracts", ("inventory/**/*.yaml", "inventory/**/*.yml")),
    ("Ops scripts", ("ops/**/*.sh", "ops/**/*.service", "ops/**/*.timer")),
    ("Project scripts", ("scripts/*.py", "scripts/*.sh")),
)
OWNED_SCHEMAS = (
    "api",
    "catalog",
    "core",
    "fact",
    "ingest",
    "leg",
    "mart",
    "openstates_source",
    "stage",
    "public",
)


def redact_dump(sql: str) -> str:
    """Strip credential literals from pg_dump USER MAPPING options."""
    return PASSWORD_OPTION.sub(r"\1'REDACTED'", sql)


def _pg_dump_bin(major: str) -> Path:
    candidate = Path(f"/usr/lib/postgresql/{major}/bin/pg_dump")
    if candidate.exists():
        return candidate
    return Path("pg_dump")


def _dsn_for(database: str) -> str:
    url = make_url(settings.database_url)
    return url.set(database=database).render_as_string(hide_password=False)


def _connect(dsn: str) -> psycopg.Connection:
    return psycopg.connect(dsn, row_factory=dict_row)


def _pg_dump(dsn: str, *extra: str) -> str:
    with _connect(dsn) as conn:
        major = (
            conn.execute("SHOW server_version")
            .fetchone()["server_version"]
            .split(".", 1)[0]
        )
    command = [
        str(_pg_dump_bin(major)),
        f"--dbname={dsn}",
        "--schema-only",
        "--encoding=UTF8",
        "--no-tablespaces",
        f"--restrict-key={RESTRICT_KEY}",
        *extra,
    ]
    result = subprocess.run(command, check=True, capture_output=True, text=True)
    return redact_dump(result.stdout)


def _md_cell(value: Any) -> str:
    text = "" if value is None else str(value)
    return text.replace("|", "\\|").replace("\n", " ").strip()


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content if content.endswith("\n") else content + "\n")


def _fetch_all(
    conn: psycopg.Connection, sql: str, params: Any = None
) -> list[dict[str, Any]]:
    return list(conn.execute(sql, params or ()))


def _cluster_metadata(conn: psycopg.Connection) -> dict[str, Any]:
    version = conn.execute("SHOW server_version").fetchone()["server_version"]
    db = conn.execute(
        """
        SELECT current_database() AS database_name,
               pg_size_pretty(pg_database_size(current_database())) AS size_pretty,
               pg_database_size(current_database()) AS size_bytes
        """
    ).fetchone()
    alembic = conn.execute(
        """
        SELECT version_num
        FROM public.alembic_version
        ORDER BY version_num
        """
    ).fetchall()
    extensions = _fetch_all(
        conn,
        """
        SELECT extname, extversion
        FROM pg_extension
        ORDER BY extname
        """,
    )
    return {
        "captured_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "database": db["database_name"],
        "server_version": version,
        "size_pretty": db["size_pretty"],
        "size_bytes": db["size_bytes"],
        "alembic_versions": [row["version_num"] for row in alembic],
        "extensions": extensions,
        "note": "schema-only snapshot of the live cluster; not a migration path",
    }


def _relations(conn: psycopg.Connection) -> list[dict[str, Any]]:
    return _fetch_all(
        conn,
        """
        SELECT n.nspname AS schema_name,
               c.relname AS relation_name,
               CASE c.relkind
                 WHEN 'r' THEN 'table'
                 WHEN 'v' THEN 'view'
                 WHEN 'm' THEN 'matview'
                 WHEN 'f' THEN 'foreign table'
                 WHEN 'S' THEN 'sequence'
                 WHEN 'p' THEN 'partitioned table'
                 ELSE c.relkind::text
               END AS kind,
               pg_size_pretty(pg_total_relation_size(c.oid)) AS total_size,
               pg_total_relation_size(c.oid) AS bytes,
               c.reltuples::bigint AS est_rows,
               obj_description(c.oid, 'pg_class') AS comment,
               c.oid
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = ANY(%s)
          AND c.relkind IN ('r', 'v', 'm', 'f', 'S', 'p')
          AND NOT EXISTS (
            SELECT 1
            FROM pg_depend d
            JOIN pg_extension e ON e.oid = d.refobjid
            WHERE d.objid = c.oid AND d.deptype = 'e'
          )
        ORDER BY n.nspname, c.relkind, c.relname
        """,
        (list(OWNED_SCHEMAS),),
    )


def _columns(conn: psycopg.Connection) -> list[dict[str, Any]]:
    return _fetch_all(
        conn,
        """
        SELECT n.nspname AS schema_name,
               c.relname AS relation_name,
               a.attnum,
               a.attname AS column_name,
               pg_catalog.format_type(a.atttypid, a.atttypmod) AS data_type,
               a.attnotnull AS not_null,
               pg_get_expr(ad.adbin, ad.adrelid) AS column_default,
               col_description(c.oid, a.attnum) AS comment
        FROM pg_attribute a
        JOIN pg_class c ON c.oid = a.attrelid
        JOIN pg_namespace n ON n.oid = c.relnamespace
        LEFT JOIN pg_attrdef ad
          ON ad.adrelid = a.attrelid AND ad.adnum = a.attnum
        WHERE n.nspname = ANY(%s)
          AND a.attnum > 0
          AND NOT a.attisdropped
          AND c.relkind IN ('r', 'v', 'm', 'f', 'p')
          AND NOT EXISTS (
            SELECT 1
            FROM pg_depend d
            JOIN pg_extension e ON e.oid = d.refobjid
            WHERE d.objid = c.oid AND d.deptype = 'e'
          )
        ORDER BY n.nspname, c.relname, a.attnum
        """,
        (list(OWNED_SCHEMAS),),
    )


def _constraints(conn: psycopg.Connection) -> list[dict[str, Any]]:
    return _fetch_all(
        conn,
        """
        SELECT n.nspname AS schema_name,
               c.relname AS relation_name,
               con.conname,
               con.contype,
               pg_get_constraintdef(con.oid, true) AS definition
        FROM pg_constraint con
        JOIN pg_class c ON c.oid = con.conrelid
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = ANY(%s)
        ORDER BY n.nspname, c.relname, con.contype, con.conname
        """,
        (list(OWNED_SCHEMAS),),
    )


def _indexes(conn: psycopg.Connection) -> list[dict[str, Any]]:
    return _fetch_all(
        conn,
        """
        SELECT n.nspname AS schema_name,
               c.relname AS relation_name,
               ic.relname AS index_name,
               pg_get_indexdef(i.indexrelid) AS definition
        FROM pg_index i
        JOIN pg_class c ON c.oid = i.indrelid
        JOIN pg_class ic ON ic.oid = i.indexrelid
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = ANY(%s)
          AND NOT EXISTS (
            SELECT 1
            FROM pg_depend d
            JOIN pg_extension e ON e.oid = d.refobjid
            WHERE d.objid = c.oid AND d.deptype = 'e'
          )
        ORDER BY n.nspname, c.relname, ic.relname
        """,
        (list(OWNED_SCHEMAS),),
    )


def _views(conn: psycopg.Connection) -> list[dict[str, Any]]:
    return _fetch_all(
        conn,
        """
        SELECT n.nspname AS schema_name,
               c.relname AS relation_name,
               pg_get_viewdef(c.oid, true) AS definition
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = ANY(%s)
          AND c.relkind IN ('v', 'm')
          AND NOT EXISTS (
            SELECT 1
            FROM pg_depend d
            JOIN pg_extension e ON e.oid = d.refobjid
            WHERE d.objid = c.oid AND d.deptype = 'e'
          )
        ORDER BY n.nspname, c.relname
        """,
        (list(OWNED_SCHEMAS),),
    )


def _foreign_tables(conn: psycopg.Connection) -> list[dict[str, Any]]:
    return _fetch_all(
        conn,
        """
        SELECT n.nspname AS schema_name,
               c.relname AS relation_name,
               s.srvname AS server_name,
               w.fdwname
        FROM pg_foreign_table ft
        JOIN pg_class c ON c.oid = ft.ftrelid
        JOIN pg_namespace n ON n.oid = c.relnamespace
        JOIN pg_foreign_server s ON s.oid = ft.ftserver
        JOIN pg_foreign_data_wrapper w ON w.oid = s.srvfdw
        ORDER BY n.nspname, c.relname
        """,
    )


def render_catalog(conn: psycopg.Connection, meta: dict[str, Any]) -> str:
    """Render a ChatGPT-readable catalog of owned warehouse objects."""
    relations = _relations(conn)
    columns = _columns(conn)
    constraints = _constraints(conn)
    indexes = _indexes(conn)
    views = _views(conn)
    foreign_tables = _foreign_tables(conn)
    cols_by_rel: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    cons_by_rel: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    idx_by_rel: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in columns:
        cols_by_rel[(row["schema_name"], row["relation_name"])].append(row)
    for row in constraints:
        cons_by_rel[(row["schema_name"], row["relation_name"])].append(row)
    for row in indexes:
        idx_by_rel[(row["schema_name"], row["relation_name"])].append(row)

    lines: list[str] = [
        "# Live OpenDiscourse schema catalog",
        "",
        "Schema-only snapshot of the operator warehouse. **Not a second",
        "migration path.** Alembic owns catalog/core/fact/ingest/stage",
        "contracts; `sql/query/` is runtime SQL; `sql/NNN_*.sql` is bootstrap",
        "legacy reference.",
        "",
        "| Field | Value |",
        "|---|---|",
        f"| Captured | {meta['captured_at']} |",
        f"| Database | `{meta['database']}` |",
        f"| PostgreSQL | {meta['server_version']} |",
        f"| Database size | {meta['size_pretty']} (data; dump is schema-only) |",
        f"| Alembic head | {', '.join(f'`{v}`' for v in meta['alembic_versions']) or '_none_'} |",
        "",
        "## Extensions",
        "",
        "| Extension | Version |",
        "|---|---|",
    ]
    for ext in meta["extensions"]:
        lines.append(f"| `{ext['extname']}` | {ext['extversion']} |")

    lines += [
        "",
        "## Object inventory",
        "",
        "| Schema | Name | Kind | Est. rows | Total size | Comment |",
        "|---|---|---|---:|---|---|",
    ]
    for rel in relations:
        lines.append(
            "| "
            + " | ".join(
                [
                    f"`{rel['schema_name']}`",
                    f"`{rel['relation_name']}`",
                    rel["kind"],
                    str(rel["est_rows"]),
                    rel["total_size"],
                    _md_cell(rel["comment"]),
                ]
            )
            + " |"
        )

    if foreign_tables:
        lines += [
            "",
            "## Foreign tables",
            "",
            "OpenStates is a provider snapshot. These foreign tables are the",
            "approved `openstates_source` FDW surface, not the researcher",
            "contract. Do not copy Django dump tables into `core`.",
            "",
            "| Schema | Table | Server | FDW |",
            "|---|---|---|---|",
        ]
        for row in foreign_tables:
            lines.append(
                f"| `{row['schema_name']}` | `{row['relation_name']}` |"
                f" `{row['server_name']}` | `{row['fdwname']}` |"
            )

    lines += ["", "## Relations"]
    current_schema = None
    for rel in relations:
        key = (rel["schema_name"], rel["relation_name"])
        if rel["schema_name"] != current_schema:
            current_schema = rel["schema_name"]
            lines += ["", f"### Schema `{current_schema}`"]
        lines += [
            "",
            f"#### `{rel['schema_name']}.{rel['relation_name']}`",
            "",
            f"- Kind: {rel['kind']}",
            f"- Estimated rows: {rel['est_rows']}",
            f"- Total size: {rel['total_size']}",
        ]
        if rel["comment"]:
            lines.append(f"- Comment: {rel['comment']}")
        rel_cols = cols_by_rel.get(key, [])
        if rel_cols:
            lines += [
                "",
                "| Column | Type | Null | Default | Comment |",
                "|---|---|---|---|---|",
            ]
            for col in rel_cols:
                lines.append(
                    "| "
                    + " | ".join(
                        [
                            f"`{col['column_name']}`",
                            f"`{_md_cell(col['data_type'])}`",
                            "NO" if col["not_null"] else "YES",
                            f"`{_md_cell(col['column_default'])}`"
                            if col["column_default"]
                            else "",
                            _md_cell(col["comment"]),
                        ]
                    )
                    + " |"
                )
        rel_cons = cons_by_rel.get(key, [])
        if rel_cons:
            lines += ["", "Constraints:", ""]
            for con in rel_cons:
                lines.append(
                    f"- `{con['conname']}` ({con['contype']}): `{con['definition']}`"
                )
        rel_idx = idx_by_rel.get(key, [])
        if rel_idx:
            lines += ["", "Indexes:", ""]
            for idx in rel_idx:
                lines.append(f"- `{idx['index_name']}`: `{idx['definition']}`")

    if views:
        lines += ["", "## View definitions", ""]
        for view in views:
            lines += [
                f"### `{view['schema_name']}.{view['relation_name']}`",
                "",
                "```sql",
                view["definition"].rstrip() + ";",
                "```",
                "",
            ]
    return "\n".join(lines)


def render_related_files() -> str:
    """Index in-repo SQL, models, and inventory that accompany the live dump."""
    lines = [
        "# Related schema files already in this repository",
        "",
        "The live dump in this directory is the as-built warehouse. These",
        "paths are the owned contracts and runtime SQL ChatGPT should read",
        "alongside it. Do not treat `sql/NNN_*.sql` as a second migration",
        "path.",
        "",
    ]
    for title, patterns in RELATED_GLOBS:
        paths = sorted(
            {
                path
                for pattern in patterns
                for path in ROOT.glob(pattern)
                if path.is_file() and "__pycache__" not in path.parts
            }
        )
        lines += [f"## {title}", ""]
        if not paths:
            lines += ["_None found._", ""]
            continue
        for path in paths:
            lines.append(f"- `{path.relative_to(ROOT).as_posix()}`")
        lines.append("")
    lines += [
        "## Product and architecture (review order)",
        "",
        "- `AGENTS.md`",
        "- `_bmad-output/specs/spec-opendiscourse/SPEC.md`",
        "- `_bmad-output/planning-artifacts/architecture/architecture-opendiscourse-2026-09-14/ARCHITECTURE-SPINE.md`",
        "- `_bmad-output/planning-artifacts/epics.md`",
        "- `docs/adr/0001-postgres-system-of-record.md`",
        "- `docs/model.md`",
        "- `docs/openstates-integration.md`",
        "- `docs/persistence-migration-status.md`",
        "- `docs/runtime.md`",
        "- `docs/schema-snapshot/spec-8-1-post-division-membership.md`",
        "",
        "Prior ChatGPT essays in `docs/research/` are research, not the",
        "current epic list.",
        "",
    ]
    return "\n".join(lines)


def render_openstates_inventory(conn: psycopg.Connection) -> str:
    tables = _fetch_all(
        conn,
        """
        SELECT c.relname,
               c.reltuples::bigint AS est_rows,
               pg_size_pretty(pg_total_relation_size(c.oid)) AS total_size
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public' AND c.relkind = 'r'
        ORDER BY c.relname
        """,
    )
    ocd_columns = _fetch_all(
        conn,
        """
        SELECT c.relname,
               a.attname,
               pg_catalog.format_type(a.atttypid, a.atttypmod) AS data_type,
               a.attnotnull
        FROM pg_attribute a
        JOIN pg_class c ON c.oid = a.attrelid
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public'
          AND c.relkind = 'r'
          AND c.relname LIKE %s
          AND a.attnum > 0
          AND NOT a.attisdropped
        ORDER BY c.relname, a.attnum
        """,
        ("opencivicdata_%",),
    )
    cols_by_table: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in ocd_columns:
        cols_by_table[row["relname"]].append(row)
    lines = [
        "# OpenStates provider database inventory",
        "",
        "Database `openstates` on the same PostgreSQL 17 cluster. This is a",
        "read-only provider snapshot (Django + Open Civic Data). Do not write",
        "warehouse rows into it. Researchers query `core`/`fact`; ingest may",
        "read `openstates_source` FDW.",
        "",
        "| Table | Est. rows | Total size |",
        "|---|---:|---|",
    ]
    for row in tables:
        lines.append(
            f"| `{row['relname']}` | {row['est_rows']} | {row['total_size']} |"
        )
    lines += ["", "## `opencivicdata_*` columns", ""]
    current = None
    for table, cols in cols_by_table.items():
        if table != current:
            current = table
            lines += [
                f"### `public.{table}`",
                "",
                "| Column | Type | Null |",
                "|---|---|---|",
            ]
        for col in cols:
            lines.append(
                f"| `{col['attname']}` | `{col['data_type']}` |"
                f" {'NO' if col['attnotnull'] else 'YES'} |"
            )
        lines.append("")
    return "\n".join(lines)


def render_readme(meta: dict[str, Any]) -> str:
    return f"""# Schema snapshot

Captured **{meta["captured_at"]}** from the live operator cluster
(`{meta["database"]}`, PostgreSQL {meta["server_version"]},
{meta["size_pretty"]} of data).

This directory is a **review artifact**: schema-only DDL and catalogs so an
external model can inspect the warehouse as it stands. It is **not** a
migration path, bootstrap script, or restore kit.

| File | What it is |
|---|---|
| `opendiscourse.schema.sql` | `pg_dump --schema-only` of `opendiscourse` |
| `openstates-opencivicdata.schema.sql` | OCD tables only from the `openstates` provider DB |
| `catalog.md` | Columns, constraints, indexes, views, sizes |
| `openstates-inventory.md` | All OpenStates dump tables + OCD column lists |
| `related-files.md` | In-repo SQL, Alembic, models, inventory, specs |
| `spec-8-1-post-division-membership.md` | Convenience copy of Story 8.1; canonical is `_bmad-output/implementation-artifacts/` |
| `spec-8-2-openstates-promote.md` | Convenience copy of Story 8.2 |
| `epic-8-context.md` | Convenience copy of Epic 8 context |
| `metadata.json` | Capture metadata |

Regenerate (needs the live DSN, default `postgresql:///opendiscourse?port=5434`):

```bash
uv run python scripts/export_schema_snapshot.py
```

Rules for reviewers:

- Hierarchy of truth: current code+tests → migrations/schema → architecture
  spine/ADRs → active BMAD spec/story.
- Do not copy OpenStates Django tables into `core`.
- Federal person joins need BioGuide; do not name-match people.
- `dlt` writes `stage` only.
- `core.embedding.vector_values` stays `real[]` until a later ADR.
"""


def export(output_dir: Path) -> None:
    """Write the live schema snapshot into ``output_dir``."""
    dsn = settings.database_url
    with _connect(dsn) as conn:
        meta = _cluster_metadata(conn)
        catalog = render_catalog(conn, meta)
    warehouse_sql = _pg_dump(dsn)
    openstates_dsn = _dsn_for("openstates")
    openstates_sql = _pg_dump(openstates_dsn, "--table=public.opencivicdata_*")
    with _connect(openstates_dsn) as conn:
        openstates_inventory = render_openstates_inventory(conn)

    output_dir.mkdir(parents=True, exist_ok=True)
    _write(output_dir / "opendiscourse.schema.sql", warehouse_sql)
    _write(output_dir / "openstates-opencivicdata.schema.sql", openstates_sql)
    _write(output_dir / "catalog.md", catalog)
    _write(output_dir / "openstates-inventory.md", openstates_inventory)
    _write(output_dir / "related-files.md", render_related_files())
    _write(output_dir / "README.md", render_readme(meta))
    _write(output_dir / "metadata.json", json.dumps(meta, indent=2, default=str))


def main() -> None:
    """Export the live schema snapshot for review."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=SNAPSHOT_DIR,
        help="directory to write snapshot files (default: docs/schema-snapshot)",
    )
    arguments = parser.parse_args()
    export(arguments.output_dir.resolve())
    print(f"Wrote schema snapshot to {arguments.output_dir}", file=sys.stderr)


if __name__ == "__main__":
    main()
