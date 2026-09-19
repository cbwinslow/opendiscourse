# Data acquisition plan: what we need, where it comes from, how we fetch it

Status: proposal for operator review, 2026-09-19. Measurements are marked
(measured); recalled facts about external services are marked (verify when
implementing). Implementation happens through Connectors (SPEC CAP-2), one
source at a time, each passing the Story 9.1 harness.

## 1. What the research questions need

| Need | Source | On disk now | Loaded |
|---|---|---|---|
| Bill identity, sponsors, cosponsors, actions, committees, subjects, CRS summary (the bill's intent), related bills | GovInfo BILLSTATUS bulk (108th on; confirmed) | 108-119 zips, 77 of 96 byte-identical to official, 118-119 refreshed by hand (measured) | 118, 119 |
| Bill text (what it actually does; entities later) | GovInfo BILLS bulk XML; `BILLSUM` for CRS summaries | 1.0 GB and 151 MB, unverified | no |
| Amendments (content, sponsor, status) | Congress.gov API `/amendment`; BILLSTATUS lists only a stub (verify) | none reliable | no |
| Roll-call votes and every member's position | House Clerk XML (`clerk.house.gov/evs/{year}/rollNNN.xml`), Senate.gov XML (`vote_menu_{congress}_{session}.xml` and per-vote files) (both measured to exist) | 118th only | 118: 912/1,241 House, 176/691 Senate |
| Why a member voted (evidence, not inference) | Congressional Record floor statements (GovInfo `CREC` via sitemaps), committee reports (`CRPT`), hearings (`CHRG`), CRS reports | none | no |
| Who and when (terms, state, district, party) | congress-legislators YAML (BioGuide ids) | loaded as people; **terms not loaded** | 12,770 people, 0 memberships |
| Money: donations | FEC bulk: `cn`/`cm` masters are on disk (`epstein/fec/`, 2000-2024); `ccl` linkage and `pas2`, `indiv` (registered) | mostly | staged only |
| Money: investments | House and Senate financial disclosures | 661 MB, unverified | no |
| Places for effects | Census/ACS/TIGER (loaded), FRED, crime (Epic 7) | state, county, CBSA, ZCTA boundaries | no congressional districts |

The earlier statement that the FEC `cn`/`cm` linkage files were missing was
wrong: they sit in `epstein/fec/`, which is why nobody found them.

## 2. Offerings and how to fetch each efficiently

**GovInfo bulk (`/bulkdata`, no key)** - collections include BILLSTATUS, BILLS, BILLSUM,
PLAW, STATUTE, FR, CFR. Directory JSON (`Accept: application/json`) gives name, size and
last-modified per file, so listing is free. BILLSTATUS ships one zip per Congress and bill
type (574 MB for 108-119, versus 171,799 single files): always take the zip. Closed
Congresses never change: fetch once. Open Congress: conditional request (size /
`Last-Modified`) once a day, replace only zips that changed.

**GovInfo packages and sitemaps (no key)** - `CREC` (Congressional Record), `CRPT`, `CHRG`,
`CDOC` are not in `/bulkdata`. Per-collection year sitemaps enumerate packages with
`lastmod` (measured); a package downloads as a zip (302 to the file, measured). One request
per package day; enumerate from the sitemap and diff against the registry.

**Congress.gov API (key, about 5,000 requests per hour, verify)** - for what bulk data lacks:
amendments, committee reports and meetings, nominations, treaties, House votes (recent
Congresses only, verify). Use it to fill gaps found by the coverage report, not to
backfill bills.

**House Clerk and Senate.gov XML (no key)** - only source of complete member positions for
108-117. About 12,000 House and 6,700 Senate votes: about 19,000 small requests. Two
concurrent connections per host at one request per second each is roughly 2.5 hours and
about 1.5 GB. Enumerate from the year index and the Senate vote menu (both measured),
skip what is already registered, never refetch a closed session.

## 3. Rules every downloader follows

1. **Enumerate cheaply, diff against the registry, fetch only what is new or changed.**
2. **Adopt, do not re-download**: bytes already on disk are compared to the official source
   by zip-member CRC (not whole-file hash: GovInfo repackages zips with different
   timestamps and identical content, measured for 117/hr). Identical: register into the
   active lake. Different: download the official file as a new artifact version.
3. **Immutable evidence**: files land in the active lake as `<dataset>/<name>.<sha256>.<ext>`
   (existing convention); old versions are never overwritten; the registry records URL,
   size, checksum, `Last-Modified`.
4. **Polite and resumable**: per-host pacing and concurrency caps, `Retry-After`, a
   descriptive User-Agent, capacity gate before large plans, resume from the registry
   state.
5. **Locations are configuration** (`inventory/lake_layout.yaml`, Story 9.4), so a folder
   can move and another person can point the project at their own storage.

## 4. Where things live (and the storage reality)

The two large volumes (`workspace`, `/mnt/storage`) are logical volumes on **the same
4-disk spinning array**; only the OS disk is separate, and both volume groups are fully
allocated. So spreading data across "partitions" adds no throughput; what helps is
avoiding copies, keeping the database tablespace and raw evidence on the array, WAL and
scratch on the OS disk (already the case for WAL; `/` is at 79%, watch it), and tuning
memory (pending the PostgreSQL 17 restart). Target layout: raw evidence and `meta/` under
one active lake (`DATA_ROOT` parent), sensitive material in `hold/`, database files under
the PostgreSQL role paths, legacy areas read through `LEGACY_LAKE_ROOT` until adopted.

## 5. Geography, kept simple and expandable

Join on the state first, and let the district be added without rework:
person (BioGuide) -> membership (term dates, chamber, party) -> post -> division
(`ocd-division/country:us/state:xx[/cd:n]`). `core.post` and `core.division` already
exist; `core.geography` has state, county, CBSA and ZCTA but no congressional
district. Step 1: load member terms with state (and district) from congress-legislators, so
every vote, sponsorship and donation ties to a state and joins to state-level ACS, FRED
and later crime. Step 2: add `congressional_district` geographies by Congress vintage
(TIGER CD files) and district-to-county/ZCTA weights from Census relationship files;
a ZIP is never assigned to one district without weights, since ZCTAs straddle districts.

## 6. Order of work

1. Merge 9.3 and 9.4 (coverage report, lake registry).
2. Prune the safe legacy areas (record what was deleted); adopt BILLSTATUS, FEC masters.
3. BILLSTATUS Connector: adopt-or-refresh 108-119, load bills, actions, sponsors.
4. Member terms and state posts (3.3).
5. Votes Connector (House and Senate XML), then amendments and text.
6. Districts and crosswalks; FEC promotion behind the person-join gate.
