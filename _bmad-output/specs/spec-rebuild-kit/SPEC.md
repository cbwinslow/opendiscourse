---
id: SPEC-rebuild-kit
companions:
  - source-matrix.md
sources: []
---

> **Canonical contract.** This SPEC and the files in `companions:` are the complete, preservation-validated contract for what to build, test, and validate. Source documents listed in frontmatter are for traceability.

# OpenDiscourse rebuild kit

## Why

A mandate and an opportunity. The operator will drop the rebuildable `stage`
duplicates (about 37 GB: `stage.cbp_row` 22, `stage.tiger_feature` 10,
`stage.acs_bulk_row` 5) and keep one small database backup only if everything
loaded can be rebuilt from raw files, and the project's goal is that anyone can
bootstrap the same warehouse on their own machine. Today each source has its own
command chain, the Census selection lives in gitignored lake files, FEC has no
downloader (its 50 archives are registered under a legacy `/mnt/storage` path),
and nothing proves a rebuild works.

## Capabilities

- **CAP-1**
  - **intent:** An operator can take an empty `DATA_ROOT` and empty database to the loaded state of every v1 source with one documented, ordered, resumable, idempotent command sequence (download, then inventory, then ingest).
  - **success:** On a scratch root, a bounded run completes each source's stages in order; interrupting and rerunning finishes without re-downloading verified files or duplicating rows.

- **CAP-2**
  - **intent:** The scope of a rebuild (sources, Census tables, geographies and years, Congresses, FEC families and cycles) is declared in tracked configuration.
  - **success:** Deleting `<lake>/meta` and the checkout's untracked files changes nothing about what a rebuild selects.

- **CAP-3**
  - **intent:** A verify step proves a rebuild by comparing per-source row counts and artifact checksums with the run ledger, the coverage report and official manifests.
  - **success:** It exits non-zero and names the source when any count, checksum or manifest entry differs; it exits zero on a correct rebuild.

- **CAP-4**
  - **intent:** `stage` and derived `fact` data can be dropped and re-created from retained raw files.
  - **success:** On one real loaded dataset, dropping its staged rows and rebuilding restores identical row counts and content hashes, and only then are the about 37 GB of `stage` duplicates dropped on the live warehouse.

- **CAP-5**
  - **intent:** An agent starting cold finds and follows the rebuild through a small project skill `opendiscourse-rebuild`.
  - **success:** The skill names the command sequence, the rules above and the verify step, and contains no logic that the commands do not.

## Constraints

- Every source is downloaded from its original government endpoint into the user's `DATA_ROOT`; no loader, default or inventory entry reads `/mnt/storage` or any machine-specific path. FEC (50 archives, 20 GB) and 16 BILLSTATUS rows are registered under `/mnt/storage` today and no FEC downloader exists, so FEC cannot be claimed until one does; building that downloader is part of this kit's last phase.
- New sources are Connectors. The kit orchestrates existing commands and Connectors and adds no `if/elif` to `cli.py`, `plans.py` or `registry.sync`. Census families still use plan/preview/approve/download/stage/load; migrating them is a separate story.
- Raw artifacts are never deleted or overwritten; a rebuild reuses retained files whose checksum matches and downloads only what is missing or changed. Wiping derived rows is allowed and recorded in the run ledger.
- Acceptance runs on a scratch `DATA_ROOT` and a throwaway database, never the live lake or warehouse.
- Politician-keyed rows stay behind `identitygate.require_person_join`; no FEC-to-person joins, elections or crime (Epic 7 is not v1).
- Downloads are polite, API keys come from `.env` only, and each source passes the capacity gate with a written size estimate before it downloads.

## Non-goals

- No new data sources, schema changes, scorecards, NLP or embeddings.
- No redesign of the Connector, the run ledger or the load strategies (ADR-0003).
- No backup tooling: `scripts/ops/backup_opendiscourse.sh` and the restore drill stay as built.
- No renaming of retained raw files and no rewrite of the loaded Census, CBP, TIGER, PEP or DHC data without cause.
- No off-machine copy and no scheduler; scheduling stays the operator's choice.

## Success signal

A person who has only a clone, a PostgreSQL 17 server and an API key file runs the
kit against an empty folder and ends with a warehouse whose `research-db loaded`
and `coverage` output, and the verify step, match the operator's; and the operator
drops the `stage` duplicates knowing they can be re-created.

## Assumptions

- "Every loaded source" means the datasets in `source-matrix.md`; BLS, FRED and Treasury series are small, already re-runnable through plans, and optional steps.
- The Census selection now lives in gitignored `<lake>/meta/bulk-plans/*.yaml` (about 30 files, up to 150 KB each) and moves into tracked configuration.
- Acceptance uses PostgreSQL through testcontainers or `OPENDISCOURSE_TEST_DATABASE_URL`, as the DB tests do, on a bounded slice (one Congress, one ACS year, one TIGER layer). The full rebuild is an operator-run command.
- OpenStates follows AD-8: the monthly dump is restored read-only into database `openstates` and promoted through the FDW into `core`/`fact` (people, organizations, votes). Creating the database and FDW needs a superuser once; the kit documents that step and does the rest as the application role.
- FEC is the last phase: the kit ships without it if needed, but is not complete until FEC downloads from its origin into `DATA_ROOT`.

## Open Questions

- FEC layout: `stage.fec_row` (74 GB) is not among the about 37 GB of droppable duplicates, and its compact layout and partitioning (ADR-0003) are undecided. Does the FEC downloader land into the current layout first, or wait for that decision?
