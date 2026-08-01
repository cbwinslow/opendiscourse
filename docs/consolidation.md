# Consolidation

## Decision

`/home/cbwinslow/workspace/opendiscourse` is the single active project root.
`/home/cbwinslow/workspace/government` is a read-only migration source until
each useful component has been reviewed, adopted, tested, and recorded here.
No bulk move or deletion is allowed during consolidation.

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
2. Add read-only FDW/mapping access from `opendiscourse` to `openstates`.
3. Adapt GovInfo BILLSTATUS ingestion using the official bulk directory and
   OCD bill/action/sponsorship/document targets.
4. Add Congress.gov member enrichment using Bioguide IDs.
5. Add the official vote adapters.
