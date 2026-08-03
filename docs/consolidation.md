# Consolidation

## Decision

`/home/cbwinslow/workspace/opendiscourse` is the single active project root.
`/home/cbwinslow/workspace/government` is a read-only migration source until
each useful component has been reviewed, adopted, tested, and recorded here.
No bulk move or deletion is allowed during consolidation.

OpenStates is the legislative interoperability baseline. Its restored Django /
Open Civic Data schema remains an immutable upstream snapshot; it is not the
target for Congress.gov or GovInfo writes. OpenDiscourse owns the canonical
federal records, source lineage, and reconciliation mappings. A read-only
database mapping and compatibility views provide one query surface without
co-mingling provider ownership.

## What to retain from government

| Asset | Action |
|---|---|
| OpenStates dump and upstream monorepo | Use as provider snapshot/reference; preserve original source and version |
| GovInfo/Congress scripts | Review and extract only proven adapter logic into this project's adapters |
| GovInfo BILLSTATUS schemas/guides | Vendor or pin as parser reference with source/version metadata |
| Existing local ledgers | Treat as discovery metadata; validate before promoting artifacts |
| Duplicate experiments/caches | Leave untouched until replacement coverage and backups are confirmed |

## Migration procedure

1. Inventory one component and state its owner, source, data scope, license,
   dependencies, and current test/operational status.
2. Add its dataset contract and OCD mapping in this project.
3. Port or vendor the smallest useful code path; do not copy whole projects.
4. Run it against a bounded official sample in `opendiscourse`.
5. Record the result in `inventory/progress.yaml`.
6. After a complete verified replacement, mark the original as archived. Delete
   only under an explicit later cleanup decision.

## First migration slice

1. Finish and validate the isolated OpenStates restore.
2. Provision the least-privilege read-only FDW access described in
   `docs/openstates-integration.md`.
3. Add compatibility views and mappings from the OpenStates entity shapes to
   OpenDiscourse's owned canonical entities.
4. Adapt GovInfo BILLSTATUS ingestion using the official bulk directory and
   OCD bill/action/sponsorship/document targets.
5. Add Congress.gov member enrichment using Bioguide IDs.
6. Add the official vote adapters.
