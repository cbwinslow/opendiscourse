# Census bulk package roadmap

## Objective

Make the browser a clear control plane for loading authoritative Census bulk
products into PostgreSQL. The normal path is deliberately short:

```text
package → preview → approve → download → stage → load → query
```

The browser presents packages, not raw FTP directory listings. Every package
shows its scope, source URLs, format, dependencies, capacity estimate, and
current lifecycle state. Advanced table/file selection remains separate and
never changes the meaning of a package.

## Shared lifecycle

Every adapter must use the same states and evidence boundaries:

| State | Meaning |
|---|---|
| `cataloged` | Official package metadata is visible; no data is acquired. |
| `draft` | An explicit plan names files and the intended canonical scope. |
| `previewed` | Published file sizes, disk projection, and source URLs are recorded. |
| `approved` | An operator approves exact files and load scope. |
| `downloaded` | Immutable artifacts and checksums are registered. |
| `staged` | Format-specific source rows are parsed without altering canonical facts. |
| `loaded` | Validated canonical tables reference immutable source artifacts. |

No loader may treat a provider ZIP as canonical data. Raw artifacts, staging
tables, and analytical tables remain separately owned and queryable.

## Package families and order

1. **ACS 5-year Summary File — complete release package** (implemented through
   catalog and preview): yearly Detailed Table archive, geography file, and
   table shells. It is the reference implementation for explicit bulk plans.
2. **County Business Patterns (CBP)** (catalog and preview implemented): one current-year bundle with
   county, state, U.S., CBSA/MSA, ZIP, and reference artifacts. The source is
   CSV-in-ZIP and maps naturally to a typed business-statistics fact table.
3. **Population Estimates Program (PEP)**: one package per published vintage.
   Do not mix vintages; raw CSV releases are revised annually and must retain
   vintage identity.
4. **2020 Decennial DHC**: product-specific package selection. The loader must
   join geographic headers and segmented files with `LOGRECNO`; it is not an
   ACS-compatible table loader.
5. **TIGER/Line**: geography layer packages by vintage. These load into spatial
   staging and `core.geography_boundary`, never measurement facts.

## CBP first-milestone acceptance criteria

- Browser exposes a single named 2023 CBP complete package and its component
  source artifacts, without a raw-file chooser.
- Preview records published size for every artifact and calculates stage,
  database, and reserve requirements.
- Approval requires an explicit geography/industry scope and does not silently
  promote all source rows to canonical data.
- Download is resumable, checksum-registered, and reports progress per artifact.
- Staging retains the source schema; the canonical loader is idempotent and
  records the source artifact for every loaded fact.
- At least one county-level analytical query is documented and validated against
  source rows.

## Design constraints

- Keep source-specific parsing inside provider adapters; the browser only
  coordinates packages and lifecycle state.
- Prefer a complete package plus explicit canonical filters over a growing list
  of special-case download toggles.
- Require documented handling for revised vintages, deleted files, and changed
  schemas before an adapter is promoted beyond preview.
- Show phase, completed/total, elapsed time, remaining time when meaningful,
  resume location, and actionable failure messages for download/stage/load jobs.
