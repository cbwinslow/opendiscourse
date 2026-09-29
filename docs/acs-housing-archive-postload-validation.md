# ACS/AHS archive post-load validation

Use this checklist only after `od-acs-housing-archive.service` exits. It is a
read-only verification procedure; it must not start another archive worker,
delete retained files, or begin the separate ACS Detailed Tables load.

## 1. Confirm how the service ended

```sh
systemctl --user show od-acs-housing-archive.service \
  --property=ActiveState,SubState,Result,ExecMainCode,ExecMainStatus,MainPID,MemoryCurrent,MemoryPeak,CPUUsageNSec \
  --no-pager

journalctl --user -u od-acs-housing-archive.service -n 30 --no-pager
```

Success means the service is no longer running, `Result=success`,
`ExecMainCode=exited`, and `ExecMainStatus=0`. If any result differs, record
the first new traceback and investigate it before retrying. A stopped service
is not automatically a successful load.

## 2. Obtain the evidence-ledger report

```sh
uv run research-db source-status census.acs_housing_archive
```

This report is the source of truth for the approved selection, stated publisher
gaps, usable retained artifacts, failed attempts, staged rows, and published
rows. Save its complete JSON output outside the tracked checkout or attach it
to the run handoff; do not rely on a truncated terminal scrollback.

## 3. Check retained official evidence

Confirm all of the following in `artifacts`:

- `usable_artifact_count` is 3,762 and `retained_bytes` is 136,873,504,564,
  unless a documented later official selection changed the manifest.
- Interpret `failures` as attempt history, not an automatic blocker. A failed
  earlier attempt may coexist with a later usable retained version; record it
  and confirm that the logical artifact has a current usable version. An
  unresolved current failure is a blocker.
- Every `usable` group has an approved product, period, kind, and usable
  status. Documentation artifacts are evidence; selected data artifacts are
  the inputs to stage and publication.
- The report's contract preserves the stated gaps: no standard 2020 ACS
  PUMS one-year release, no pre-2005 ACS PUMS, and no 2000 AHS public-use
  release. Do not manufacture a replacement product.

## 4. Check coverage and product separation

Compare `contract.selection`, `contract.gaps`, and `artifacts.usable` with
`inventory/contracts/acs-housing-archive.yaml`:

- ACS PUMS one-year: 2005–2019 and 2021–2024.
- ACS PUMS five-year: periods 2005–2009 through 2020–2024.
- AHS: each published release, using only the selected current relational CSV
  representation for each national or metropolitan component.

PUMS one-year, PUMS five-year, and AHS remain separate products. Do not use
one to fill another product's gap.

The current status report groups artifacts by product, period, kind, and
status; it does not expose every AHS national/metropolitan component or a
per-artifact stage count. Do not certify component-level completeness from its
aggregate groups alone. Record that limitation and require a reviewed,
read-only manifest/current-artifact comparison before making that claim.

## 5. Check stage and publication separately

Use `stage.acs_pums_rows`, `stage.ahs_rows`, `published.releases`, and
`published.projection_rows` as progress signals, not completion proof: the
current aggregate counters include all dataset artifact versions. Stage is
temporary source-shaped preparation data; publication is the researcher-facing,
provenance-linked release/projection layer. Do not certify completion from a
nonzero aggregate count. Require a reviewed comparison of selected current
artifacts with their release and stage/projection evidence.

Each published release must link directly to its retained source artifact.
The project reads the newest usable artifact through `ingest.current_artifact`,
so failed or provisional bytes must never shadow verified evidence.

## 6. Decide the next action

| Finding | Safe action |
|---|---|
| Service succeeded; evidence, coverage, stage, and publication checks pass | Record final counts, run identifiers, and the component-level verification method in `docs/PROJECT-STATE.md` and `inventory/progress.yaml`; then decide whether the separate Detailed Tables delta may proceed. |
| Service succeeded but stage or publication is incomplete | Investigate the first missing product/period or traceback. Do not restart blindly or overwrite retained files. |
| Service failed | Preserve the first traceback and use the existing resume path only after the cause is understood. |
| Evidence/report does not match the approved contract | Stop. Reconcile the manifest or source contract before any promotion or new transfer. |

## 7. Regression checks after a repair

Run these only after a code or workflow repair, not merely because the loader
is still running:

```sh
uv run pytest tests/test_acs_archive.py -q
just check-fast
just check-db
```

The database gate verifies staging, publication, provenance, failure visibility,
and idempotent repeat publication. It needs a test database or testcontainers;
do not run it against the live warehouse.
