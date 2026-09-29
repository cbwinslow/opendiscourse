# Session handoff — ACS/AHS staging and dataset inventory — 2026-09-29

## Start here

Read `AGENTS.md`, `docs/PROJECT-STATE.md`, and this file. This handoff
supersedes the transfer-status portions of
`docs/SESSION-HANDOFF-2026-09-28-ACS-RECOVERY.md`; retain that older handoff
for the Census HTML-rejection investigation and fallback evidence.

## Plain status

The complete approved ACS PUMS and AHS raw archive is safely retained and is
now loading into the warehouse. Do not start a second ACS job.

- **Retained:** 3,762 usable official artifacts totaling **136,873,504,564
  bytes** (about 136.87 GB).
- **Transfer failures:** zero.
- **Running:** one managed user service,
  `od-acs-housing-archive.service`, started at 2026-09-29 10:52 UTC.
- **Observed staging progress:** 4,725,621 ACS PUMS rows at the last check;
  AHS and published-row counts were still zero because the run is in its
  staging phase.
- **Capacity at last check:** about 51 GB memory available and 1.8 TB disk
  free. The service is CPU-active; do not interrupt it merely because it is
  long-running.

## What was repaired

The first complete transfer stopped during staging on official 2005 PUMS ZIP
member `ss05pnj.csv`. Commit `23e56c7` (`fix: recognize legacy ACS PUMS
members`) recognizes the official legacy `ss` + two-digit year + `p`/`h`
member family as person/housing microdata and still rejects malformed names.
The official 2005 and 2006 New Jersey ZIP contents were checked through the
artifact registry. Verification passed:

- `uv run pytest tests/test_acs_archive.py -q`: 38 passed.
- `just check-fast`: 638 passed.

Commit `b57046f` records the recovery and restart in `docs/PROJECT-STATE.md`.

## Safe monitoring

Use these read-only checks. They must not create a second worker:

```sh
systemctl --user show od-acs-housing-archive.service \
  --property=ActiveState,SubState,MainPID,ExecMainStatus,MemoryCurrent,MemoryPeak,CPUUsageNSec \
  --no-pager

journalctl --user -u od-acs-housing-archive.service -n 30 --no-pager

uv run research-db source-status census.acs_housing_archive
```

Only after the service has exited successfully should the next session inspect
the final `stage` and `published` counts, validate release coverage and source
row counts, and decide whether a publish repair is needed. If it fails, record
the first new traceback and investigate it before any retry. Never delete or
overwrite retained artifacts.

## Work approved while staging runs

The operator approved a non-invasive dataset inventory and priority review.
It must not modify the ACS service, start another bulk transfer, launch another
heavy warehouse load, or assume a dataset is complete from an old chat.

Deliver a plain-language table covering the project-approved sources:

1. Dataset and source owner.
2. What it contributes to the public-policy research warehouse.
3. Target time coverage and product distinctions that must remain separate.
4. Actual state: loaded, raw retained/staging, ready to ingest, blocked, or
   intentionally deferred.
5. The next safe action and any external dependency.

Prioritize the separate ACS Detailed Tables delta, published ACS/AHS archive
validation, congressional completeness (including the two Congress 107
Congress.gov HTTP-500 pages), population/geography coverage, and only then
gated or unbuilt sources such as FEC. Preserve the rule that federal people
join by BioGuide and FEC/election person joins remain gated.

## Do not lose these distinctions

- ACS PUMS 1-year and 5-year are different products and must not be combined
  or used as replacements for one another.
- The ACS Detailed Tables work is separate from raw PUMS/AHS archive loading.
- AHS selected relational public-use CSVs are raw microdata; documentation
  artifacts are evidence, not data rows.
- Congress 107 is short two bills because their official detail endpoints
  return HTTP 500. This is an upstream availability problem, not evidence that
  the other Congresses failed to load.
