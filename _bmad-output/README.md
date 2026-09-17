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

Live schema snapshot for external review: `docs/schema-snapshot/`
(reading order: `docs/research/2026-09-17-chatgpt-review-packet.md`).

Partial absorb (2026-09-17): `docs/research/2026-09-15-chatgpt-architecture-rereview.md`
is research, not a replacement epic list. Accepted: OpenStates dump is a source
snapshot (OCD language, not Django schema); identity gates politician *joins*
not every v1.1 acquire; legislative post/division before Epic 4; Connector v2
and market-table move stay deferred. Do not implement the strangler reboot from
that essay.

Next: Story 2.2 (PR #18), then 2.3 (FRED e2e).
Stories 1.1–1.3 and 2.1 are done. Story 1.4 (GitHub ruleset) is optional.
Epic 8 (legislative primitives) blocks Epic 4; do not start it on a FRED branch.
