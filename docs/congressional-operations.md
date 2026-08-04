# Congressional operations runbook

## Health and reconciliation

Run `research-db congress-health` before a refresh. It writes the source-aware
report under `meta/health/congressional.json`. Review `status`, `failed_runs`,
`recovered_runs`, and `stale_runs` before treating a refresh as healthy. A
recovered run is retained as operational evidence and produces `attention`, not
an active `failed` state.

Run `research-db reconcile-openstates-votes --congress 118` to verify the
documented 1,089 source events and 1,088 stable roll-call identifiers. The
duplicate key `us-2024-lower-515` is expected. Run the same command for the
119th Congress; its coverage remains partial.

If an abandoned congressional run is older than six hours, run
`research-db recover-stale-congress-runs`. It changes only old `running` runs
for congressional datasets to `failed`, with an explicit recovery reason.

## Bounded loading and recovery

Use `research-db load-openstates-votes --congress 118 --limit 25` for a
bounded smoke or repair batch. The loader uses committed keyset pages and is
idempotent. For the current Congress, use the same command with `--congress
119`; every resulting run is explicitly `partial`.

After a failed or deliberately bounded vote batch, rerun with `--resume` to
continue after the last committed `ocd_id`. The result prints the exact resume
command and preserves the checkpoint with its source artifact and ingestion-run
lineage. Do not use `--resume` after the source snapshot has changed; validate
and stage the new snapshot first.

Run `research-db load-billstatus --congress 118` or `--congress 119` only
against a validated complete local archive. The loader records artifact lineage
and resumes by skipping already-loaded archives and XML members.

## OpenStates vote refresh planning

Run `research-db plan-openstates-vote-refresh` before requesting an OpenStates
snapshot refresh. It opens a read-only database transaction, writes
`meta/plan/openstates/openstatesvotes-dry-run.json`, and records source and
canonical vote counts, source watermarks, storage reserve, and approval gates.
It does not contact OpenStates, alter the source FDW, write canonical tables,
or create an `ingest.run` record.

An `approval_required` result is expected while the `openstatesvotes` contract
is disabled. Review the report and the detailed refresh plan before approving
snapshot acquisition; source-to-canonical equality does not by itself prove
that the current Congress is complete.

The existing `research-db bootstrap openstates-dump --data` command now enforces
the same gate: it refuses data-dump download until `openstatesvotes` is enabled
with `approval: approved_snapshot_acquisition`. Schema-only downloads remain
read-only provider artifacts, but they do not authorize a vote refresh.

After an approved data dump exists, copy
`plans/templates/openstates-snapshot-manifest.yaml` to the review location,
fill it with the exact artifact path, bytes, and SHA-256, then run
`research-db validate-openstates-snapshot --manifest <path>`. This inspects the
pg_dump directory only; it does not restore, register, or map the snapshot.

## Identity exceptions

Run the unresolved-identity report before enrichment. Resolve an identifier
only through a stable primary-source key. The Congress.gov member adapter is
the approved path for BioGuide exceptions; it stores the API payload and then
re-resolves related sponsorships. Do not use name matching.

## 119th GovInfo promotion gate

The 119th BILLSTATUS promotion completed on 2026-08-04: all eight archives
match GovInfo's official inventory, and reconciliation found 18,052 canonical
bill matches with zero missing or malformed XML members. Future refreshes still
require all of the following gates:

1. Official missing-file manifest and capacity preview.
2. Downloaded files validated against the official listing.
3. Zero malformed identities and reconciliation to the OpenStates baseline.
4. Explicit approval to change coverage from `partial` to `complete`.
