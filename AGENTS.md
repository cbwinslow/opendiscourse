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
  FDW is not the researcher contract; promote into `core`/`fact` (AD-8).
- Do not name-match people. Federal person *joins* need BioGuide (Epic 3).
  FEC/disclosure politician joins stay blocked until then. Do not start
  Epic 7 (FEC-native/crime staging, elections) in v1.
- Do not invent news, stocks, or corruption scores as schema domains.
  Politician scorecards are allowed later only as derived `mart` outputs over
  evidence-backed `core`/`fact` rows (SPEC non-goals); never an opaque single
  "corruption score".
- Never commit secrets or `.env`. Capacity gate fails closed on unknown size.
- `dlt` writes `stage` only, never `core`/`fact`.

## Where things are

- Product contract: `_bmad-output/specs/spec-opendiscourse/SPEC.md`
- Architecture: `_bmad-output/planning-artifacts/architecture/architecture-opendiscourse-2026-09-14/ARCHITECTURE-SPINE.md`
- ADRs: `docs/adr/0001-postgres-system-of-record.md` (Postgres system of
  record); `docs/adr/0002-schema-invariants.md` (identity, provenance,
  ownership, schema ≠ ingest)
- Project skills: `.agents/skills/opendiscourse-connector`, `opendiscourse-schema-change`, `opendiscourse-provenance`, `opendiscourse-testing`
- Data registry: `inventory/sources.yaml`, `plans.yaml`, `contracts/`
- HTTP only: `src/opendiscourse_research/providers/`
- Pipelines: `src/opendiscourse_research/ingestion/`
- SQL only: `src/opendiscourse_research/repositories/`
- Runtime SQL: `sql/query/`; bootstrap schema: `sql/NNN_*.sql`; catalog from
  Alembic baseline `d207df35ca10` onward
- Upstream clones: `vendor/` (gitignored); refresh `scripts/bootstrap_upstream.sh`
- Planning index: `_bmad-output/README.md`
- **Current state, decisions, and next steps: `docs/PROJECT-STATE.md`. Read it
  first when resuming; update it when a decision or story status changes.**

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
- Do not delegate to Antigravity/Gemini ("AGY"). Its merged work was reverted
  in #26 after independent review (operator, 2026-09-19). Any AGY-authored code
  still in the tree (e.g. Story 1.6 tests) is unverified: re-run the gates and
  get independent review before building on it. Never trust its "tests passed".
- Never merge a PR the operator has not seen reviewed. Open PRs; do not merge.

## Known pitfalls

- `cli.py` and `plans.py` are god modules. New sources go through a Connector,
  not another dispatcher branch.
- `IngestionRun` is a provenance context manager, not a Connector.
- `core.embedding.vector_values` is `real[]` for portability; the live cluster
  has pgvector but promotion is a later ADR.
- `censusdis` is Hippocratic-licensed — do not add it as a required dependency.
- OpenStates database `openstates` is a provider snapshot; do not merge it
  into `opendiscourse`. Do not ingest Congress.gov/GovInfo/clerk rows into
  the dump; combine in `core` by identifier.
- Read artifacts only through `ingest.current_artifact` /
  `repositories/artifacts.py` (newest *usable* version). Never write
  `ORDER BY artifact_version DESC LIMIT 1` in a loader: a failed refresh appends
  a provisional version that would shadow verified bytes (Story 1.7).
- Retained artifact files are evidence: never overwrite or delete one to fix an
  error. Wiping and re-ingesting *untrustworthy derived rows* is authorized by
  the operator; list what will be deleted and get a yes first.
- The 10-stage Connector is current (Story 2.3), not sacred; do not redesign
  it on the FRED branch. `docs/research/2026-09-15-chatgpt-architecture-rereview.md`
  and `docs/research/2026-09-17-chatgpt-schema-review.md` are research, not
  replacement epic lists. Keep-and-refine; AD-10 is the absorb.

<!-- /bmad:context -->
