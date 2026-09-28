# Session handoff — ACS PUMS and AHS archive recovery — 2026-09-28

## Start here

Read `AGENTS.md`, `docs/PROJECT-STATE.md`, and this file. This handoff
supersedes the transfer-status portions of
`docs/SESSION-HANDOFF-2026-09-27-ACS-HOUSING.md`. The separate 2021–2024 ACS
Detailed Table work is unchanged and must remain separate.

Current merged baseline: `c9f4239` (`Add reliable source lifecycle (#98)`).

## Plain status

The ACS PUMS/AHS archive transfer stopped safely after a temporary Census HTML
rejection page. It is not running now.

- **Retained:** 2,277 usable official artifacts, totaling **56,781,189,429
  bytes** (about 56.8 GB).
- **Failed:** one 2013 five-year PUMS ZIP (`csv_pdc.zip`) returned an HTML
  rejection page instead of a ZIP.
- **Not yet started:** staging, validation, and publishing. The corresponding
  database row counts are therefore zero.
- **Disk:** there is ample free capacity; do not delete retained raw files or
  the transfer lock to retry.

This was not a Census API-key or rate-limit problem. It was an intermittent
bulk-download rejection from the Census web server.

## What changed and is merged

Pull request #98 added safe recovery and visibility:

- The transfer retries temporary network, timeout, rate-limit, server, and
  HTML-rejection failures three times before considering a fallback.
- The only fallback is the separately published official Census 2013 five-year
  PUMS path. It is accepted only when it is still on `www2.census.gov`, reports
  the expected byte count, returns a binary response, and the finished download
  has the exact expected size.
- A partial primary download is discarded before a fallback begins, so bytes
  from two endpoints cannot be mixed.
- `uv run research-db source-status census.acs_housing_archive` gives a
  read-only summary of approved coverage, retained bytes, failures, stage
  counts, and published counts. It is intentionally concise; the database
  artifact ledger retains per-file detail.

## Safe next step

First inspect the current state:

```sh
uv run research-db source-status census.acs_housing_archive
```

Then, only after reviewing a fresh official capacity manifest and confirming
the transfer, resume with:

```sh
uv run python -m opendiscourse_research.ingestion.acs_archive \
  --all-official-indexes --approve-transfer
```

The command reuses the 2,277 retained artifacts. It retries the one failed
file, uses the verified legacy Census path only if needed, and does not
overwrite retained evidence. Do not run two copies at once.

## Verification already completed

- `just check-fast`: **624 passed**.
- `just check-db`: **384 passed, 631 deselected**.
- GitHub PR #98: fast tests, full tests, security, formatting, and commit
  checks passed before merge.

