---
title: Story 1 — Read-only OpenStates snapshot audit
type: feature
created: '2026-10-02'
status: in-progress
baseline_commit: a6baee74d391742a73c6c3b1645fc5edf7c925d4
route: dispatch
review_loop_iteration: 1
context:
  - docs/SESSION-HANDOFF-2026-10-02-POLITICAL-RESEARCH-PLANNING.md
  - _bmad-output/specs/spec-openstates-political-core/source-mapping.md
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

Produce a reproducible evidence audit answering what is in the restored OpenStates
snapshot, what the existing FDW can read, how every source relation and public field
should be treated, and which owned-schema or reader changes a later story requires.
GitHub issue #100 tracks this story under parent #99.

## Boundaries & Constraints

Always use read-only transactions, explicit timeouts, quoted identifiers, and
operator-supplied connections. Never publish connection secrets or private
application/account values. Classify every source relation, including administrative
and extension tables, before deciding whether its data is public research evidence.
The audit may inspect the restored snapshot directly for its approved inventory;
future production promotion continues through the approved FDW. Connections do not
authorize role changes or reader expansion.

Preserve source evidence and all unrelated working-tree changes. Produce proposed
mapping targets without creating them. No migrations, source writes, FDW alterations,
canonical promotion, FEC transfers, or actual cross-provider person links.

## I/O & Edge-Case Matrix

| Scenario | Input/state | Expected behavior | Error handling |
| --- | --- | --- | --- |
| Complete audit | Readable snapshot and warehouse catalogs | Versioned inventory, mappings, coverage, identity and reconciliation outputs | Validate output completeness before reporting success |
| Missing FDW relation | Present source relation without approved exposure | Explicit present-but-unreadable disposition | Never silently exclude it |
| Restricted table | Account/authentication or operational relation | Catalog inventory with implementation disposition and reason | Never sample sensitive values |
| Query timeout/permission failure | Any required measurement unavailable | Record query scope and unresolved evidence | Audit remains incomplete; no invented zero |
| Nested-field drift | New public JSON path, table or column | Baseline comparison rejects the changed structure | Require reviewed baseline update |
| Name collision | Different source IDs with the same display name | Distinct unresolved identities | No person link |
| Missing artifact proof | Restore cannot be tied to verified registered bytes | Explicit unresolved snapshot lineage | Cannot claim a verified artifact fingerprint |

</frozen-after-approval>

## Code Map

- `scripts/export_schema_snapshot.py`: existing catalog export patterns; do not
  invoke its broad export as an audit or copy its embedded SQL into a new public module.
- `src/opendiscourse_research/openstatessnapshot.py`: reuse checksum and archive
  manifest validation; validation itself does not prove which bytes were restored.
- `src/opendiscourse_research/repositories/artifacts.py`: existing usable-artifact
  reader; do not select an arbitrary latest provisional artifact.
- `src/opendiscourse_research/feedback.py`: shared progress reporting.
- `docs/schema-snapshot/openstates-inventory.md`: historical reference only;
  estimated rows must not be described as verified current counts.
- `docs/openstates-integration.md`: minimum reader boundary and identifier policy.
- `sql/query/`: maintained home for executable audit SQL.

## Tasks & Acceptance

**Execution:**

- [x] `sql/query/openstates_audit/`: add catalog, FDW, column/profile, coverage,
  identifier and reference-integrity queries with bounded read-only execution.
- [x] `src/opendiscourse_research/repositories/openstates_audit.py`: implement
  isolated read-only query access and safely quoted catalog-derived identifiers.
- [x] `src/opendiscourse_research/openstatesaudit.py`: add deterministic inventory
  generation and baseline validation; expose a module command without expanding
  provider dispatchers. Connections and output destination are explicit arguments.
- [x] `docs/audits/openstates/2026-10-02/`: save relation/column/nested-field
  inventory, FDW diff, entity/field dispositions, jurisdiction/session coverage,
  fingerprint, identity audit and reconciliation baseline, plus readable report.
- [x] `tests/test_openstates_audit.py`: verify drift detection, incomplete-evidence
  failures, deterministic serialization, name collisions and identifier policy.
- [x] `tests/test_openstates_audit_db.py`: verify read-only enforcement, catalog
  and profiling queries, permission failures and reference reconciliation.
- [x] `docs/PROJECT-STATE.md`: record evidence, remaining gaps and the issue status;
  close #100 only after every governing definition-of-done condition is satisfied.
  Not closed: semantic mapping was accepted on 2026-10-04, but field-level
  review times and restored-archive lineage are still absent.

**Acceptance Criteria:**

- Given the actual restored snapshot, when audited, then every relation and scalar
  column has a disposition and every public nested field is inventoried; bounded
  samples alone cannot establish exhaustive nested-field coverage.
- Given a source relation absent from the reader, when compared, then the report
  names its source schema/table and readability status without altering access.
- Given unknown or partial coverage, when reporting periods/jurisdictions, then
  missing data is distinguished from an observed zero and publisher availability
  is not inferred from the dump alone.
- Given source identity records, when audited, then identifier namespaces and
  BioGuide missingness/duplicates are measured without creating person links.
- Given a reviewed baseline, when an unreviewed relation/column/nested path changes,
  then validation fails closed. Declared keys and source counts form later
  promotion reconciliation metrics.
- Given generated evidence, when mapped to current owned tables, then necessary
  schema deltas and unresolved decisions are explicit, with no table-copy proposal.
- Given an interrupted audit, when resumed, then incomplete measurements remain
  visible and successful evidence is reusable only for the same snapshot baseline.

## Implementation Notes

Initial read-only catalog checks on 2026-10-02 observed PostgreSQL 17.11,
88 public snapshot relations, and 11 relations in `openstates_source`. This is
structural evidence only; exact counts, field profiles and coverage remain unmeasured.
Implementation checkout: `/home/cbwinslow/workspace/opendiscourse-story-1`, branch
`feat/openstates-audit-story-1`, based on the committed programme.

## Spec Change Log

2026-10-04: the operator accepted the semantic mapping in
`../spec-openstates-political-core/source-mapping.md`, including the future
schema mismatches. That acceptance does not complete #100. `mapping-review.json`
is still `approved: false`. Restore lineage is still absent. No migration was
written.

2026-10-03: the unapproved schema decisions that block promotion are listed in
`../spec-openstates-political-core/source-mapping.md`. `mapping-review.json`
remains a proposal (`approved: false`). Parent-derived coverage was measured
and is not an approval. Restore lineage is still absent, so #100 stays open.

2026-10-02 independent review: the first implementation exposes useful evidence
but does not satisfy all completion gates. Refine the non-frozen implementation
design: consistent exported read snapshots; effective RLS visibility checks;
source/reader column and type diff retaining every alias; tagged nested paths;
recomputed structural fingerprints; explicit reviewed mapping/restore-evidence
inputs; concrete semantic field transformations; text-date precision profiles;
parent-derived coverage; and tested identity/privacy behavior. Preserve the
read-only boundary, immutable original run evidence, honest unresolved scopes,
quoted identifiers, environment-based connections, and passed regression checks.
Do not fabricate a restore attestation or change failed measurements to zero.

## Review Triage Log

| Finding | Verdict | Evidence and disposition |
| --- | --- | --- |
| Blind 1: no passing approval path | high | Approval flags are hardcoded false; add validated evidence inputs, remaining unset for this unproven live restore. |
| Blind 2: fingerprint not recomputed | high | validate trusts a supplied fingerprint; recompute manifest from recorded structures before comparing. |
| Blind 3: only direct coverage | high | Child entities have no derived jurisdiction/session groups; complete parent-derived coverage with unresolved links visible. |
| Blind 4: text dates unmeasured | high | Historical date fields are predominantly varchar; add precision-aware text-date profiling without inventing full dates. |
| Blind 5: mixed measurement snapshots | high | Each query opens a new transaction; export/import a consistent read snapshot while preserving independent error recovery. |
| Blind 6: RLS completeness | medium | Current snapshot has no demonstrated filtered relation, but runner lacks effective visibility guard; fail closed on active row filtering. |
| Blind 7: reader column/type coverage | medium | Reader tables are probed but column exposure and duplicate aliases are absent; inventory both. |
| Blind 8: occurrence rates versus missingness | false | The corrected derived artifact explicitly labels rates as present-path occurrences and excludes absence; no claim of source-row missingness is made. Add row-presence metrics if deriving them with exact scope. |
| Blind 9: resumability | medium | Checkpoints retain evidence but only complete reruns are supported; implement verified-baseline scope reuse or keep resume unavailable and document the gate precisely. |
| Blind 10: name-only proposed fields | high | Proposed typed targets lack concrete source-to-owned transformations and constraint decisions; replace generic proposals with a semantic mapping review. |
| Blind 11: coupled fingerprint components | medium | Whole fingerprint comparison couples candidate artifacts and measured values to schema drift; separate structural identity, evidence identity, mapping approval and measurements. |
| Edge 1: row filtering | medium | Same visibility guard gap as Blind 6; preserve independent reviewer finding in this log. |
| Edge 2: mixed snapshots | high | Same transaction-consistency gap as Blind 5. |
| Edge 3: literal [] key collision | high | Untagged object keys and array steps share a token; encode their kinds separately and qualify legacy evidence. |
| Edge 4: reader aliases overwritten | medium | A dictionary keyed by source relation keeps one exposure; retain all reader aliases and probe each independently. |
| Verification 1: identity-query test gap | medium | Existing collision helper test does not execute identity.sql/bioguide.sql; add isolated data-backed exact assertions. |
| Verification 2: sampling guard test gap | medium | Classification tests cannot detect restricted sampling regression; exercise full audit with private sentinels and assert no sample call/output. |

## Verification

- `just check-fast`: required fast checks pass in the isolated checkout.
- `just check-db`: database tests pass against a separate test database; never
  point mutation-capable test fixtures at either live database.
- Live audit: all source and warehouse connections remain read-only; fingerprint
  and disposition validation complete or explicitly report blocking evidence gaps.
- `git diff --check`: changed files have no whitespace errors.
