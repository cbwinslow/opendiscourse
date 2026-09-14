---
title: OpenDiscourse
status: final
created: 2026-09-14
updated: 2026-09-14
---

# Product brief: OpenDiscourse

OpenDiscourse is a **reproducible, provenance-aware public-policy and
social-science research warehouse**. It joins authoritative U.S. government
datasets across **identities, geography, and time**. It is not a giant lake of
every interesting file.

The product is a **singular research surface**: ingest structured and
unstructured public data, keep the original evidence, promote reviewed facts,
and let researchers query place-year panels, bills, votes, members, and
documents without rebuilding connectors. Prefer wrapping maintained upstream
projects (`unitedstates/congress`, `congress-legislators`, OpenStates dumps,
Census, dlt, dbt, PostgREST, DuckDB, pgvector) over writing new scrapers.

**v1 loadable spine:** identities, geography (TIGER), legislation
(Congress.gov / GovInfo / OpenStates), census/housing, sparse macro (FRED,
Treasury, bounded BLS). **v1.1** (identity-gated): FEC, politician
disclosures/investments, elections, crime. **Not a product:** news as a
schema domain, stock picking, corruption scores, CFA market work.

Primary user is a researcher/operator (this repo's owner) who needs
defensible joins, not a consumer app. Surfaces: CLI (`research-db`), optional
Textual browse, later read-only `api` (PostgREST) and DuckDB/Parquet sidecars.

Success: a new source is added through a Connector + reviewed contract without
editing god modules; a researcher can trace a fact to URL/checksum/run; Senate
and House votes come from wrapped upstream tools, not a homegrown scraper.
