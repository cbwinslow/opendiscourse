"""Isolated, time-bounded read-only access to an explicitly supplied snapshot.

Only reviewed SQL templates and quoted catalog identifiers are executable here.
Each query has its own read-only transaction, so a denied query cannot poison
later measurements. Error messages deliberately omit server text and credentials.
"""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path

import psycopg
from psycopg import sql
from psycopg.rows import dict_row

QUERY_ROOT = Path(__file__).resolve().parents[3] / "sql/query/openstates_audit"
SAFE_SAMPLE_COLUMNS = frozenset(
    (
        "id",
        "identifier",
        "jurisdiction_id",
        "legislative_session_id",
        "classification",
        "start_date",
        "end_date",
        "created_at",
        "updated_at",
    )
)


class Reader:
    """Own a connection which cannot execute writes, including accidental writes."""

    def __init__(self, dsn: str, timeout_ms: int = 60000):
        if not 1 <= timeout_ms <= 3600000:
            raise ValueError("timeout must be between 1 and 3600000 milliseconds")
        self.dsn = dsn
        self.timeout_ms = timeout_ms
        self.snapshot_token = None

    @contextmanager
    def connection(self):
        """Start a fresh read-only transaction with explicit local timeouts."""
        with (
            psycopg.connect(
                self.dsn, autocommit=True, row_factory=dict_row, connect_timeout=10
            ) as conn,
            conn.transaction(),
        ):
            conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            if self.snapshot_token is not None:
                conn.execute(
                    sql.SQL("SET TRANSACTION SNAPSHOT {}").format(
                        sql.Literal(self.snapshot_token)
                    )
                )
            conn.execute(
                "SELECT set_config('statement_timeout', %s, true)",
                (str(self.timeout_ms),),
            )
            conn.execute(
                "SELECT set_config('lock_timeout', %s, true)",
                (str(min(self.timeout_ms, 5000)),),
            )
            yield conn

    @contextmanager
    def snapshot(self):
        """Keep one exported read snapshot alive for all independently recoverable queries."""
        if self.snapshot_token is not None:
            raise ValueError("snapshot context is already active")
        with self.connection() as conn:
            token = conn.execute("SELECT pg_export_snapshot() AS token").fetchone()[
                "token"
            ]
            self.snapshot_token = token
            try:
                yield token
            finally:
                self.snapshot_token = None

    def visible(self, schema, table):
        """Refuse completeness claims under effective row filtering, including view dependencies."""
        self.ensure_unfiltered(sql.Identifier(schema, table))

    def ensure_unfiltered(self, relation):
        """Bind a safely quoted relation name as a regclass value, never raw SQL."""
        rows = self.query("visibility", (relation.as_string(),))
        if any(row["filtered"] for row in rows):
            raise RowFilteringError(
                "effective row filtering prevents exhaustive evidence"
            )

    def query(self, name: str, params=(), **identifiers):
        """Run one maintained SELECT template; names cannot become raw SQL."""
        statement = sql.SQL((QUERY_ROOT / f"{name}.sql").read_text())
        if identifiers:
            statement = statement.format(**identifiers)
        if name in (
            "profile",
            "table_profile",
            "count",
            "nested",
            "coverage",
            "samples",
            "text_dates",
        ):
            self.ensure_unfiltered(identifiers["relation"])
        if name == "references":
            self.ensure_unfiltered(identifiers["source"])
            self.ensure_unfiltered(identifiers["target"])
        with self.connection() as conn:
            return conn.execute(statement, params).fetchall()

    def namespaces(self, schema):
        """Measure identifier namespaces only after verifying full row visibility."""
        self.visible(schema, "opencivicdata_personidentifier")
        return self.query(
            "identity",
            identifiers=sql.Identifier(schema, "opencivicdata_personidentifier"),
        )

    def identity_counts(self, schema):
        """Measure BioGuide and display-name collisions without creating a link."""
        self.visible(schema, "opencivicdata_person")
        self.visible(schema, "opencivicdata_personidentifier")
        return self.query(
            "bioguide",
            people=sql.Identifier(schema, "opencivicdata_person"),
            identifiers=sql.Identifier(schema, "opencivicdata_personidentifier"),
        )

    def version(self):
        """Read server version without publishing connection or account values."""
        with self.connection() as conn:
            return conn.execute(
                "SELECT current_setting('server_version') AS version"
            ).fetchone()["version"]

    def profile(self, schema, table, column):
        """Measure all rows; no samples or estimated counts establish completeness."""
        return self.query(
            "profile",
            relation=sql.Identifier(schema, table),
            column=sql.Identifier(column),
        )[0]

    def nested(self, schema, table, column):
        """Inventory every JSON/array path by scanning all visible values."""
        return self.query(
            "nested",
            relation=sql.Identifier(schema, table),
            column=sql.Identifier(column),
        )

    def table_profile(self, schema, table, columns):
        """Measure all scalar null rates and date bounds with one whole-table scan."""
        aggregates = []
        for index, column in enumerate(columns):
            field = sql.Identifier(column["source_path"])
            aggregates.append(
                sql.SQL("count(*) FILTER (WHERE {} IS NULL) AS {}").format(
                    field, sql.Identifier(f"null_{index}")
                )
            )
            if column["source_type"] in (
                "date",
                "timestamp with time zone",
                "timestamp without time zone",
            ):
                for function in ("min", "max"):
                    aggregates.append(
                        sql.SQL("{}({}) AS {}").format(
                            sql.SQL(function),
                            field,
                            sql.Identifier(f"{function}_{index}"),
                        )
                    )
        return self.query(
            "table_profile",
            relation=sql.Identifier(schema, table),
            aggregates=sql.SQL(", ").join(aggregates),
        )[0]

    def text_dates(self, schema, table, column):
        """Preserve year/month/day precision; never fill missing month or day."""
        return self.query(
            "text_dates",
            relation=sql.Identifier(schema, table),
            column=sql.Identifier(column),
        )

    def coverage(self, schema, table, columns):
        """Count observed groups; absent groups are not inferred to be zero."""
        groups = sql.SQL(", ").join(map(sql.Identifier, columns))
        return self.query(
            "coverage", relation=sql.Identifier(schema, table), groups=groups
        )

    def samples(self, schema, table, columns):
        """Return one deterministic source-ID/date/classification example, never contacts."""
        if not columns or not set(columns).issubset(SAFE_SAMPLE_COLUMNS):
            raise ValueError(
                "sample columns must be approved source IDs, dates or classification"
            )
        ordering = "id" if "id" in columns else columns[0]
        return self.query(
            "samples",
            relation=sql.Identifier(schema, table),
            columns=sql.SQL(", ").join(map(sql.Identifier, columns)),
            ordering=sql.Identifier(ordering),
        )

    def references(self, key):
        """Measure missing targets for a declared composite foreign key."""
        pairs = list(zip(key["columns"], key["target_columns"], strict=True))
        return self.query(
            "references",
            source=sql.Identifier(key["source_schema"], key["source_table"]),
            target=sql.Identifier(key["target_schema"], key["target_table"]),
            nonnull=sql.SQL(" AND ").join(
                sql.SQL("s.{} IS NOT NULL").format(sql.Identifier(a)) for a, _ in pairs
            ),
            matches=sql.SQL(" AND ").join(
                sql.SQL("s.{} = t.{}").format(sql.Identifier(a), sql.Identifier(b))
                for a, b in pairs
            ),
        )[0]


class RowFilteringError(psycopg.Error):
    """The current actor cannot establish complete source evidence under RLS."""

    sqlstate = "ODRLS"
