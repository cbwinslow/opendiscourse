# Runbook

## Purpose

This is the operating procedure for adding, validating, loading, refreshing,
and retiring research data. The source catalog says what we may use;
`inventory/progress.yaml` says what we are actually doing and its current
state. Update the progress item in the same change as any ingestion work.

## States

| State | Meaning | Allowed action |
|---|---|---|
| `idea` | Possible source, not scoped | Research only |
| `planned` | Contract and intended scope chosen | Obtain credentials or schedule work |
| `found` | Local files or endpoints discovered | Register metadata; do not parse as truth |
| `verify` | Authenticity/coverage review active | Compare to publisher manifests/API |
| `ready` | Scope and validation rule accepted | Ingest through a declared plan/adapter |
| `loaded` | Typed rows committed with lineage | Refresh and quality-check |
| `hold` | Sensitive, unclear, restricted, or too broad | No parsing/embedding/copying |
| `rejected` | Not suitable for the corpus | Retain the decision and reason |

## Intake

1. Add or confirm the provider/dataset contract in `inventory/sources.yaml`.
2. Create a short one-word progress ID in `inventory/progress.yaml`.
3. Record exact scope, original location/URL, claimed publisher, sensitivity,
   validation rule, and next action. Never label a legacy cache authoritative.
4. Register each candidate artifact by its original path, checksum, byte size,
   coverage, and source URL/origin note. Do not move it during intake.
5. Move the item from `found` to `verify` only when an owner is actively
   comparing it against an authoritative source.

## Verify

1. Prefer a publisher manifest, signed checksum, stable package ID, or API
   response over filenames and directory labels.
2. Check format, date/congress/vintage coverage, record count, and duplicates.
3. Quarantine corrupt, unknown, access-restricted, or mixed-sensitive files.
4. Record the validation result before parser work begins. A failed check moves
   the item to `hold` or `rejected`; it is never quietly replaced.

## Load

1. Keep raw input immutable. Parse only to `stage/`.
2. Start with a bounded sample; compare parsed counts/keys to the artifact.
3. Load idempotently into a typed target table and retain `payload_id` or
   `artifact_id` lineage on every derived record.
4. Run duplicate, null-key, coverage, and referential-integrity checks.
5. Mark an item `loaded` only after those checks pass and record the exact
   loaded scope in the progress register.

## Refresh

1. Plans in `inventory/plans.yaml` are the allow-list for scheduled work.
2. Run `research-db plan-due --dry-run`, review the list, then run
   `research-db plan-due` from a scheduler.
3. Never widen scope just because a provider offers more data. Add a reviewed
   plan or change parameters first.
4. Record provider changes, backfills, and failures in the progress item.

## Sensitive material

Mixed-origin or potentially sensitive collections remain in `hold/` and are
metadata-only until access, provenance, retention, and intended use are
approved. OCR and embeddings are derivative processing; they are prohibited
until the source passes that review.

## Weekly review

1. Run `research-db progress-list` and `research-db plan-due --dry-run`.
2. Advance only items with an explicit next action and validation result.
3. Check storage headroom and backup status before any large backfill.
4. Select one bounded source family for the following week.
