<!-- bmad:context -->
<!-- Verified 2026-09-14 against 5fa7c49724f9d41cd1254b27d1744c6e4920d704. Managed by bmad-project-context; edits inside this block are replaced on refresh. Keep anything you want preserved outside the markers. -->

## OpenDiscourse

Provenance-first U.S. public-policy research warehouse. PostgreSQL 17/PostGIS,
database name `opendiscourse`. Software SDD is BMAD; data SDD is `inventory/`.
Start from `_bmad-output/specs/spec-opendiscourse/SPEC.md` and
`_bmad-output/planning-artifacts/epics.md`, not archived ChatGPT essays.

## Policy

- Hierarchy of truth, highest wins: current code+tests → migrations/schema →
  architecture spine/ADRs → active BMAD spec/story → GitHub → agent memory →
  old chats → model guesses.
- Search for a maintained project before writing acquisition, parse,
  orchestrate, search, or export code. Wrap it; own evidence and canonical
  keys. Catalog: `reuse.md` beside the spec.
- Adding a source is a Connector (`SPEC.md` CAP-2). Do not add `if/elif` to
  `cli.py`, `plans.py` HANDLERS, or `registry.sync`. Keep provider-specific
  behavior at the adapter boundary.
- Do not write OpenStates dump tables; read `openstates_source` FDW only.
- Do not load FEC, disclosures, elections, or crime until BioGuide identity
  exists (Epic 3).
- Do not invent news, stocks, or corruption scores as schema domains.
- Never commit secrets or `.env`. Capacity gate fails closed on unknown size.
- `dlt` writes `stage` only, never `core`/`fact`.

## Where things are

- Product contract: `_bmad-output/specs/spec-opendiscourse/SPEC.md`
- Architecture: `_bmad-output/planning-artifacts/architecture/architecture-opendiscourse-2026-09-14/ARCHITECTURE-SPINE.md`
- ADRs: `docs/adr/0001-postgres-system-of-record.md` (Postgres system of record)
- Project skills: `.agents/skills/opendiscourse-connector`, `opendiscourse-schema-change`, `opendiscourse-provenance`, `opendiscourse-testing`
- Data registry: `inventory/sources.yaml`, `plans.yaml`, `contracts/`
- HTTP only: `src/opendiscourse_research/providers/`
- Pipelines: `src/opendiscourse_research/ingestion/`
- SQL only: `src/opendiscourse_research/repositories/`
- Runtime SQL: `sql/query/`; bootstrap schema: `sql/NNN_*.sql`; catalog from
  Alembic baseline `d207df35ca10` onward
- Upstream clones: `vendor/` (gitignored); refresh `scripts/bootstrap_upstream.sh`
- Planning index: `_bmad-output/README.md`

## Running and verifying

- Use `uv run` / `just check-fast`. Bare `pytest` or `ruff` may miss the
  project environment.
- Fast lane (CI `fast` job): `just check-fast` or `bash scripts/ci/check_fast.sh`
  — `ruff check src` plus `pytest -m "not db and not slow and not live and not e2e" -n auto`.
- DB tests: `just check-db` (needs `OPENDISCOURSE_TEST_DATABASE_URL` or
  testcontainers). Do not pass `-n` for DB tests.
- Full suite: `just check-full`. Never run `-m live` in ordinary CI.
- App DSN default: `postgresql:///opendiscourse?port=5434`. Docker Compose
  fallback is port `5433`, still database `opendiscourse`.
- `ty`, `ruff format`, and `sqlfluff` are installed but not merge gates.

## Conventions that differ from defaults

- Long work uses `opendiscourse_research.feedback` (spinner or progress bar,
  phase, resume, actionable failure) — not ad-hoc prints.
- Bound parameters only; JSON via `psycopg.types.json.Jsonb`.
- Alembic for catalog/core/fact/ingest/stage. Raw psycopg for COPY, set-based
  promotion, OpenStates FDW, and caller-supplied legislative transactions.
- Federal people join on BioGuide, never display name.
- Change class: XS/S → `bmad-build`; M → `bmad-spec` then Build; L/XL →
  existing PRD/spine/epics. Do not add OpenSpec or Spec Kit.
- TEA/pytest: warehouse tests, not Playwright-first.
- New public modules need docstrings. Tests ship with the change, including
  failure, idempotency, resume, and provenance cases when they apply.
- Small cohesive commits; agents may commit and push focused work. Imperative
  subject plus body when the why is not obvious.
- Codex may delegate bounded mechanical work to Antigravity (plan mode unless
  edits are authorized); inspect output before relying on it.

## Known pitfalls

- `cli.py` and `plans.py` are god modules. New sources go through a Connector,
  not another dispatcher branch.
- `IngestionRun` is a provenance context manager, not a Connector.
- `core.embedding.vector_values` is `real[]` for portability; the live cluster
  has pgvector but promotion is a later ADR.
- `censusdis` is Hippocratic-licensed — do not add it as a required dependency.
- OpenStates database `openstates` is a provider snapshot; do not merge it
  into `opendiscourse`.

<!-- /bmad:context -->
