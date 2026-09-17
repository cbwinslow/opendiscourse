# Epic 2 Context: Connector protocol + FRED reference

<!-- Compiled from planning artifacts. Edit freely. Regenerate with compile-epic-context if planning docs change. -->

## Goal

Make Connector the only way to add or migrate a source, and prove it by running FRED end-to-end behind a typed 10-stage protocol with no schema change and no new `cli.py` / `plans.py` / `registry.sync` dispatcher branches. Shared code keeps provenance, capacity, and persistence; the adapter owns one source family. Later sources inherit this path instead of growing god modules.

## Stories

- Story 2.1: Connector Protocol
- Story 2.2: Registry without HANDLERS if/elif
- Story 2.3: Migrate FRED end-to-end

## Requirements & Constraints

- A Connector owns one source family for the full lifecycle: discover → select → plan → extract → evidence → stage → normalize → validate → publish → checkpoint.
- Registering a source must not require editing central `if/elif` dispatchers. FRED must run without a new `plans.py` HANDLERS branch.
- FRED is the reference migration: no schema change. Discover/index vs observations stay split; observations stay contract-gated. Existing FRED tests must pass; provenance must not regress.
- Every ingest run records provider, dataset, params, URL, checksum, and raw payload or artifact. A loaded fact must resolve to `ingest.run` + URL + checksum.
- Capacity gate fails closed: block bulk download when size is unknown or disk budget fails. Failures must be actionable and resumable.
- Staging may evolve automatically; `core`/`fact` change only through reviewed transforms and stable keys. Raw is immutable. `dlt` writes `stage` only.
- Inventory remains the data SDD: `sources.yaml` registration, reviewed YAML contracts (grain, coverage, cadence, enabled), exact allowed ingest in `plans.yaml`. Do not clone sources into product docs.
- Search for a maintained project before writing acquisition code. Own evidence and canonical keys; wrap upstream behind the Connector.
- Success is Connector-shaped registration, not catalog size. Do not expand ingest scope (no v1.1 money, elections, or crime loads).

## Technical Decisions

- Layered lakehouse + Connector adapters: provider → extract → raw lake → stage → core/fact → mart → api/export. Schemas: `ingest` / `stage` / `core` / `fact` / `mart` / `api`.
- Python split: `providers/` HTTP only, `ingestion/` pipelines, `repositories/` SQL only, `cli.py` coordination only. Shared runtime owns provenance, identity, capacity, and persistence.
- Postgres 17 + PostGIS is the system of record; database name `opendiscourse`. DuckDB, PostgREST, and Parquet are derived.
- Persistence: Alembic for catalog/core/fact/ingest/stage contracts; raw psycopg only for COPY, set-based promotion, OpenStates FDW, and caller-supplied legislative transactions. Bound parameters only; JSON via Jsonb.
- FRED/ALFRED (with Treasury) are the macro spine; BLS/BEA only under reviewed geography/time contracts. This epic does not add those series.
- Protocol work is a typed interface plus tests first; FRED then registers and migrates onto it. Long work uses the shared `feedback` module. Python 3.12; `dlt` is a staging extra only.

## UX & Interaction Patterns

- Operator refreshes a reviewed plan from the existing CLI (`research-db` plan-due / browse): capacity gate first, checksummed lake artifacts, staging replaceable, core/fact only via reviewed transforms, resume command on failure.
- Adding a source: find an upstream project, register in inventory, add a disabled contract, implement a Connector — never a new god-module branch.
- No new UI epic; CLI and optional Textual browse stay the operator surface.

## Cross-Story Dependencies

- Build order: typed protocol (2.1), then registry without HANDLERS (2.2), then FRED e2e (2.3).
- Epic 1 substrate is already the constitution/ADR/skills baseline; this is the next product build.
- Later wrap and identity work (votes, BioGuide-gated politician joins) depend on this Connector path. Epic 8 (legislative primitives) blocks Epic 4. Epic 7 is v1.1: politician joins need Epic 3; do not start FEC/crime staging from this epic.
