---
title: 'Legislative tracker reconciliation'
type: 'chore'
created: '2026-09-27'
status: 'done'
route: 'oneshot'
review_loop_iteration: 0
context:
  - 'AGENTS.md'
  - 'docs/PROJECT-STATE.md'
  - '_bmad-output/specs/spec-opendiscourse/legislative-north-star.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** The congressional progress register and legislative north star still describe live-loaded votes and member profiles as unfinished. That hides the actual remaining work: two missing 107th bill details, three unavailable cosponsor pages, and the separate committee-seat merge task.

**Approach:** Reconcile only the written tracker records to the 2026-09-27 live warehouse evidence. Mark completed datasets loaded, add the missing legislator source entry, preserve all named publisher failures, and clearly defer the committee-seat merge behavior to its own task.

## Implementation Notes

- Read-only port-5434 checks confirmed the bill, roll-call, member-vote, person, and membership counts recorded in the 2026-09-27 handoff.
- Reconciled tracker prose only; no connector, schema, artifact, or live warehouse row changed. The Congress.gov source stays `ready` because two detail pages and three cosponsor pages still return HTTP 500.
- Independent review found that the profile load used an unmerged duplicate-leadership fix. The new legislator entry therefore stays `ready`; its observed live values are not described as reproducible completion.

## Review Triage Log

- fixed — The initial legislator entry overstated an unmerged live profile load as reproducibly loaded. It is now `ready`, and its next action requires the focused fix, a main-branch rerun, and recorded run/artifact evidence.
- fixed — The initial scope implied a pinned source without recording a durable revision. It now makes no pin claim, and the next action requires evidence before the item can become loaded.
- false — `ready` is the existing non-final state; the register has no partial state. The source's exact loaded counts, five unavailable requests, and retry stop condition are now in its `next` field, while the north star explicitly says tracker alignment is only partial.
