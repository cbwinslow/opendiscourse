# Bulk bootstrap plan

The database is designed to retain source artifacts before parsing them. Every
download is registered in `ingest.artifact` with a stable dataset ID, period,
URL, local path, bytes, SHA-256 checksum, status, and error state. Downloads
are atomic and resume from a `.part` file when the server supports HTTP Range.

## Bootstrap profiles

| Profile | Purpose | Included source families |
|---|---|---|
| `foundation` | Useful workstation-sized baseline | Census geography/ACS selected tables, Treasury curves, curated FRED, Congress/GovInfo recent history, OpenStates current dump |
| `historical` | Full public time-series and legislative history | All annual Census/ACS vintages, all Treasury years, full GovInfo collections, OpenStates monthly archives, FEC cycles |
| `exhaustive` | Large research archive | Census summary files at all target geographies, NIBRS/UCR annual releases, QCEW, USAspending, document/PDF archives |

`exhaustive` must be intentionally scoped by source, year range, geography, and
storage budget. “All Census data” is many distinct products and can require
terabytes; the catalog records every product independently rather than hiding
that behind one job.

## Authoritative bulk sources and acquisition policy

- **Census / ACS / TIGER:** download annual product files by dataset, vintage,
  geography and table group; use APIs only for incremental, targeted pulls.
  Store variable metadata and the estimate/MOE pair. Start with ACS 5-year,
  population estimates, TIGER boundaries, and County Business Patterns.
- **FRED / ALFRED:** use a versioned curated series manifest for the common
  macroeconomic baseline, then add thematic series manifests. Retain ALFRED
  real-time vintages if revision-aware analysis matters.
- **Treasury:** ingest the published daily nominal, real, and bill curves by
  calendar year. The loader preserves every published tenor instead of only
  2/10/30-year points.
- **FBI Crime:** use annual NIBRS/UCR/CDE bulk artifacts for historical loads;
  store agency/ORI reporting coverage separately from crime measures.
- **Congress/GovInfo:** use GovInfo bulk XML/JSON collections for bill status,
  bill text, Congressional Record, statutes, CFR and Federal Register. Use
  Congress.gov API for incremental entity changes and newer roll-call data.
- **OpenStates:** use its official monthly public PostgreSQL dump for a near
  complete snapshot, or per-session CSV/JSON archives for portable normalized
  imports. Download and register dumps first; restore only to an isolated,
  disposable staging database after inspecting the archive.
- **FEC / disclosures:** prefer official bulk transaction/filing files. Keep
  report URLs, filing/amendment IDs, and disclosure value ranges. Treat PDFs as
  source documents, not guessed structured facts.
- **Markets / OpenBB:** make each OpenBB provider a separately configured
  adapter. Index values and constituent data can have licensing limits; do not
  bundle or redistribute provider data without checking terms.

## Safety and reproducibility

- Never execute an externally downloaded `.sql` or `.pgdump` in the research
  database. Inspect it and restore only in a throwaway staging database.
- Keep downloaded artifacts outside Git (`data/` is ignored) and back them up
  to object storage using their checksum as the content identity.
- A parser may mark an artifact `loaded` only after it commits typed facts and
  records the exact artifact ID as lineage.
