# Code and SQL conventions

Every Python module begins with a module docstring that states its boundary.
Public functions and classes require concise docstrings. Provider modules make
HTTP requests only; repository modules persist/query database records only; UI
and CLI modules coordinate those layers.

## Persistence and SQL boundaries

Alembic is the canonical schema authority for the application-owned `catalog`,
`core`, `fact`, `ingest`, and `stage` contracts. Use SQLModel/SQLAlchemy
sessions for catalog metadata, immutable source evidence, canonical entities,
measurements, search, and ordinary repository queries. Schema changes to those
mapped contracts require ordered, reversible Alembic revisions; new-database
bootstraps start from the frozen reviewed baseline DDL. The historical ordered
`sql/NNN_name.sql` files are reference material, not a second runtime migration
path.

The following narrowly scoped raw `psycopg` paths are intentional and must not
be converted into row-at-a-time ORM loops:

| Boundary | Allowed raw operation | Required safeguard |
| --- | --- | --- |
| Provider staging | ACS, CBP, DHC, PEP, TIGER, and FEC COPY/`executemany` and set-based `INSERT … SELECT` promotion | Preserve source-owned staging shape, immutable artifact/raw-payload lineage, idempotency key, and existing batch/commit semantics. |
| OpenStates FDW | FDW reads, source-schema reconciliation, and compatibility-view publishing | Keep the source mapping external and explicitly approved; publishers read their named operational SQL resource. |
| Caller transaction | Legislative graph/provenance reconciliation receiving a caller-supplied connection | Do not create, commit, or roll back an independent transaction; retain the caller's atomic boundary. |

Reusable runtime SQL belongs in `sql/query/<area>/`. Python must use bound
parameters and must not assemble SQL with string interpolation. Existing inline
SQL is migrated incrementally when its adapter changes; new provider work may
not add inline SQL.

Every provider must declare its source URL, authentication requirement,
rate-limit policy, pagination/cursor behavior, raw-provenance strategy, and
resume key before ingestion is enabled.

Alembic owns provider-specific staging-table contracts; their high-throughput
COPY and set-based promotion operations remain at the raw repository boundary.

Use the shared `opendiscourse_research.feedback` helper for any operation with
more than one unit of work. Show phase, progress, elapsed time, remaining time
when totals are known, and an actionable resume command after interruption.

## Names

- **Datasets and lake folders:** `provider.dataset_name`, lowercase with underscores;
  the raw folder is the same id with the dot as a slash (`docs/lake.md`, "Names").
- **Python modules:** snake_case words (`artifact_storage`, `billstatus_record`), one
  boundary per module. Older run-together names (`legload`, `censushealth`) are
  renamed only when the module is replaced, not in passing.
- **`research-db` commands:** kebab-case `<verb>-<object>`. `sync-<source>` downloads
  from the origin, inventories and loads in one idempotent step; `load-<object>` loads
  what is already retained; `validate-` and `reconcile-` are read-only apart from their
  report. New sources are Connectors, not new dispatcher branches.
- **Scripts:** operational shell and Python helpers live under `scripts/<area>/`
  (`ops`, `ci`, `bench`), snake_case with a verb first; systemd units keep the
  `opendiscourse-<job>.service|timer` form under `ops/systemd/`.
- **Docs:** kebab-case; a dated snapshot ends in `-YYYY-MM-DD` (audits, inventories,
  research); living documents carry no date. Decisions are `docs/adr/NNNN-title.md`.
