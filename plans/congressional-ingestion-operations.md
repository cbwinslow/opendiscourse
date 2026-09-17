# Congressional ingestion operations plan

## Purpose

Operate the congressional warehouse as a source-preserving, observable system.
OpenDiscourse owns the canonical research model; it does **not** appoint one
provider database as a universal federal truth baseline. Official source
artifacts remain independently identifiable and reconcilable:

- GovInfo supplies official bulk BILLSTATUS, bill text, summaries, and package
  evidence for historical/bootstrap acquisition.
- Congress.gov supplies current/incremental legislative and member metadata and
  source-native identifiers.
- The House Clerk and Senate LIS supply chamber-native roll-call evidence.
- `congress-legislators` supplies a maintained identity/term crosswalk that is
  reconciled to official identifiers; BioGuide is the deterministic federal
  person join key.
- OpenStates is a read-only provider snapshot and OCD interoperability/reference
  source. It is useful for state/local data and cross-source reconciliation but
  is not the authority that overwrites conflicting official federal evidence.

Canonical rows reconcile these sources by stable identifiers while retaining
source-specific evidence. A disagreement is surfaced and investigated; it is
not silently resolved by display name, provider ordering, or last-writer-wins.
This plan does not authorize copying provider snapshots wholesale into
canonical tables or promoting incomplete coverage as complete.

## Federal source-role contract

| Domain | Primary acquisition/evidence | Secondary/reconciliation | Rule |
|---|---|---|---|
| Bill identity/status/actions | GovInfo BILLSTATUS bulk + Congress.gov | OpenStates | Join on Congress + normalized measure type + number. Preserve source observations and identifiers. |
| Bill text/versions | GovInfo BILLS/BILLSUM/package artifacts | Congress.gov text metadata | A version is an immutable document with URL/package/version/checksum evidence. |
| Federal people | Congress.gov/BioGuide | `congress-legislators`, OpenStates identifiers | BioGuide is the deterministic join key; names are labels only. |
| Terms/seats/party/caucus | Official member data + `congress-legislators` temporal terms | OpenStates membership/post semantics | Preserve start/end dates and affiliation changes; never infer a historical affiliation from a current label. |
| House roll calls | House Clerk chamber-native vote data | Congress.gov house-vote where coverage is verified; OpenStates | Do not rely on a partial/beta endpoint as the sole House vote corpus. |
| Senate roll calls | Senate LIS chamber-native vote data | Congress.gov recorded-vote links; OpenStates | Preserve official vote number, session, motion/question, tally, and member positions. |
| State/local legislation | OpenStates/OCD provider data plus jurisdiction-native evidence where available | Other reviewed sources | Promote bounded grains to owned `core`/`fact`; FDW is not the researcher contract. |

### Reconciliation rule

Canonical current-state fields may be selected from reviewed source-specific
observations, but the evidence that supports the selected value must remain
traceable. Never destroy a conflicting observation merely because another
source is preferred for that field. Derived research classifications, scores,
or model outputs belong in marts/analysis and never rewrite source facts.

## Current verified baseline

| Entity | Scope | Verified state | Evidence |
|---|---:|---:|---|
| Bills | 118th Congress | 19,315 canonical bills | Complete GovInfo BILLSTATUS reconciliation |
| Bills | 119th Congress | 18,052 canonical bills | Complete GovInfo inventory validation and BILLSTATUS reconciliation |
| People | Federal baseline | 723 people / 9,115 identifiers | OpenStates snapshot load |
| Organizations | Federal baseline | 242 organizations | OpenStates snapshot load |
| Roll calls | 118th Congress | 1,088 canonical roll calls | 1,089 source events collapse to 1,088 unique keys |
| Member votes | 118th Congress | 310,038 rows | OpenStates vote load |
| Roll calls | 119th Congress | 739 canonical roll calls | OpenStates source reconciliation; explicitly partial |

The 118th duplicate source key is `us-2024-lower-515`; it represents two source
events and is intentionally represented once by the canonical roll-call key.

## Objectives and measurable acceptance criteria

### 1. Unified congressional health check

Create one read-only command/report covering bills, people, organizations,
roll calls, member votes, ingestion runs, source coverage, unresolved identity
counts, and resume cursors.

Success criteria:

- Command exits zero against a healthy local database and writes a JSON report.
- Report includes 118th and 119th coverage state for every loaded entity.
- It distinguishes `complete`, `partial`, `running`, and `failed`; no unknown
  state is silently rendered as complete.
- It reports the expected 118th bill and roll-call reconciliation values above.
- Automated tests cover an empty table, a partial run, a failed run, and the
  documented duplicate roll-call identity.

### 2. Incremental refresh contracts

Define reviewed, disabled-by-default contracts for OpenStates, Congress.gov,
GovInfo, House Clerk, and Senate LIS refreshes. Enable only the sources whose
credentials, rate limits, source manifests, and verification rules have been
approved.

Success criteria:

- Each contract names provider, dataset, cadence, source identifiers, coverage
  policy, cursor strategy, artifact/provenance behavior, and validation gate.
- Every incremental run creates `ingest.run` evidence and is idempotent.
- A retry after an injected failure resumes from a committed cursor/page without
  duplicating canonical records.
- A scheduled dry run changes neither provider data nor canonical tables.
- A source refresh that changes bytes for the same logical remote artifact must
  create new immutable evidence rather than changing the meaning of an existing
  evidence identifier.

### 3. Identity enrichment and exception resolution

Enrich canonical people only from stable Congress.gov/BioGuide evidence and
reviewed crosswalks. Resolve historical sponsors and voters only when a stable
identifier proves the association; retain unmatched rows and an exception
report otherwise.

Success criteria:

- Every newly linked person has a stable source identifier and provenance.
- No existing identifier is reassigned by a refresh without an explicit,
  reviewed conflict-resolution migration.
- The report enumerates unresolved sponsor and voter IDs before and after each
  enrichment run, including the reason each remains unresolved.
- Tests cover a resolved identity, a missing identity, and a conflicting ID.

### 4. 119th Congress completeness policy

Keep each 119th entity explicitly partial until its approved source backfill is
downloaded, validated, reconciled, and loaded. BILLSTATUS bill coverage may be
complete while vote coverage remains partial.

Success criteria:

- All 119th ingestion runs and health reports show `partial` until promotion.
- The backfill uses the generated official manifest; no speculative URLs.
- Promotion to `complete` requires 100% manifest validation, zero malformed
  identities, reconciliation to the reviewed source set, and documented review.
- Tests reject an attempted complete status while any required source group is
  partial or missing.

### 5. Operational verification and documentation

Maintain a concise runbook with commands, expected reports, failure recovery,
and rollback boundaries for the pipeline.

Success criteria:

- Unit and integration tests run in the supported project workflow.
- A bounded smoke test and one multi-page resume test run for each loader.
- Documentation is updated in the same commit as every behavior, schema,
  contract, or workflow change.
- Each completed milestone has a focused commit with validation results.

## Execution order

1. Implement the unified health check and tests.
2. Add reviewed incremental refresh contracts and dry-run validation.
3. Implement primary-source identity enrichment and exception reporting.
4. Execute the approved 119th source backfills and only then consider promotion.
5. Add scheduling after all prior gates are green.

The next OpenStates execution phase is detailed in
[`openstates-119th-vote-refresh.md`](openstates-119th-vote-refresh.md). It
keeps the 119th vote refresh disabled until its source snapshot and dry-run
approval gates are satisfied. Epic 4 then replaces OpenStates-as-acquisition
for federal roll calls with wrapped chamber-native House/Senate evidence while
retaining OpenStates for reconciliation.

## Non-negotiable safeguards

- Provider snapshots remain read-only sources; canonical tables retain mapping
  metadata and provenance rather than replacing upstream ownership.
- No source has blanket precedence across all political fields. Source authority
  is domain/field specific and disagreements remain inspectable.
- SQL is parameterized and stored under `sql/query/` when reusable.
- Schema changes are ordered migrations.
- Long-running commands show progress, elapsed time, safe resume information,
  and actionable failure output.
- Tests are designed alongside each change and cover the applicable failure,
  idempotency, pagination/resume, provenance, source-disagreement, and migration
  paths.
