# Political research programme: planning-readiness record

## Plain result

The FEC/OpenStates political-research programme is **ready to enter the implementation queue**. This means the work has a defined model, source boundary, completion rules, and story order. It does **not** mean historical FEC data has been transferred, OpenStates has been broadly promoted, or politicians have been joined to finance records.

## Approved contract set

| Area | Governing contract | Planning status | First implementation gate |
| --- | --- | --- | --- |
| Political core / OpenStates | `spec-openstates-political-core/SPEC.md` and `source-mapping.md` | Ready | Run the strictly read-only snapshot/FDW audit: inventory, coverage diff, entity/field dispositions, identity audit, fingerprint, and reconciliation baseline. |
| FEC campaign finance | `spec-fec-reproducible-ingest/SPEC.md` and `coverage-and-grains.md` | Ready | Independently review the four-file 2024 pilot; no transfer before a fresh manifest/capacity approval. |
| Research marts | `spec-political-research-marts/SPEC.md` and `mart-catalog.md` | Ready | Publish only when each mart's source/identity/geography dependencies pass. |
| Programme queue | `spec-fec-reproducible-ingest/stories.yaml` | Ready | Story 1; each story has pre-build and post-completion human checkpoints. |

## Non-negotiable controls

1. `openstates_source` remains read-only evidence; OpenDiscourse does not copy or write the upstream Django schema.
2. FEC bytes come from original FEC endpoints into `DATA_ROOT`; legacy local files and `stage.fec_row` are not rebuild evidence.
3. All useful OpenStates/FEC fields require an explicit typed, retained-detail, or documented-exclusion disposition.
4. A display name never creates a politician link. Federal links require BioGuide; FEC links additionally require the reviewed, enabled identifier bridge.
5. FEC targets available equivalent official products from 2000–2024. Each family/cycle remains subject to capacity, reconciliation, restart, provenance, and coverage gates.
6. Research marts report coverage status and evidence paths; they do not turn unknown, unresolved, or non-comparable data into zeroes.

## Queue completion standard

The six stories are complete only when their contract-specific completion checks pass:

1. OpenStates mapping and field inventory/drift gate.
2. Reviewed compact typed schema and benchmarks.
3. Bounded, reconciled, evidence-backed OpenStates promotion.
4. Approved, repeatable FEC family/cycle batches through the 2000–2024 scope.
5. Reviewed identifier bridge with failure cases for name matching.
6. dbt-owned, coverage-aware political research marts.

An individual story remains incomplete if a required available source is
unresolved, a field/relation is unclassified, a row cannot be reconciled, a
transfer has not been approved, or an identity remains unresolved. A genuinely
publisher-unavailable FEC product is a documented coverage finding, not a
failure; it satisfies its matrix cell without being treated as a zero.

## Remaining decisions that are intentionally deferred

- FEC amendment/version handling is selected per source family during the typed-model story.
- The first historical FEC batch after the 2024 pilot is chosen from a capacity benchmark, not guessed in advance.
- An OpenStates entity absent from the snapshot needs a separate official acquisition decision after the field/coverage inventory proves the gap.
- A district-year mart across redistricting waits for an approved geographic-vintage relationship rule.

## Verification recorded on 2026-10-02

- `stories.yaml` parsed with six unique string IDs and required fields.
- `research-db progress-check` passed.
- `git diff --check` passed.
- Cross-document wording was updated to remove the obsolete six-year FEC-retention rule and the obsolete FEC-2004-only scope.

## Planning exit

The next authorized action is Story 1's **read-only OpenStates field and coverage inventory**. It must not start a bulk promotion, FEC transfer, schema migration, or person-join enablement. Each later story pauses for the checkpoint recorded in `stories.yaml`.
