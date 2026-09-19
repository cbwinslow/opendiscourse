"""Story 9.1 benchmark: how should a large slice of stage data be (re)loaded?

Copies real ``pas2`` rows from ``stage.fec_row`` into a scratch schema and compares:

* layout A: keyed-jsonb rows in one unpartitioned table (today's ``stage.fec_row``)
* layout B: the same rows, LIST-partitioned by cycle
* layout C: compact ``text[]`` rows, LIST-partitioned by cycle

and reload strategies for one cycle: delete-and-insert in a transaction (A), partition
swap (B, C), and set-based upsert (A, unchanged and 1% changed). It reports elapsed
seconds, WAL written, size growth and dead tuples, and checks the reloaded slice is
byte-identical. Nothing outside the scratch schema is touched; the schema is dropped at
the end unless ``--keep`` is given. Postgres settings in force are recorded in the report.

    uv run python scripts/bench/benchmark_load_strategies.py [--cycles 2012,2014,...]
"""

from __future__ import annotations

import argparse
import json
import time
from contextlib import contextmanager
from datetime import UTC, datetime

import psycopg
from psycopg import sql

from opendiscourse_research.config import settings

SCHEMA = "bench_91"
SETTINGS_OF_INTEREST = (
    "shared_buffers", "work_mem", "maintenance_work_mem", "effective_cache_size",
    "max_parallel_workers_per_gather", "max_parallel_maintenance_workers", "max_wal_size",
    "checkpoint_timeout", "max_worker_processes",
)


def q(conn: psycopg.Connection, query: str | sql.Composable, params=None):
    return conn.execute(query, params).fetchall()


def one(conn: psycopg.Connection, query: str | sql.Composable, params=None):
    return q(conn, query, params)[0][0]


class Meter:
    """Time a block and measure the WAL it wrote."""

    def __init__(self, conn: psycopg.Connection) -> None:
        self.conn = conn
        self.seconds = 0.0
        self.wal_mb = 0.0

    @contextmanager
    def measure(self):
        start_lsn = one(self.conn, "select pg_current_wal_lsn()")
        started = time.perf_counter()
        yield
        self.seconds = time.perf_counter() - started
        self.wal_mb = one(
            self.conn, "select pg_wal_lsn_diff(pg_current_wal_lsn(), %s)::float8 / 1048576", (start_lsn,)
        )


def size_mb(conn: psycopg.Connection, table: str) -> float:
    """Total size (heap + indexes + toast); for a partitioned table, summed over partitions."""
    name = f"{SCHEMA}.{table}"
    return one(
        conn,
        "select coalesce((select sum(pg_total_relation_size(relid)) from pg_partition_tree(%s::regclass)),"
        " pg_total_relation_size(%s::regclass))::float8 / 1048576",
        (name, name),
    )


def dead_tuples(conn: psycopg.Connection, table: str) -> int:
    conn.execute("select pg_stat_force_next_flush()")
    return one(
        conn,
        "select coalesce(sum(n_dead_tup), 0) from pg_stat_user_tables "
        "where schemaname = %s and relname = %s",
        (SCHEMA, table),
    )


def digest(conn: psycopg.Connection, table: str, cycle: int, payload: str) -> str:
    return one(
        conn,
        sql.SQL(
            "select md5(string_agg(concat_ws('|', artifact_id, source_ordinal, {p}::text), ',' "
            "order by artifact_id, source_ordinal)) from {t} where cycle = %s"
        ).format(p=sql.Identifier(payload), t=sql.SQL(f"{SCHEMA}.{table}")),
        (cycle,),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--family", default="pas2")
    parser.add_argument("--cycles", default="2012,2014,2016,2018,2020,2022,2024")
    parser.add_argument("--reload-cycle", type=int, default=2024)
    parser.add_argument("--repeats", type=int, default=3, help="reloads of the same cycle (shows bloat compounding)")
    parser.add_argument("--keep", action="store_true", help="keep the scratch schema")
    parser.add_argument("--json", help="also write the raw results to this file")
    args = parser.parse_args()
    cycles = [int(c) for c in args.cycles.split(",")]
    target = args.reload_cycle
    assert target in cycles, "--reload-cycle must be one of --cycles"

    results: dict = {"started": datetime.now(UTC).isoformat(), "family": args.family, "cycles": cycles}
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        results["settings"] = {
            name: f"{setting}{unit or ''}" + (" (restart pending)" if pending else "")
            for name, setting, unit, pending in q(
                conn,
                "select name, setting, unit, pending_restart from pg_settings where name = any(%s)",
                (list(SETTINGS_OF_INTEREST),),
            )
        }
        conn.execute(f"drop schema if exists {SCHEMA} cascade")
        conn.execute(f"create schema {SCHEMA}")
        try:
            run(conn, args, cycles, target, results)
        finally:
            if not args.keep:
                conn.execute(f"drop schema if exists {SCHEMA} cascade")
    print(render(results))
    if args.json:
        with open(args.json, "w") as out:
            json.dump(results, out, indent=2, default=str)


def run(conn, args, cycles, target, results) -> None:
    fam = args.family
    keys = [
        r[0]
        for r in q(
            conn,
            "select k from (select jsonb_object_keys(raw) k from stage.fec_row "
            "where family = %s and cycle = %s limit 1000) t group by k order by k",
            (fam, target),
        )
    ]
    array_expr = sql.SQL("array[{}]").format(
        sql.SQL(", ").join(sql.SQL("raw ->> {}").format(sql.Literal(k)) for k in keys)
    )
    results["columns_in_family"] = len(keys)
    S = SCHEMA

    # -- layouts -------------------------------------------------------------
    conn.execute(f"""create table {S}.a_flat (artifact_id uuid not null, family text not null,
        cycle smallint not null, source_ordinal bigint not null, raw jsonb not null,
        staged_at timestamptz not null default now(), primary key (artifact_id, source_ordinal))
        with (autovacuum_enabled = false)""")
    conn.execute(f"create index a_flat_family_cycle_idx on {S}.a_flat (family, cycle)")
    conn.execute(f"""create table {S}.b_part (artifact_id uuid not null, family text not null,
        cycle smallint not null, source_ordinal bigint not null, raw jsonb not null,
        staged_at timestamptz not null default now(), primary key (cycle, artifact_id, source_ordinal))
        partition by list (cycle)""")
    conn.execute(f"""create table {S}.c_part (artifact_id uuid not null, family text not null,
        cycle smallint not null, source_ordinal bigint not null, vals text[] not null,
        staged_at timestamptz not null default now(), primary key (cycle, artifact_id, source_ordinal))
        partition by list (cycle)""")
    for c in cycles:
        conn.execute(f"create table {S}.b_p{c} partition of {S}.b_part for values in ({c}) with (autovacuum_enabled = false)")
        conn.execute(f"create table {S}.c_p{c} partition of {S}.c_part for values in ({c}) with (autovacuum_enabled = false)")

    # -- initial load, same source rows into each layout ---------------------
    load = {}
    src_where = "family = %s and cycle = any(%s)"
    for name, statement in (
        (
            "A flat jsonb",
            sql.SQL(
                f"insert into {S}.a_flat (artifact_id, family, cycle, source_ordinal, raw) "
                f"select artifact_id, family, cycle, source_ordinal, raw from stage.fec_row where {src_where}"
            ),
        ),
        (
            "B partitioned jsonb",
            sql.SQL(
                f"insert into {S}.b_part (artifact_id, family, cycle, source_ordinal, raw) "
                f"select artifact_id, family, cycle, source_ordinal, raw from stage.fec_row where {src_where}"
            ),
        ),
        (
            "C partitioned compact",
            sql.SQL(f"insert into {S}.c_part (artifact_id, family, cycle, source_ordinal, vals) select artifact_id, family, cycle, source_ordinal, ")
            + array_expr
            + sql.SQL(f" from stage.fec_row where {src_where}"),
        ),
    ):
        meter = Meter(conn)
        with meter.measure():
            conn.execute(statement, (fam, cycles))
        table = {"A": "a_flat", "B": "b_part", "C": "c_part"}[name[0]]
        load[name] = {"seconds": meter.seconds, "wal_mb": meter.wal_mb, "size_mb": size_mb(conn, table),
                      "rows": one(conn, f"select count(*) from {S}.{table}")}
    results["initial_load"] = load
    rows = {v["rows"] for v in load.values()}
    assert len(rows) == 1, f"row counts differ between layouts: {load}"

    # the slice to reload: the real rows for the target cycle, held apart from every layout
    conn.execute(f"create table {S}.slice as select artifact_id, family, cycle, source_ordinal, raw, {array_expr.as_string(conn)} as vals from stage.fec_row where family = '{fam}' and cycle = {target}")
    slice_rows = one(conn, f"select count(*) from {S}.slice")
    results["reload_slice_rows"] = slice_rows
    before = {
        "A": digest(conn, "a_flat", target, "raw"),
        "B": digest(conn, "b_part", target, "raw"),
        "C": digest(conn, "c_part", target, "vals"),
    }
    conn.execute(f"analyze {S}.a_flat")

    # -- reload strategies ---------------------------------------------------
    reloads: dict[str, list[dict]] = {"A delete+insert": [], "B partition swap": [], "C partition swap (compact)": [],
                                      "A upsert, unchanged": [], "A upsert, 1% changed": []}
    for i in range(args.repeats):
        # A: delete and insert the slice in one transaction (heap and both indexes churn)
        size0, dead0 = size_mb(conn, "a_flat"), dead_tuples(conn, "a_flat")
        meter = Meter(conn)
        with meter.measure(), conn.transaction():
            conn.execute(f"delete from {S}.a_flat where family = %s and cycle = %s", (fam, target))
            conn.execute(f"insert into {S}.a_flat (artifact_id, family, cycle, source_ordinal, raw) select artifact_id, family, cycle, source_ordinal, raw from {S}.slice")
        reloads["A delete+insert"].append({"seconds": meter.seconds, "wal_mb": meter.wal_mb,
            "growth_mb": size_mb(conn, "a_flat") - size0, "dead_tuples_added": dead_tuples(conn, "a_flat") - dead0})

        # B and C: build the slice as a standalone table, index it, swap the partition
        for label, parent, part, payload_cols, payload_src in (
            ("B partition swap", "b_part", "b_p", "raw", "raw"),
            ("C partition swap (compact)", "c_part", "c_p", "vals", "vals"),
        ):
            size0 = size_mb(conn, parent)
            meter = Meter(conn)
            with meter.measure():
                conn.execute(f"drop table if exists {S}.swap_new")
                conn.execute(f"create table {S}.swap_new (like {S}.{parent} including defaults)")
                conn.execute(f"insert into {S}.swap_new (artifact_id, family, cycle, source_ordinal, {payload_cols}) select artifact_id, family, cycle, source_ordinal, {payload_src} from {S}.slice")
                conn.execute(f"alter table {S}.swap_new add primary key (cycle, artifact_id, source_ordinal)")
                conn.execute(f"alter table {S}.swap_new add constraint swap_new_cycle_chk check (cycle = {target})")
                with conn.transaction():
                    conn.execute(f"alter table {S}.{parent} detach partition {S}.{part}{target}")
                    conn.execute(f"drop table {S}.{part}{target}")
                    conn.execute(f"alter table {S}.swap_new rename to {part}{target}")
                    conn.execute(f"alter table {S}.{parent} attach partition {S}.{part}{target} for values in ({target})")
            reloads[label].append({"seconds": meter.seconds, "wal_mb": meter.wal_mb,
                                   "growth_mb": size_mb(conn, parent) - size0, "dead_tuples_added": 0})

        # A: set-based upsert touching only changed rows
        for label, changed in (("A upsert, unchanged", False), ("A upsert, 1% changed", True)):
            source = f"{S}.slice"
            if changed:  # a real upstream revision: 1% of rows differ, on a copy so the slice stays pristine
                conn.execute(f"drop table if exists {S}.slice_changed")
                conn.execute(f"create table {S}.slice_changed as select * from {S}.slice")
                conn.execute(f"update {S}.slice_changed set raw = jsonb_set(raw, '{{memo_text}}', to_jsonb('rev{i}'::text)) where source_ordinal % 100 = 0")
                source = f"{S}.slice_changed"
            size0, dead0 = size_mb(conn, "a_flat"), dead_tuples(conn, "a_flat")
            meter = Meter(conn)
            with meter.measure(), conn.transaction():
                conn.execute(f"""insert into {S}.a_flat as t (artifact_id, family, cycle, source_ordinal, raw)
                    select artifact_id, family, cycle, source_ordinal, raw from {source}
                    on conflict (artifact_id, source_ordinal) do update set raw = excluded.raw, staged_at = now()
                    where t.raw is distinct from excluded.raw""")
            reloads[label].append({"seconds": meter.seconds, "wal_mb": meter.wal_mb,
                "growth_mb": size_mb(conn, "a_flat") - size0, "dead_tuples_added": dead_tuples(conn, "a_flat") - dead0})
    results["reloads"] = reloads

    # -- what a normal VACUUM buys A back, and idempotency -------------------
    size_bloated = size_mb(conn, "a_flat")
    meter = Meter(conn)
    with meter.measure():
        conn.execute(f"vacuum {S}.a_flat")
    results["a_after_vacuum"] = {"seconds": meter.seconds, "size_before_mb": size_bloated, "size_after_mb": size_mb(conn, "a_flat")}
    after = {"A": digest(conn, "a_flat", target, "raw"), "B": digest(conn, "b_part", target, "raw"),
             "C": digest(conn, "c_part", target, "vals")}
    results["idempotent"] = {"B_slice_identical_after_reload": before["B"] == after["B"],
                             "C_slice_identical_after_reload": before["C"] == after["C"],
                             "A_has_expected_row_count": one(conn, f"select count(*) from {S}.a_flat where cycle = {target}") == slice_rows}
    results["final_sizes_mb"] = {"A flat jsonb": size_mb(conn, "a_flat"), "B partitioned jsonb": size_mb(conn, "b_part"),
                                 "C partitioned compact": size_mb(conn, "c_part")}


def render(r: dict) -> str:
    def avg(rows, key):
        return sum(x[key] for x in rows) / len(rows)

    out = [f"# Load strategy benchmark: {r['family']}, cycles {r['cycles'][0]}-{r['cycles'][-1]}", ""]
    out.append("Settings in force: " + ", ".join(f"{k}={v}" for k, v in r["settings"].items()))
    out.append("")
    out += ["## Initial load", "", "| layout | rows | seconds | WAL MB | size MB | bytes/row |", "|---|---:|---:|---:|---:|---:|"]
    for name, v in r["initial_load"].items():
        out.append(f"| {name} | {v['rows']:,} | {v['seconds']:.1f} | {v['wal_mb']:.0f} | {v['size_mb']:.0f} | {v['size_mb'] * 1048576 / v['rows']:.0f} |")
    out += ["", f"## Reload one cycle ({r['reload_slice_rows']:,} rows), mean of {len(next(iter(r['reloads'].values())))} runs", "",
            "| strategy | seconds | WAL MB | size growth MB | dead tuples added |", "|---|---:|---:|---:|---:|"]
    for name, rows in r["reloads"].items():
        out.append(f"| {name} | {avg(rows, 'seconds'):.1f} | {avg(rows, 'wal_mb'):.0f} | {avg(rows, 'growth_mb'):.0f} | {avg(rows, 'dead_tuples_added'):,.0f} |")
    v = r["a_after_vacuum"]
    vacuum_line = (
        f"Table A after all reloads: {v['size_before_mb']:.0f} MB, after plain VACUUM {v['size_after_mb']:.0f} MB "
        f"(VACUUM took {v['seconds']:.1f}s; a plain VACUUM does not shrink the file)."
    )
    out += ["", vacuum_line, "",
            "Final sizes (MB): " + ", ".join(f"{k} {x:.0f}" for k, x in r["final_sizes_mb"].items()), "",
            "Idempotency: " + ", ".join(f"{k}={x}" for k, x in r["idempotent"].items())]
    return "\n".join(out)


if __name__ == "__main__":
    main()
