# BMAD artifacts

Durable plans distilled from the 2026-09-14 ChatGPT review/plan docs and the
operator decisions that followed (BMAD Method v6 + TEA; Fast path).

| Artifact | Path |
|---|---|
| Product brief | `planning-artifacts/briefs/brief-opendiscourse-2026-09-14/brief.md` |
| PRD | `planning-artifacts/prds/prd-opendiscourse-2026-09-14/prd.md` |
| Architecture spine | `planning-artifacts/architecture/architecture-opendiscourse-2026-09-14/ARCHITECTURE-SPINE.md` |
| Spec kernel | `specs/spec-opendiscourse/SPEC.md` |
| Epics and stories | `planning-artifacts/epics.md` |
| Story specs / epic context | `implementation-artifacts/` (tracked; bmad-build working files) |

Sources (absorbed; do not re-ingest unless updating the spec):

- `docs/research/2026-09-14-chatgpt-review.md`
- `docs/research/2026-09-14-chatgpt-engineering-plan.md`
- `docs/research/2026-09-14-chatgpt-bmad-context-plan.md`
- `docs/research/2026-09-15-chatgpt-architecture-rereview.md` (partial; not a
  replacement epic list; do not implement its strangler reboot)
- `docs/research/2026-09-17-chatgpt-schema-review.md` (keep-and-refine;
  ADR-0002 / `schema-invariants.md`)

Live schema snapshot for external review: `docs/schema-snapshot/`
(reading order: `docs/research/2026-09-17-chatgpt-review-packet.md`).

**Standing (2026-09-17):** Architecture approved. Stories 1.1–1.3, 1.5, 2.1,
8.1 done (PR #21). Story 8.2 implemented on `feat/8-2-openstates-promote-spec`
(PR #22; Alembic `b8c2f1d4e390`). Story 1.4 optional. Story 2.2 = PR #18;
Story 2.3 = PR #20 stacked on 2.2. Story 1.6 not started. Story 8.3 deferred.
Epic 7 closed even though `stage.fec_row` already has data.

Next: merge 8.2; Connector PRs #18/#20 are an independent track. Do not
start Epic 7. Do not redesign.
