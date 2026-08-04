# OpenStates 119th Congress vote refresh and reconciliation plan

## Decision and scope

This is the next bounded congressional-ingestion phase. It refreshes the
read-only OpenStates provider snapshot and reconciles the 119th Congress vote
baseline into canonical roll-call and member-vote tables. It does **not**
replace OpenStates source ownership, scrape Congress.gov vote pages, enable a
recurring scheduler, or mark 119th votes complete without the promotion gate
below.

Current evidence (2026-08-04): the provisioned snapshot contains 739 source
vote events and 739 unique identifiers, all of which map to 739 canonical
roll calls and 163,452 member votes. This is internally reconciled but remains
`partial` because the snapshot has not been refreshed and assessed for current
119th coverage.

## Implementation status

The contract-backed read-only dry run is implemented as
`research-db plan-openstates-vote-refresh`. It records source/canonical counts,
source event watermarks, storage reserve, and approval state in
`meta/plan/openstates/openstatesvotes-dry-run.json`. Its expected current
result is `approval_required`: snapshot acquisition, source access, promotion,
and scheduling remain deliberately unapproved.

## Desired outcome

Maintain OpenStates as the bill/person/vote reference baseline while producing
a repeatable, source-preserving refresh process that can safely advance 119th
vote coverage. The process must make the snapshot version, source freshness,
row-count deltas, cursor position, canonical effects, and any unresolved
identities auditable.

## Preconditions and explicit approval gates

| Gate | Required evidence | Owner decision | Effect if absent |
|---|---|---|---|
| Source access | Approved OpenStates endpoint, credential method, terms/rate limits, and snapshot export method | Operator | Do not contact or replace source snapshot |
| Storage | Previewed snapshot size, checksum location, staging location, and 100 GiB reserve | Operator | Do not download or stage |
| Contract | `openstatesvotes` contract reviewed; its cursor and validation rules match the refresh implementation | Maintainer | Contract remains disabled |
| Dry run | Read-only source inspection writes a report and changes neither the provider snapshot nor canonical tables | CI/operator | Do not enable or load |
| Promotion | Fresh snapshot validation plus canonical reconciliation meets the criteria below | Maintainer | 119th votes remain partial |
| Scheduling | A successful manual refresh, resume test, and rollback drill have been recorded | Operator | No cron/systemd timer is installed |

Approval is intentionally granular: approving a snapshot refresh does not
authorize promotion to complete or recurring execution.

## Workstreams

### 1. Snapshot contract and evidence model

1. Extend the disabled `openstatesvotes` contract with:
   - exact endpoint/export identity and source snapshot version;
   - source watermark (`updated_at` or publisher revision) and retrieval time;
   - expected tables, jurisdictions, Congresses, and a declared completeness
     policy;
   - staging path, SHA-256 checksum, artifact key, and retention policy;
   - provider pacing/retry policy owned by the OpenStates provider module.
2. Add a versioned snapshot manifest under `meta/plan/openstates/` containing
   no secrets and recording the preceding fields plus planned row counts.
3. Keep the restored Postgres snapshot behind the `openstates_source` FDW.
   Do not copy it directly into `core`/`fact` tables; canonical changes flow
   only through the existing repository loaders.

Success measures:

- `research-db catalog-check` accepts the amended contract.
- The manifest has a stable artifact key, SHA-256 field, source URL/identity,
  extraction time, and expected row counts for `voteevent` and `personvote`.
- Review can determine exactly which snapshot produced any canonical row.

Implementation: use the reviewed template at
`plans/templates/openstates-snapshot-manifest.yaml` and validate a supplied
dump with `research-db validate-openstates-snapshot --manifest <path>`. The
validator is read-only: it verifies byte count, SHA-256, and required archive
relations before any restore or FDW action is considered.

### 2. Read-only discovery and dry run

1. Implement a provider-owned snapshot inspection command. It may request
   metadata or enumerate a proposed export but must not write the source FDW,
   canonical tables, or `ingest.run` as a successful ingestion.
2. Produce a JSON dry-run report showing:
   - old and proposed snapshot watermarks;
   - row/identifier counts by Congress and chamber when available;
   - estimated staging/database space and available reserve;
   - proposed artifact checksum/path;
   - expected canonical insert/update counts based on stable vote identifiers;
   - a clear `no_writes: true` assertion.
3. Fail closed for missing credentials, an unapproved contract, an unknown
   watermark, insufficient space, or a source schema incompatible with the
   FDW mappings.

Success measures:

- Dry run exits zero only when all evidence is present and writes its report.
- Database row counts and `ingest.run` counts are unchanged before/after a
  dry run.
- Tests cover disabled-contract rejection, missing source metadata, no-write
  behavior, and an incompatible source schema.

### 3. Snapshot acquisition and source validation

1. After explicit source-access and storage approval, acquire the exact
   snapshot/export into the data lake with progress, elapsed time, ETA,
   checksum, and safe-resume information.
2. Verify checksum and archive/database integrity before exposing the snapshot
   through `openstates_source`.
3. Stage/restore it as a separate provider-owned database or schema; update
   the FDW mapping atomically only after validation succeeds.
4. Record an `ingest.artifact` row for the provider snapshot. Preserve the old
   snapshot and FDW connection details until post-load verification passes.

Success measures:

- Artifact checksum equals the manifest checksum.
- Required tables and stable identifier columns are present.
- Source counts by Congress are recorded; identifier uniqueness is measured,
  not assumed.
- A failed restore leaves the prior source FDW mapping usable.

### 4. Canonical vote refresh with safe resume

1. Run a bounded smoke load for 119th votes using the existing keyset cursor
   (`ocd_id`) and committed pages.
2. Compare smoke output with source counts and verify artifact lineage on every
   created/updated roll call and member vote.
3. Run the full 119th load in committed pages. Record the last completed
   cursor after each page and show current page, records processed, elapsed
   time, remaining estimate, and exact resume command.
4. On rerun, skip stable roll-call/member-vote identities already committed;
   do not duplicate facts or overwrite unrelated canonical metadata.
5. Resolve any new people only through stable OpenStates identifiers or an
   approved Congress.gov BioGuide lookup. Emit exceptions rather than using
   name matching.

Success measures:

- Smoke load is bounded and idempotent on a second execution.
- An injected mid-run failure resumes after the last committed page with no
  duplicate roll calls, member votes, artifacts, or identifiers.
- Full load has one terminal `ingest.run` record with record count, snapshot
  artifact, cursor/range, and explicit `partial` coverage until promotion.
- All canonical write paths use repositories and parameterized SQL.

Implementation: the vote loader persists an `ingest.resume_cursor` checkpoint
after every committed keyset page. `research-db load-openstates-votes --resume`
continues after its recorded `ocd_id` and prints a safe resume command. A
snapshot change still requires a new artifact/validation cycle before reuse.

### 5. Reconciliation and 119th promotion decision

1. Run `research-db reconcile-openstates-votes --congress 119` and persist a
   detailed report with source event count, source unique identifiers,
   canonical roll-call count, member-vote count, and duplicate identifiers.
2. Run congressional health and the identity-exception report. Review all
   unresolved identities and failed/stale ingestion runs.
3. Compare snapshot scope/watermark to the published 119th coverage target.
   Internal source-to-canonical equality alone is not sufficient to claim the
   source itself is complete.
4. Promote only by changing the contract approval and health coverage policy
   in the same reviewed commit, with exact validation evidence in the notes.

Promotion criteria:

- Approved snapshot manifest and verified checksum;
- source schema validation succeeds;
- `source_keys == canonical_roll_calls` after applying the documented duplicate
  policy;
- member-vote counts and unresolved-person exceptions are reviewed;
- no unacknowledged failed or stale related runs;
- source watermark/coverage evidence supports a complete 119th scope;
- unit/integration tests and catalog validation pass.

If any criterion fails, preserve all evidence and retain `votes.119: partial`.

### 6. Scheduling and operational handoff

Only after one manually verified refresh and one resume drill:

1. Add a disabled-by-default systemd timer or equivalent scheduler definition
   that invokes the dry run first and runs the loader only when contract
   approval is enabled.
2. Add alertable outcomes for stale runs, actionable failures, source schema
   drift, reconciliation mismatch, storage threshold, and unresolved identity
   growth.
3. Update the runbook with normal execution, resume, rollback, and emergency
   disable procedures.

Success measures:

- Scheduler dry run makes no provider/canonical writes.
- Disabling the contract stops scheduled writes without deleting artifacts.
- An operator can resume, roll back the FDW mapping, and find all validation
  reports using the runbook alone.

## Test matrix

| Area | Required coverage |
|---|---|
| Contract | Invalid/missing approval, malformed manifest, disabled contract rejection |
| Provider | Paging, pacing/retry boundary, schema drift, checksum mismatch |
| Repository | Idempotent roll-call/member-vote upsert and parameter binding |
| Resume | Failure after a committed page, cursor restart, no duplicates |
| Identity | Resolved stable ID, missing ID exception, conflicting ID preservation |
| Health | Empty source, partial snapshot, recovered run, actionable failure, promotion evidence |
| End-to-end | Dry run has no writes; bounded smoke; full reconciliation against a fixture snapshot |

## Sequencing and deliverables

1. Contract/manifest and dry-run implementation with tests.
2. Review the dry-run report and request source/storage approval.
3. Acquire and validate the snapshot; preserve previous mapping.
4. Smoke, resume drill, then full canonical load.
5. Reconcile, resolve exceptions, and make the promotion decision.
6. Add scheduling only after all prior gates are green.

Each numbered deliverable is a separate focused commit with its tests and
validation output noted in the commit body or linked runbook evidence.

## Rollback boundaries

- Snapshot download/staging failure: remove only the incomplete staging
  artifact; retain the prior source mapping and canonical tables unchanged.
- Source validation failure: do not alter the FDW mapping or canonical data.
- Canonical-load failure: rerun from the recorded committed cursor; do not
  delete existing canonical facts to retry.
- Post-load reconciliation failure: retain the run/artifact evidence, keep
  119th votes partial, and revert only the source mapping or the focused
  canonical migration if a reviewed rollback is necessary.
- Promotion error: revert the contract/health policy commit; it does not
  remove source artifacts or canonical provenance.
