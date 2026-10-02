---
id: SPEC-source-completion
companions:
  - completion-matrix.md
  - ../../spec-opendiscourse/SPEC.md
  - ../../spec-opendiscourse/legislative-north-star.md
  - ../spec-longitudinal-source-coverage/SPEC.md
  - ../../../docs/PROJECT-STATE.md
sources:
  - ../../../inventory/DATA-SPEC.md
  - ../../../inventory/progress.yaml
  - ../../../docs/data-acquisition-plan.md
  - ../../../docs/data-source-map.md
---

> **Canonical contract.** This SPEC and its companions define the delivery queue and the evidence required to call each source complete. Current code and tests outrank this document; `docs/PROJECT-STATE.md` is the current operational handoff.

# Source completion north stars and delivery queue

## Why

OpenDiscourse has substantial data already loaded, but its source register, operational handoff, and older planning documents do not always agree. That makes it too easy to treat a downloaded file or a merged command as completion, or to start a large new source before the v1 spine is auditable. This specification gives the operator one plain, dependency-ordered answer to: what is loaded, what is actually unfinished, what must be specified before work begins, and how completion is proven.

## Capabilities

- **CAP-1**
  - **intent:** The operator can inspect every active or catalogued source in one completion matrix and see its scope, current state, next action, completion test, and whether work is authorized.
  - **success:** The matrix classifies every source in `inventory/sources.yaml` as v1 active, v1 conditional, v1.1 deferred, catalogued/unapproved, or prohibited, and names the authoritative state record when trackers disagree.

- **CAP-2**
  - **intent:** The operator can work through a dependency-ordered v1 data queue without guessing which source to download or ingest next.
  - **success:** Each queued item names its prerequisite, bounded deliverable, BMAD spec required before build, verification command or measurable check, and explicit stop condition.

- **CAP-3**
  - **intent:** The operator can call a source complete only when its data is reproducible and auditable rather than merely present in the database.
  - **success:** Each active source meets the shared completion gate: original-source acquisition into `DATA_ROOT`, immutable inventory, field accounting, evidence-linked rows, idempotent/resumable load, and publisher-based coverage where the publisher exposes a count.

- **CAP-4**
  - **intent:** The operator can defer sources safely without losing their known scope or accidentally opening prohibited work.
  - **success:** The approved FEC/OpenStates programme, disclosures, elections, crime, news, stocks, and the mixed Epstein collection each show their authorization and prerequisites; FEC transfer, canonical promotion, and joins cannot proceed until their individual gates pass.

- **CAP-5**
  - **intent:** The operator can see each source's earliest official release, continuous annual coverage, publisher gaps, and valid comparison windows before authorizing historical backfill.
  - **success:** The matrix names the official availability boundary and any comparability restriction for every active source; a source beginning after 2000 has a stated publisher reason rather than an assumed omission.

## Constraints

- The hierarchy of truth is current code and tests, then schema/migrations, then the architecture and active specs, then the operational state; `inventory/progress.yaml` must be reconciled when it disagrees rather than copied forward.
- Every implementation is a source Connector: download from the original publisher into the user's `DATA_ROOT`, inventory immutable bytes, then ingest through the Connector lifecycle. No machine-specific lake path, untracked cache, central dispatcher branch, or name-based person join is allowed.
- A source-specific BMAD build spec is required before a new connector, source expansion, schema change, or large acquisition. Its acceptance criteria include failure, idempotency, resume, provenance, capacity, and coverage behavior.
- A completion claim needs a field checklist; absence of a checklist means the source is incomplete even when rows are present.
- The longitudinal target is calendar year 2000 where an equivalent official product exists. A later start is allowed only when the publisher did not release that product, and the boundary remains visible to researchers.
- The legislative source of truth remains `legislative-north-star.md`; this spec coordinates it but does not lower or replace its standard.

## Non-goals

- This is not authorization to download every catalogued source or to revise existing loaded data without evidence.
- This does not authorize FEC transfer, promote legacy FEC staging, link politicians by name, or create scorecards.
- This does not replace the detailed legislative north star, rebuild-kit specification, Connector protocol, source contracts, or field checklists.
- This does not add Pandera or any other validation library solely to create a technology checklist.

## Success signal

At any handoff, a new operator can open this spec and its matrix, select the highest-ready v1 item, find the exact evidence and completion bar, and know why every other source is waiting. The live warehouse, `inventory/progress.yaml`, field checklists, and `docs/PROJECT-STATE.md` then agree for every source marked loaded.

## Assumptions

- The work is an express source-completion plan derived from the existing
  project contract and state, including the separately approved strict-gated
  FEC/OpenStates programme; it does not authorize every catalogued source.
