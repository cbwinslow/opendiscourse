# Mart layer (dbt)

The `mart` schema holds purpose-built research views (bill timelines, member
records, place-year panels, impact cohorts — see `docs/blueprint.md`'s layer
table) built on top of the reviewed `core`/`fact` tables. It is built with
[dbt](https://www.getdbt.com/) rather than hand-written SQL, so marts get
tests, documentation, and lineage for free.

The `mart` schema itself is created by `sql/023_mart_schema.sql` (via
`research-db init-db`, like every other schema) so it always exists; dbt only
owns what's inside it.

## Engine: dbt-fusion, with two caveats

This project uses [dbt-fusion](https://github.com/dbt-labs/dbt-fusion) (the
`dbt` CLI; run `dbt --version` to confirm). As of `2.0.0-preview.202`, its
Postgres adapter has two rough edges worth knowing before you run it:

1. **Postgres is experimental.** You must set
   `DBT_ALLOW_EXPERIMENTAL_ADAPTERS=true` or every command fails immediately
   with `InvalidConfig (dbt1005)`.
2. **It cannot connect over a Unix socket** (`host: /var/run/postgresql`
   produces `AuthenticationFailed: empty host`, even though the path is
   valid and `psql` connects with it fine). The app itself
   (`src/opendiscourse_research/db.py`) uses peer auth over that socket with
   no password, per `docs/runtime.md` — but dbt needs TCP loopback instead.

   The checked-in profile defaults to the Docker Compose database. For the
   bare-metal cluster, `pg_hba.conf` already allows
   `host all all 127.0.0.1/32 scram-sha-256`; give the `cbwinslow` role a
   password and override the profile variables:
   ```sql
   ALTER ROLE cbwinslow WITH PASSWORD '...';
   ```
   ```bash
   export DBT_PG_HOST=127.0.0.1 DBT_PG_PORT=5434
   export DBT_PG_USER=cbwinslow DBT_PG_DBNAME=opendiscourse
   export DBT_PG_PASSWORD='...'
   ```

   `dbt` does not read `.env` files on its own, so source or export these
   variables before running it.

If a future `dbt-fusion` release adds stable, non-experimental Postgres
support (or Unix-socket support), both workarounds above can be dropped:
switch `host` back to the socket path in `dbt/profiles.yml`, drop the
`password` line, and stop setting `DBT_ALLOW_EXPERIMENTAL_ADAPTERS`. If
dbt-fusion's Postgres support turns out not to mature, the project files are
written in standard dbt syntax and should run unmodified under classic
`dbt-core` + `dbt-postgres` (which does support Unix sockets) as a fallback.

## Running it

```bash
export DBT_ALLOW_EXPERIMENTAL_ADAPTERS=true
set -a; source .env; set +a   # provides DBT_PG_PASSWORD

dbt debug --project-dir dbt --profiles-dir dbt   # connection check
dbt build --project-dir dbt --profiles-dir dbt   # run models + tests
```

For Docker Compose, the checked-in profile defaults already match the
quickstart. Set only `DBT_PG_PASSWORD=change-me` (or the value chosen in
`POSTGRES_PASSWORD`) before the same commands.

## What's in it

- `models/staging/` — thin, 1:1 views over `core`/`fact` source tables
  (`stg_bills`, `stg_roll_calls`, `stg_member_votes`, `stg_geography`,
  `stg_measurements`), each with `not_null`/`unique` schema tests on its key.
- `models/marts/`:
  - `mart_roll_call_results` — one row per roll call: bill identity,
    chamber, jurisdiction, session, and yea/nay/other/total vote tallies.
  - `mart_geography_year_measurement` — a geography x year panel pivoted
    from `fact.measurement`, the join point for combining vote/bill research
    with place-level economic/demographic series. Empty until a
    `fact.measurement`-writing adapter (FRED, BLS, BEA) actually runs.

All models are materialized as `view` for now — trivially fresh, no refresh
step to schedule. Revisit as `table`/incremental once a `dbt build` step is
added to the `plan-due`/systemd refresh cadence alongside the ingestion
adapters that feed these tables.
