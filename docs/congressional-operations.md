# Congressional operations runbook

## Health and reconciliation

Run `research-db congress-health` before a refresh. It writes the source-aware
report under `meta/health/congressional.json`. Review `status`, `failed_runs`,
and `stale_runs` before treating a refresh as healthy.

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

Run `research-db load-billstatus --congress 118` or `--congress 119` only
against a validated complete local archive. The loader records artifact lineage
and resumes by skipping already-loaded archives and XML members.

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
