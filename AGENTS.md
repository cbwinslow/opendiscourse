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
- Every source is acquired from its original government endpoint over the network,
  into the user's `DATA_ROOT`, then inventoried (artifact registry), then ingested into
  the data model: download -> inventory -> ingest, runnable by anyone on their own machine.
  Never ship a loader, script or default that reads a machine-specific path (a legacy
  lake, a homelab folder, `/mnt/...`). Data already sitting on the operator's server is
  a shortcut for that machine only, not an input to the project.
- Adding a source is a Connector (`SPEC.md` CAP-2). Do not add `if/elif` to
  `cli.py`, `plans.py` HANDLERS, or `registry.sync`. Keep provider-specific
  behavior at the adapter boundary.
- Do not write OpenStates dump tables; read `openstates_source` FDW only.
  FDW is not the researcher contract; promote into `core`/`fact` (AD-8).
- Do not name-match people. Federal person *joins* need BioGuide (Epic 3).
  FEC/disclosure/elections politician joins stay gated by `person_join` in
  `inventory/sources.yaml`; call `identitygate.require_person_join` before promoting
  person-keyed rows. Do not start
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
- Merge your own PRs once CI is green (standing operator instruction, 2026-09-19);
  do not ask. Squash merge, subject ending `(#N)`. Reproduce CI failures locally
  (CI runs all DB tests against one shared database, so tests that write rows
  must clean them up) instead of dismissing them.
- Stacked PRs: merge the parent, then `git rebase --onto origin/main <old parent tip>
  <branch>`, force-push with lease, retarget via `gh api -X PATCH
  repos/cbwinslow/opendiscourse/pulls/N -f base=main` (`gh pr edit --base` fails on a
  deprecated GraphQL field), then close and reopen the PR: a base change does not
  trigger `fast`/`test`.

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
  error. Wiping and re-ingesting untrustworthy *derived rows* is authorized by the
  operator; do it when it is the right fix, and record what you wiped in
  `docs/PROJECT-STATE.md` or the run ledger. No need to ask first.
- The 10-stage Connector is current (Story 2.3), not sacred; do not redesign
  it on the FRED branch. `docs/research/2026-09-15-chatgpt-architecture-rereview.md`
  and `docs/research/2026-09-17-chatgpt-schema-review.md` are research, not
  replacement epic lists. Keep-and-refine; AD-10 is the absorb.

<!-- /bmad:context -->

## Talking to the operator (mandatory, every reply)

The operator is not a database engineer and does not follow jargon. Every reply to them:

1. **Starts with the plain answer**: what happened or what you recommend, in ordinary words, before any detail.
2. **Explains terms the first time** (one short phrase: "a trigger is a rule the database runs by itself"). Prefer
   "the database refuses the edit" over "raises 42501". Say what a thing is *for* before what it is called.
3. **Gives options with a recommendation** whenever there is a choice: each option in one or two plain sentences,
   what it costs or risks, then "I recommend X because Y". Name your concerns and doubts, do not bury them.
4. **Ends with what happens next** and whether anything is needed from the operator.
5. **Never drops information to keep it simple.** If something cannot be put simply, include it in the normal technical
   wording, labelled "technical detail", rather than leaving it out. Simplifying is never a reason to omit a finding,
   a risk, a skipped item, or a failed check.
6. Keep a short status view when asked: done, running, next, blocked. Do not claim work is done that has not been verified.

Code, specs, ADRs and commit messages keep their normal precision; this rule is about replies to the operator.
