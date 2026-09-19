# Data acquisition plan

Status: proposal, 2026-09-19. Facts marked (measured) were checked against the live
service; (verify) means confirm against current documentation when implementing.

## The workflow every source follows

**download -> inventory -> ingest**, on anyone's machine:

1. **Download** from the original government endpoint over the network into the folder the
   user configures (`DATA_ROOT`; its parent also holds `meta/`). Bytes are immutable and
   named by checksum (existing `retain_artifact_bytes` convention). Nothing reads a
   machine-specific path.
2. **Inventory**: every file is recorded in the artifact registry (`ingest.artifact`) with
   URL, size, checksum, and the server's `Last-Modified`; a check compares the folder to the
   registry (missing, orphaned, unfinished). "What do I have?" is a query, not folklore.
3. **Ingest** from registered artifacts into the data model (`core`/`fact`), by set-based
   load per ADR-0003, idempotent and resumable, each run recorded in `ingest.run_target`.

Each source is a Connector (SPEC CAP-2) implementing those stages, so a new researcher
runs one command per source and gets the same database.

## What is needed and where it comes from

| Need | Original source | Notes |
|---|---|---|
| Bills, sponsors, cosponsors, actions, committees, subjects, CRS summaries | GovInfo BILLSTATUS bulk zips, Congress 108 on (108 confirmed as the first) | one zip per Congress and bill type; 574 MB for 108-119 (measured) |
| Bill text | GovInfo BILLS bulk XML | needed for intent and later entity extraction |
| Amendments, committee reports and meetings, nominations | Congress.gov API (key, about 5,000 requests/hour, verify) | fills what bulk data lacks |
| Roll-call votes and every member's position | House Clerk XML per vote; Senate.gov vote menus and per-vote XML (both measured); reuse `unitedstates/congress` as the producer per `reuse.md` | about 19,000 small files for 108-117; polite, resumable |
| Floor statements, committee reports, hearings (evidence of "why") | GovInfo package sitemaps and package zips (CREC, CRPT, CHRG; sitemaps measured) | stored as evidence, never interpreted |
| Members, terms, states, districts, BioGuide ids | `unitedstates/congress-legislators` | already loaded as people; terms still to load |
| Campaign finance | FEC bulk files (cn, cm, ccl, indiv, pas2, oth, oppexp) | committee and candidate masters link money to candidates |
| Places for effects | Census (ACS, TIGER incl. congressional districts and relationship files), FRED | state first, districts later |

## Efficiency rules

1. Enumerate cheaply (directory JSON, sitemaps, year indexes), diff against the registry,
   fetch only what is new or changed.
2. Prefer bulk packages (one zip per Congress and type) to per-file requests.
3. Closed Congresses and closed cycles are fetched once; the current one is refreshed with a
   conditional request (size, `Last-Modified`) at most daily.
4. Per-host pacing and concurrency caps, `Retry-After`, a descriptive User-Agent, capacity
   gate before large plans, resume from registry state.
5. Locations are configuration: `DATA_ROOT` and the database URL. No path is baked in.

## Geography, state first and expandable

person (BioGuide) -> membership (term dates, chamber, party) -> post -> division
(`ocd-division/country:us/state:xx[/cd:n]`). `core.post` and `core.division` exist;
`core.geography` has state, county, CBSA and ZCTA but no congressional districts. Load member
terms with state first so every vote, sponsorship and donation joins to state-level ACS, FRED
and later crime; then add district geographies by Congress vintage and district-to-county/ZCTA
weights (never assign a ZIP to one district without weights).

## Order of work

1. BILLSTATUS Connector: download, register, load bills, actions, sponsors (Congresses
   108-119), then point `research-db coverage` at what it fetched.
2. Member terms and state posts.
3. Votes Connector (wrapping `unitedstates/congress`), then amendments and bill text.
4. FEC Connector with the masters; districts and crosswalks.
5. Remove the leftover loaders that read fixed local paths (below).
