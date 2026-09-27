# Session handoff — ACS PUMS and AHS full archive — 2026-09-27

## Start here

Read `AGENTS.md`, `docs/PROJECT-STATE.md`, this file, and then
`docs/SESSION-HANDOFF-2026-09-27-ACS.md`. This file supersedes the older ACS
handoff for the housing-microdata work, but does not replace its safety rules
for the separate 2021–2024 ACS Detailed Table job.

Current branch: `main`. The committed baseline is `6a1ca78`.

## Plain status

**No AHS or PUMS archive bytes have been downloaded by the new archive
Connector.** Do not report an AHS year as downloaded. The implementation has
an official 2026-09-27 preflight manifest and is verified; the large transfer
still waits for a separate transfer approval.

The earlier 2022 ACS 5-year Detailed Table plan is recorded `loaded`, and no
`acs-bulk` process is running. Do not start its 2023 plan until the prior run's
health result is located or rerun with `uv run research-db census-health`.
That job is separate from this PUMS/AHS archive.

## What the implementation covers

- ACS PUMS 1-year: 2005–2024, excluding 2020 because Census published no
  standard 1-year release.
- ACS PUMS 5-year: 2005–2009 through 2020–2024.
- AHS: every currently published official release directory: 2001–2005,
  then each odd year through 2023. The pre-2015 odd-year releases include
  metropolitan samples as published by Census. The 2000 AHS public-use
  release is not available from Census; 2001 is the closest available release.
- Raw CSV fields are retained whole in `stage`; an initial smaller typed
  projection exists for common policy measures. Expanding typed fields must
  reuse the retained evidence rather than re-download it.
- AHS selects only the newest **relational CSV** version per national or
  metropolitan component. Superseded/flat variants remain discoverable as
  evidence but are not selected, preventing duplicate observations.

Important distinction: ACS PUMS represents deidentified people and housing
units at PUMA geography; it is not identified household data and is not
county-level. AHS is a housing-unit survey. Neither is an ACS aggregate table.

## Included implementation files

- Connector: `src/opendiscourse_research/ingestion/acs_archive.py`
- Official-directory provider: `src/opendiscourse_research/providers/census.py`
- Schema migration: `migrations/versions/f6b2a7c4d913_housing_microdata_archive.py`
- Models: `src/opendiscourse_research/models/core.py` and `models/stage.py`
- Source contract: `inventory/contracts/acs-housing-archive.yaml`
- Field policy: `inventory/fields/census.acs_housing_archive.yaml`
- Operator guide: `docs/acs-housing-archive.md`
- Tests: `tests/test_acs_archive.py`, plus current-Alembic-head expectation
  updates in existing database tests.

The implementation artifact at
`_bmad-output/implementation-artifacts/spec-full-policy-relevant-acs-archive.md`
is ignored by Git and was force-intent-added for review. It records the
approved scope. Do not mark transfer tasks complete until the bytes are
actually retained, staged, validated, and published.

## Verified

- `just check-fast`: **614 passed**.
- `just check-db`: **383 passed, 619 deselected** (7m44s).
- `git diff --check`: passed.
- Official preflight: **3,762 selected artifacts**, **136,860,756,606**
  download bytes, **586,386,830,521** peak required bytes, and
  **2,134,320,922,624** bytes free. No unknown sizes.

## Safe next steps

1. Rerun discovery and capacity planning if a fresh manifest is needed:

   ```sh
   uv run python -m opendiscourse_research.ingestion.acs_archive \
     --all-official-indexes
   ```

   This reads official Census directory listings and file sizes. Unknown file
   sizes fail the plan rather than being guessed.
2. Review the resulting exact byte total and available `DATA_ROOT` capacity.
   The 2026-09-27 manifest is authoritative only as a snapshot; rerun it
   before approving a later transfer.
3. Only after the operator explicitly approves that exact manifest, rerun with
   `--approve-transfer`. This is the command that can download and retain raw
   evidence under `DATA_ROOT`.
4. Let the Connector stage, validate, and publish all selected artifacts.
   Never delete or overwrite retained raw evidence to retry an error.
5. Update `docs/PROJECT-STATE.md` with actual acquired years, manifest totals,
   and validation counts. Then run review and make a focused commit.

## Do not do

- Do not start the PUMS/AHS transfer merely because the code is present.
- Do not claim any AHS/PUMS years are loaded before the Connector completes.
- Do not substitute ACS 5-year estimates by averaging annual ACS 1-year
  estimates. A five-year change compares two comparable five-year estimates
  five years apart.
- Do not start the 2023 ACS Detailed Table plan until the 2022 health check is
  confirmed.
