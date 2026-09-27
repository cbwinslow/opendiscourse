# Session handoff — ACS comprehensive delta — 2026-09-27

## Start here

Read `AGENTS.md`, `docs/PROJECT-STATE.md`, this file, and
`_bmad-output/specs/spec-source-completion/completion-matrix.md`.

The current branch is `main`, clean at `964cc70` before this handoff is
committed. Do not switch branches or start a second ACS job.

## Running now

The approved 2022 ACS comprehensive-delta plan is **loading** on port 5434.
It was started from this checkout with six workers:

```sh
ops/census-bulk-refresh.sh acs-bulk \
  /home/cbwinslow/workspace/data-lake/opendiscourse/meta/bulk-plans/acs5-comprehensive-delta2022.yaml \
  --workers 6
```

The parent shell PID is `1557893`; the active command is
`research-db ingest acs-bulk-load`. Quitting this chat does not stop it. Check
it with:

```sh
pgrep -fa 'census-bulk-refresh|acs-bulk-stage|acs-bulk-load'
rg -m1 '^state:' /home/cbwinslow/workspace/data-lake/opendiscourse/meta/bulk-plans/acs5-comprehensive-delta2022.yaml
```

At handoff time: 2021 is `loaded`, 2022 is `staged` and actively loading,
2023 and 2024 are `downloaded`. The plan file moves to `loaded` only after the
load completes; the script then runs `research-db census-health` itself.

## Safe resume order

1. Wait for the 2022 process to exit. Do not launch a replacement while its
   PID exists.
2. Confirm the 2022 plan says `state: loaded`; inspect the script result and
   run `uv run research-db census-health` if the script did not reach it.
3. Run 2023 with the same command, changing only the plan year. Wait for it to
   finish and pass health before starting 2024.
4. Run 2024 the same way, then run a final Census health check and record the
   resulting plan states/counts in `docs/PROJECT-STATE.md` and
   `inventory/progress.yaml`.
5. Commit and push only the documentation/tracker update. The plan files and
   retained data live under `DATA_ROOT`, not in this repository.

If a plan stops, do not delete or overwrite retained files. Re-run that exact
same plan command: the refresh script resumes from its recorded plan state.

## Scope and safety boundary

This is the approved ACS 5-year Detailed Table expansion for 2021–2024. It
adds the full B25 housing family plus B10, B13, B26, and B29, at state and
county geography. The source contract is
`inventory/contracts/acscomprehensive.yaml`. It is not a new download, a
schema change, or authorization to broaden the source scope.

There is about 2 TB free on the workspace volume. `research-db census-health`
was slow enough to exceed a 30-second interactive wait before the job began;
that is not evidence of failure. Let the command finish or check its process
state before diagnosing it.

## Completed earlier this session

- Merged PR #96: narrow Congress.gov recovery for five publisher HTTP 500
  failures. H.R. 2842 and H.R. 2843 are now partial official rows; the three
  unavailable cosponsor pages remain explicit retry failures.
- Verified the live Marlin Stutzman person merge: all four committee seats
  point to the survivor and retain BioGuide `S001188`.
- Latest commits before this handoff: `964cc70`, `19394be`, `9af5383`, and
  merged PR commit `5084c61`.

## Not next

Do not re-run the full 106–107 Congress.gov bill sync. Retry only the five
named endpoints with `research-db recover-congress-bills` when Congress.gov
repairs them. Do not start FEC, OpenStates, or a new ACS family during this
ACS delta run.
