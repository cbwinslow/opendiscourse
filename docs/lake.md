# Lake

## Storage policy

The lake is one folder tree, `<lake>`, chosen by the operator and placed on a large
volume (never the root disk, which is small and holds the WAL). `DATA_ROOT` is
`<lake>/raw`: the code writes every report, plan and health file to the sibling
`<DATA_ROOT>/../meta`, so **`DATA_ROOT` must end in `/raw`**. A clean clone defaults to
`./data-lake/opendiscourse/raw` (gitignored) so it works with no edits; real
deployments set `DATA_ROOT` (and `OD_LAKE_ROOT` for Compose) to spacious, backed-up
storage. On the operator's server `<lake>` is
`/home/cbwinslow/workspace/data-lake/opendiscourse`; that is a fact about one
machine, not something code or defaults may assume. The older `/mnt/storage`
filesystem has little free space and must not receive new large backfills.

```
<lake>/
  raw/        immutable downloads, arranged by dataset id and period (DATA_ROOT)
  meta/       reports the tool writes: audit, validate, plan, health, coverage,
              load, drafts, exceptions, bulk-plans (regenerable, small)
  stage/      disposable parser output
  curate/     optional parquet exports and reproducible marts
  hold/       artifacts with unknown origin, failed checks, or access limits
  pg17/       bare-metal PostgreSQL 17 tablespace; do not manually edit
  postgres/   optional Docker development database; do not manually edit
```

`raw/` is append-only. `stage/` can be removed and rebuilt. No parser may
overwrite a raw artifact. Every raw object needs an `ingest.artifact` row with
its original path, URL or origin note, checksum, coverage, and status. Tests never
touch the real lake: `tests/conftest.py` points `DATA_ROOT` at a scratch folder.

### Names

- **Raw folder** = the catalog dataset id with the dot as a slash, then the period
  when the source has one: dataset `census.acs_5_bulk` is `raw/census/acs_5_bulk/2023/`.
  Dataset ids are lowercase `provider.name` with underscores, and are the same key in
  `inventory/sources.yaml`, `catalog.dataset` and `ingest.artifact.dataset_id`.
- **File** = `<stem>.<sha256>.<ext>` when the tool retains a download itself
  (`BILLSTATUS-118-hr.<sha256>.zip`). Some Census loaders keep the publisher's own
  file name (`cbp22co.zip`). Either way the registry row (`artifact_key`, checksum)
  is the identity, the file name is only a label, and a retained file is never
  renamed, overwritten or deleted.
- **Scratch beside the file** (`*.lock`, partial downloads) is not evidence and is
  never registered.

## Existing lake audit

The legacy lake is at `/mnt/storage/data-lake/government` and should be treated
as an external read-only source until each collection is cataloged:

| Collection | Audit result | Treatment |
|---|---:|---|
| `epstein/` | ~794k files, ~658 GiB | Do not copy. Keep isolated; catalog provenance and access rules before any parsing. |
| `epstein-meta/` | ~68k files, ~7.3 GiB | Metadata/tooling only; not evidence by itself. |
| `epstein/raw-files/congress` | 24 JSON chunks for 118th Congress | Verify against Congress.gov, then register as a cache/backfill candidate. |
| `epstein/raw-files/govinfo_bulk` | 289 ZIP, 250 XML, 329 JSON; ~5.5 GiB | Verify package IDs/checksums against GovInfo, then parse into bill documents. |
| `fec_bulk_data/` | 50 official-style ZIP archives, ~19.7 GiB | Register as immutable FEC artifacts; parse one file family at a time. |
| `ledgers/` | GovInfo/Congress/OpenStates ledgers plus SQLite | Use for discovery/provenance comparison, not as truth without validation. |

The name of a directory must never become a claim about its contents. In
particular, files under `epstein/` may contain public government downloads,
research artifacts, or sensitive material. Keep those categories separate and
never make entity assertions from a filename, OCR result, or model output.

## Admission process

1. Add a source contract and identify the original authoritative publisher.
2. Preserve the legacy file in place. Before a new checksummed byte-artifact
   registration, copy and verify its bytes at a checksum-specific retained
   path; register that retained path. Existing legacy catalog rows remain
   historical, unverified records until separately audited.
3. Compare its identifier/checksum/coverage to the official provider when
   possible. Quarantine failures or unknowns.
4. Parse into typed tables only after that validation; retain the artifact ID
   as lineage.
5. Only copy verified, actively used source artifacts into the new `raw/`
   layout. Use a content-addressed path to avoid duplicates. A changed refresh
   creates a new artifact version; it never replaces completed evidence. A
   failed refresh records a provisional version that a verified retry may
   promote. Virtual and checksum-less source references remain supported.

## Legislative inventory

Run `research-db audit` before planning any Congressional or GovInfo backfill.
It is read-only: it inventories the known legacy roots, records paths, sizes,
formats, inferred coverage, and optional checksums, and writes a report under
`meta/audit/leg/latest.json`, plus a compact `summary.json` consumed by the
Congress/GovInfo browser catalog. It never copies, parses, registers, or deletes a
source artifact. Use `research-db audit --hashes` when a full checksum pass is
needed before admitting a selected legacy artifact.

Run `research-db validate billstatus` after the inventory. It validates every
available BILLSTATUS listing/ZIP pair and samples parseable XML bill identities
without changing the cache or loading PostgreSQL records. Its report is written
under `meta/validate/billstatus/latest.json` and is required evidence before a
future BILLSTATUS ingestion contract can be enabled.
Use `research-db validate billstatus --official --congress 119` to compare one
bounded Congress against live GovInfo listing manifests. It performs no file or
database writes beyond the project validation report.
Use `research-db validate billstatus --official --all` for the complete local
coverage range; it is paced and may take several minutes.

For a validated incomplete collection, run `research-db plan billstatus
--congress 119`. It creates an exact official missing-file manifest and a
capacity preview under `meta/plan/govinfo/`; the version-controlled `billstatus`
contract remains disabled and no file is downloaded.

After a complete validation and reconciliation, load one bounded batch with
`research-db load-billstatus --congress 118 --limit 100`. The loader commits
at `--batch-size` boundaries, records an `ingest.run` with coverage, and skips
already loaded archives and XML members, so rerunning safely resumes a stopped
load. The 119th Congress
requires `--allow-partial`; its results remain explicitly partial until the
approved missing-file backfill is validated and loaded.

Use `research-db load-openstates-people` to seed canonical federal people from
the provisioned read-only OpenStates snapshot. People are keyed by their OCD
identifier and retain baseline metadata; conflicting external identifiers are
reported rather than reassigned. Congress.gov should enrich this baseline.

Federal vote events use the same read-only OpenStates snapshot. Start with
`research-db load-openstates-votes --congress 118 --limit 1` and reconcile with
`research-db reconcile-openstates-votes --congress 118`. The 118th source has
1,089 events but 1,088 stable roll-call identifiers; the reconciliation report
records the single duplicate. Loads for the 119th Congress are explicitly
recorded as partial coverage.
