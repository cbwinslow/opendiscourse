# Code and SQL conventions

Every Python module begins with a module docstring that states its boundary.
Public functions and classes require concise docstrings. Provider modules make
HTTP requests only; repository modules persist/query database records only; UI
and CLI modules coordinate those layers.

Legacy and not-yet-migrated schema changes belong in ordered
`sql/NNN_name.sql` bootstrap migrations. Alembic owns `catalog.*` and adopted
immutable/OpenStates evidence tables in `ingest.*` (runs, raw payloads,
artifacts, resume checkpoints, identity exceptions, and plan cursors); changes
to those tables, and adopted `core.geography`, `core.geography_boundary`, and
`core.jurisdiction`, `core.legislative_session`, `core.bill`,
`core.bill_identifier`, `core.person`, `core.person_identifier`, and
`core.bill_action`, and `fact.measurement`, belong in Alembic revisions after
their adoption baseline. `core.bill_sponsorship` belongs there as well.
`core.bill_committee` and `core.bill_subject` belong there as well. Reusable
`core.document` and `core.bill_document` belong there as well. Reusable runtime
`core.organization` and `core.organization_identifier` belong there as well.
`core.roll_call` and `fact.member_vote` belong there as well. Reusable runtime
`fact.population_estimate` belongs there as well. Reusable runtime statements
`fact.business_pattern` belongs there as well. Reusable runtime statements
`fact.acs_bulk_estimate` belongs there as well. Reusable runtime statements
`fact.decennial_dhc_value` belongs there as well. Reusable runtime statements
`core.instrument`, `core.instrument_symbol`, and `fact.market_bar` belong
there as well. Reusable runtime statements belong in `sql/query/<area>/`.
Python must pass bound parameters to those statements and must not assemble SQL
with string interpolation. Existing inline statements are migrated incrementally
whenever their adapter is changed; new provider work may not add inline SQL.

Every provider must declare its source URL, authentication requirement,
rate-limit policy, pagination/cursor behavior, raw-provenance strategy, and
resume key before ingestion is enabled.

Use the shared `opendiscourse_research.feedback` helper for any operation with
more than one unit of work. Show phase, progress, elapsed time, remaining time
when totals are known, and an actionable resume command after interruption.
