# Code and SQL conventions

Every Python module begins with a module docstring that states its boundary.
Public functions and classes require concise docstrings. Provider modules make
HTTP requests only; repository modules persist/query database records only; UI
and CLI modules coordinate those layers.

Schema changes belong in ordered `sql/NNN_name.sql` migrations. Reusable
runtime statements belong in `sql/query/<area>/`. Python must pass bound
parameters to those statements and must not assemble SQL with string
interpolation. Existing inline statements are migrated incrementally whenever
their adapter is changed; new provider work may not add inline SQL.

Every provider must declare its source URL, authentication requirement,
rate-limit policy, pagination/cursor behavior, raw-provenance strategy, and
resume key before ingestion is enabled.

Use the shared `opendiscourse_research.feedback` helper for any operation with
more than one unit of work. Show phase, progress, elapsed time, remaining time
when totals are known, and an actionable resume command after interruption.
