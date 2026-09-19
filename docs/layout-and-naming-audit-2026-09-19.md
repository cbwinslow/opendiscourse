# Folder and naming audit (2026-09-19)

Scope: repository layout, the data lake (`DATA_ROOT` and its siblings), artifact
names, `research-db` command names, module names and docs, checked against
`docs/conventions.md`, `docs/lake.md` and `AGENTS.md`. Read-only measurement, then
one small fix PR. Nothing under the lake was moved or deleted.

Statuses: **fixed** in this PR; **decision** needs the operator; **debt** real but
tracked elsewhere or out of scope for a small PR.

## What already conforms

- Raw folders follow the dataset id: `catalog.dataset.dataset_id` `a.b_c` is
  `<DATA_ROOT>/a/b_c/[period]/` for every loaded dataset (`census/acs_5_bulk/2023`,
  `congress/govinfo_billstatus/118`, `fec/campaign_finance`, `openstates/dump`).
- Retained downloads are content-addressed: `<stem>.<sha256>.<ext>`.
- Every registered path exists on disk (0 of 2,585 `DATA_ROOT` rows are dangling).
- Alembic revision, SQL bootstrap, test and `providers/`, `repositories/`, `models/`
  names are consistent; `providers/` is HTTP only, `repositories/` SQL only.
- Only `main` (plus dependency-bot branches and `wip/lake-registry-homelab`) remains.

## Findings

| # | Drift | Evidence | Status |
|---|---|---|---|
| 1 | **Tests wrote fixture files into the operator's real lake.** 109 tiny unregistered files (16 FEC stubs of 160 bytes, `pas2`/`indiv` stubs, 16 `matrix.*.xlsx`, 29 TIGER, 17 CBP, 3 ACS, 3 PEP, dhc stubs) sit beside real evidence in `raw/`. No `conftest` isolated `DATA_ROOT`, so `.env` was inherited. | Running the suite against a scratch `DATA_ROOT` reproduces the same content-addressed names (for example `indiv-2022.32d94937…zip`) that exist in the real lake. Running the affected tests once against the real `DATA_ROOT` (to confirm the cause) added 5 more (`indiv24`, `state`, `matrix`, `cbp`, `dhc`, created within the last two hours): the 109 include them, and it is why the fix matters. | **fixed** (autouse fixture and guard test); the 109 existing files: **decision** (proposal below) |
| 2 | **A second, stray lake inside the checkout.** `./data-lake/opendiscourse/` (366 files, 12 MB) and `./data/` (OpenStates schema dump) came from runs with the default `DATA_ROOT`. Two `congress.legislators` registry rows point into it, not into `DATA_ROOT`. Gitignored, so harmless to git. | `ingest.artifact.local_path` for `legislators-*.yaml`; identical copies (same sha256) exist in `DATA_ROOT`. | **decision**: repoint the two rows to the `DATA_ROOT` copies, then remove the stray tree |
| 3 | **`lake.md` described a layout the lake does not have.** It said `quarantine/` and gave `/home/cbwinslow/...` as the storage policy. The lake has `hold/` and `meta/` (reports, plans, health, coverage, drafts; `meta/` is where the code writes) and `docs/runbook.md` already says `hold`. The code derives every report path as `DATA_ROOT.parent/meta`, which is why `DATA_ROOT` must end in `/raw`; that rule was written nowhere. | `lake.md`, `runbook.md`, `ls <lake>`, `grep DATA_ROOT src` | **fixed** (`lake.md` rewritten) |
| 4 | **No written naming rules.** Nothing said how datasets, raw folders, artifacts, commands and modules are named. | `conventions.md` had none | **fixed** (new "Names" section in `conventions.md`) |
| 5 | **Two artifact naming schemes coexist.** Content-addressed `<stem>.<sha256>.<ext>` (BILLSTATUS, FEC, TIGER, DHC, legislators) and raw upstream names (`acsdt5y2023-b01001.dat`, `cbp22co.zip`, `co-est2025-alldata.csv`, `us2020.dhc.zip`). Both are registered and checksummed, so lineage holds. | `ls raw/census/*` | **debt**: rule now written (registry checksum is the identity, name is a label); no rename, because renaming retained files is forbidden |
| 6 | **Legacy machine paths in the registry.** 50 `fec.campaign_finance` rows (20 GB, the only copy of FEC) and 16 BILLSTATUS rows point at `/mnt/storage/data-lake/government/...`. Code and inventory keep the same paths: `fec_bulk.py:143`, `audit.py`, `legvalidate.py:21`, `inventory/progress.yaml`, `inventory/contracts/fecbulk.yaml`. This breaks the `AGENTS.md` rule that no loader may read a machine-specific path, and it means **FEC cannot be rebuilt from an empty `DATA_ROOT` today**. | `select … where local_path like '/mnt/storage/%'` → 66 rows | **debt** (already "Known debt"/4b in `PROJECT-STATE.md`); the rebuild kit must close it for FEC |
| 7 | **6 real downloads are not in the registry.** 4 ACS `Table_Shells.txt` (22 MB) and the 2 legislators files (see 2). | disk vs `ingest.artifact` | **debt**: register in the rebuild kit; do not hand-edit |
| 8 | **96 `*.zip.lock` sidecars** remain in `raw/congress/govinfo_billstatus/` (`ingestion/bulk.py:89` opens `<target>.lock` and never removes it). Noise for any copy of `DATA_ROOT`. | `find raw -name '*.lock'` | **debt**: delete on release in `bulk.py` (code change, own PR) |
| 9 | **Command names mix verbs.** `sync` (metadata), `sync-billstatus` (download + load), `load-*` (load only), `backfill-billstatus`, `plan`/`plan-run`/`plan-due`/`plan-list`, `validate`/`validate-openstates-*`, plus 95 commands in all, 68 of them hidden. The intended `research-db update` in `data-acquisition-plan.md` does not exist yet. | `research-db --help`, `cli.py` | **debt**: the rebuild kit adds one ordered entry point; renaming waits for it. `data-acquisition-plan.md` now says "planned". |
| 10 | **Module names mix styles.** `censushealth`, `legload`, `legvalidate`, `legreconcile`, `openstatesstage` (words run together) against `artifact_storage`, `acs_bulk`, `billstatus_record`. Old fixed-path loaders (`leg*`, `audit`, `govbackfill`) predate Connectors. | `ls src/opendiscourse_research` | **debt**: new modules use snake_case; rename only when a module is replaced (4b) |
| 11 | **Top-level clutter and near-duplicates.** `ops/` (systemd, census script) and `scripts/ops/` (backup, restore, tuning); `plans/` (operation notes and a manifest template) beside `inventory/plans.yaml`; `docs/superpowers/` (Aug 2026 onboarding design) beside `docs/`; `dbt/` with `dbt/logs` and `dbt/target` generated. | `git ls-files` | **debt**: merge `ops/` into `scripts/ops/` and fold `plans/` into `docs/` in a later tidy; nothing depends on it now |
| 12 | **Three tracked copies of every skill.** `.agents/`, `.agent/` and `.claude/` are byte-identical (about 970 files each, 2,875 in all); `.agent/` is the Antigravity launcher and this project does not delegate to Antigravity. | `diff -rq`, `git ls-files` | **decision**: keep `.agents` and `.claude`, untrack `.agent`? (the `.gitignore` comment says the installer regenerates them) |
| 13 | **Docs**: 25 files in `docs/` with no index; dated names for reports only partly (`performance-audit-2026-09-19`, `data-inventory-2026-09-19`). `docs/data-inventory-2026-09-19.md` is untracked (written by an earlier session; not touched here). | `git status`, `ls docs` | **decision**: commit or drop the inventory file; an index is a later chore |
| 14 | **`OD_LAKE_ROOT` and `DATA_ROOT` are two settings for one tree.** Compose reads only `OD_LAKE_ROOT`; the CLI reads only `DATA_ROOT`. `.env.example` defaults them consistently, but nothing enforces it. | `compose.yaml`, `config.py` | **debt** |

## Fixes in this PR

- `tests/conftest.py`: autouse fixture points `settings.data_root` at a scratch
  folder for every test; `tests/test_data_root_isolation.py` guards it. The
  real-corpus BILLSTATUS test still reads the real lake (its module fixture
  runs before the autouse one) and is read-only.
- `docs/lake.md`: layout and naming rewritten to match the lake and the code.
- `docs/conventions.md`: new "Names" section.
- `docs/data-acquisition-plan.md`: `update` marked planned.
- `docs/PROJECT-STATE.md`: step 0 done, links here.

## Proposal for finding 1 (needs a yes)

Move the 109 fixture files (all unregistered, all under 5 KB, all created by the
test suite) from `raw/` to `<lake>/hold/test-fixture-strays-2026-09-19/`,
preserving their relative paths, and write the list to the run ledger notes. No
bytes are deleted or rewritten; a move is reversible. They were left in place
here because `AGENTS.md` treats files under `raw/` as evidence until the
operator says otherwise.
