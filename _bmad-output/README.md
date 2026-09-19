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

**Standing:** see `docs/PROJECT-STATE.md` (updated 2026-09-19). AGY's merges
(2.2, 2.3, 8.2, 1.7) were reverted in #26 and are being redone; do not use the
2026-09-17 status that used to be here.
