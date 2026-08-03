# OpenDiscourse project creed

## User feedback

Every operation that can take more than a moment must provide useful terminal
feedback. Prefer the shared `feedback` module over ad-hoc printing. Show a
spinner for indeterminate work and a progress bar when total work is known.
Include the current phase, completed/total work, elapsed time, estimated time
remaining when meaningful, safe resume information, and actionable failures.

For TUI work, show contextual controls and offer an opt-in debug trace that
records navigation state without capturing sensitive inputs. When reviewing or
changing existing code, identify long-running or opaque workflows and apply
this standard where practical.

## Code and data boundaries

Provider modules own external requests and provider-specific pacing.
Repositories own PostgreSQL persistence. Reusable runtime SQL belongs in
`sql/query/`; schema changes belong in ordered `sql/` migrations. New public
modules and functions require concise docstrings.

## Engineering, database, and AI practice

Follow established industry standards for software engineering, database
administration, security, and operations. Favor clear module ownership, typed
interfaces, explicit error handling, idempotent and observable data changes,
least-privilege access, parameterized queries, ordered reversible migrations,
and validation appropriate to the risk of a change. Preserve immutable source
evidence and provenance; never silently overwrite, co-mingle, or promote data
whose ownership, coverage, or quality has not been established.

Treat provider snapshots and canonical warehouse data as separate owned
systems. Preserve upstream schemas and refreshability; use documented
read-only mappings or views before copying data, and record the rationale,
source identifiers, and validation evidence for every consolidation decision.

Use AI-assisted tools deliberately: delegate bounded work when it improves
coverage or speed, verify all generated output against the repository and
primary evidence, protect secrets and sensitive inputs, and retain human-
reviewable reasoning in code, migrations, runbooks, and commit history. Keep
architecture, operations, and user-facing procedures documented as the system
changes; update the relevant documentation in the same change as a behavior,
schema, contract, or workflow change.

## Git and GitHub workflow

Make small, cohesive commits as work reaches a verified checkpoint. Each
commit should contain one logical change that can be understood, reviewed,
tested, and reverted independently; do not mix unrelated cleanup or another
task's work into it. Commit frequently enough to preserve useful progress.

Write informative commit messages. Use a concise imperative subject, followed
when helpful by a body that explains the intent, key implementation choices,
user-visible or data-model effects, validation performed, and relevant issue
references. Agents may create branches and commits without asking for advance
permission. When a remote is configured and the task calls for publishing the
work, push these focused commits promptly.

Keep GitHub tracking current when it would help collaborators. Add issue
comments for meaningful progress, decisions, blockers, validation results, or
scope changes. Create or maintain sub-issues when a task has independently
trackable parts, dependencies, or follow-up work. Link commits, pull requests,
and issues where useful so the implementation and its rationale remain
discoverable.

## Delegating work to Antigravity

Codex may delegate bounded general tasks to the locally authenticated Gemini
Antigravity AGY CLI whenever doing so is useful. Prefer delegation for simple,
mechanical, read-only, repetitive, broad-reconnaissance, documentation, or
long-running work that can proceed independently, conserving Codex context for
task framing, integration, review, and final verification. Use the appropriate
delegation mode for the task: plan mode by default, and edit-accepting mode
only when changes have been authorized. Treat delegated output as a report:
inspect any edits and run relevant verification before relying on them.

## Python libraries and conventions

Use the project's declared dependencies for their intended boundaries:

- `httpx` for provider HTTP requests; providers own request behavior,
  authentication, pagination, retries, and pacing.
- `psycopg` for PostgreSQL/PostGIS access; repositories own persistence and
  queries, use bound parameters, and preserve JSON with `Jsonb` where needed.
- `pydantic` and `pydantic-settings` for typed models and configuration; keep
  environment-backed settings centralized in the configuration module.
- `typer` for CLI commands and `rich` through the shared `feedback` module for
  progress, spinners, elapsed time, and actionable failures.
- `tenacity` for explicit, provider-appropriate retry policies rather than
  ad-hoc retry loops.
- `PyYAML` for the reviewed inventory, plan, and contract files; validate
  their shape before using them operationally.

Optional dependencies are installed only when their capability is needed:
`polars`/`pyarrow` for analytics, `geopandas`/`pyogrio`/`shapely` for spatial
work, `fredapi` for FRED access, `dlt` and `openpyxl` for ingestion support,
and `textual` for the optional browser TUI. `dlt` is staging machinery, not
the canonical database model. Keep additions to the dependency set deliberate:
prefer an existing project library when it fits, declare new runtime
dependencies in `pyproject.toml`, and update the lockfile with the supported
package workflow.
