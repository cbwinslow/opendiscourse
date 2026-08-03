# Lake

## Storage policy

Use `/home/cbwinslow/workspace/data-lake/opendiscourse` for all new project
data. It is on the 2.9 TiB workspace filesystem (about 2.5 TiB free at the
initial audit). The existing `/mnt/storage` filesystem has only about 596 GiB
free and must not receive new large backfills.

```
/home/cbwinslow/workspace/data-lake/opendiscourse/
  raw/        immutable downloads, arranged by source/dataset/period
  stage/      disposable parser output
  curate/     optional parquet exports and reproducible marts
  pg17/       bare-metal PostgreSQL 17 tablespace; do not manually edit
  postgres/   optional Docker development database; do not manually edit
  quarantine/ artifacts with unknown origin, failed checks, or access limits
```

`raw/` is append-only. `stage/` can be removed and rebuilt. No parser may
overwrite a raw artifact. Every raw object needs an `ingest.artifact` row with
its original path, URL or origin note, checksum, coverage, and status.

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
2. Register a legacy file in `ingest.artifact` by path and checksum; do not
   relocate it merely to make it fit the new layout.
3. Compare its identifier/checksum/coverage to the official provider when
   possible. Quarantine failures or unknowns.
4. Parse into typed tables only after that validation; retain the artifact ID
   as lineage.
5. Only copy verified, actively used source artifacts into the new `raw/`
   layout. Use a content-addressed path to avoid duplicates.

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
