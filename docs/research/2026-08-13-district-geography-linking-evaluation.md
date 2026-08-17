# Evaluation: District/ZIP/Demographic Linking — Comparable Projects, Guidance, and Architecture

Date: 2026-08-13
Status: Research complete, single-pass web research (Agent Teams infrastructure unavailable in this session; conducted directly instead)

## Executive summary

The plan we were about to write is validated, with one addition and one architecture question now closed:

- **Comparable production systems all use relational/tabular storage, not graph databases**, for exactly this domain (people, bills, votes, districts) at real scale over decades. Stick with PostgreSQL/PostGIS.
- **The one credible graph-database proposal found is scoped to a different problem** (statutory text versioning), not entity linking. It isn't evidence for reprocessing this sub-project.
- **The Census relationship-file approach we already chose is confirmed as the standard, primary-source method** — multiple independent, credible orgs converge on the same underlying Census Bureau data.
- **A real, peer-reviewed methodological risk (MAUP / ecological inference) needs to be added to the design** — this wasn't in the original plan and should be.
- **unitedstates/congress-legislators is confirmed as the correct federal member/district source**, exactly as `docs/model.md` already named it — this is the de facto standard, maintained collaboratively by GovTrack, ProPublica, MapLight, and FiveThirtyEight, public domain (CC0).

## 1. Comparable projects surveyed

| Project | What it is | Tech/data shape | Relevance |
|---|---|---|---|
| [GovTrack](https://www.govtrack.us/) | Nonprofit legislative tracker since 2004 | Django/Python, [govtrack.us-web](https://github.com/govtrack/govtrack.us-web) on GitHub, relational | 20+ years of production evidence for this exact domain on a conventional relational stack |
| [Voteview](https://voteview.com/) | UCLA-hosted roll-call/ideology data since Poole & Rosenthal's original NOMINATE work | Flat CSV/Stata distribution, ICPSR IDs | 30+ years; confirms flat/tabular data is sufficient even for the most analytically sophisticated legislative dataset in political science (DW-NOMINATE) |
| [LegiScan](https://legiscan.com/) | Commercial/free API covering all 50 states + Congress | Weekly CSV/JSON snapshots per session | All-50-states equivalent of what OpenStates/Plural gives us; confirms flat snapshot distribution is the norm |
| [unitedstates/congress-legislators](https://github.com/unitedstates/congress-legislators) | The community-maintained federal member roster | YAML/JSON/CSV, CC0 public domain | **This is the source to use for federal member+district data** — maintained by GovTrack, ProPublica, MapLight, FiveThirtyEight; includes bioguide↔ICPSR↔GovTrack ID crosswalks. Already named in our `docs/model.md`; this research confirms it's the real standard, not just an assumption. |
| [unitedstates/congress](https://github.com/unitedstates/congress) | Public-domain scrapers for bill/vote data | Python, CC0 | Same family as above; not needed since we already have GovInfo/Congress.gov ingestion, but confirms our approach matches the standard toolchain. |
| [Open States / Plural](https://docs.openstates.org/) | State legislative data (OpenStates rebranded to Plural in 2024-2025) | Django, relational, bulk CSV/JSON at `open.pluralpolicy.com/data` | We already ingest this. Note the rename for docs — bulk data endpoint may need updating in a future pass, not urgent now. |
| [represent-boundaries](https://github.com/opennorth/represent-boundaries) (Open North) | Shapefile→API boundary/point-in-district lookup, Django app | PostGIS-backed | **Used by both GovTrack and OpenStates** for "what district is this point in." Confirms PostGIS boundary+GIST-index lookup (what we already have in `core.geography_boundary`) is the established real-world pattern, not something we invented. |
| [MapLight](https://en.wikipedia.org/wiki/MapLight) | Nonprofit combining bills+votes (from GovTrack) with campaign contributions (from OpenSecrets) by geography, since 2005 | — | Direct precedent that combining votes + money + geography is a credible, established approach — validates the *broader* project vision, and is useful prior art for the later FEC sub-project. |

## 2. Published guidance and a real pitfall we were missing

**Modifiable Areal Unit Problem (MAUP) / ecological inference.** This is a well-documented, peer-reviewed methodological issue (see Cambridge's *Political Analysis* journal, which has published specifically on MAUP in political science). Core problem: aggregating data across artificially-drawn boundaries (like our ZIP↔district crosswalk) can distort the underlying pattern, and *conclusions drawn from group-level (district-level) aggregates about individuals within that district are not statistically valid without qualification* — this is the "ecological fallacy."

**Concrete implication for our design:** when the mart view says "District X is Y% low-income based on ZIP overlap," that number is a real, useful aggregate — but it is not the same statistical claim as "the people affected by this bill are Y% low-income." The two are easy to conflate. This wasn't called out anywhere in the design we drafted, and it should be — as a documented caveat on the mart views themselves (comment + doc note), not just tribal knowledge.

## 3. Architecture question: relational vs. knowledge graph — resolved

**Search evidence for graphs:** One credible academic paper, "Legislative Knowledge Management with Property Graphs" (Colombo, Cambria, Invernici; EDBT/ICDT 2025 TGD workshop), proposes property graphs for legislative data. On inspection (via search results and related papers "MLegis" and "LegisSearch" from the same research thread), **its actual scope is statutory text versioning and amendment tracking** — retrieving the text of a law as it existed at a given timestamp, modeling documents as hierarchical "parthood" structures. That is a different problem from ours (linking people↔districts↔geography↔demographics). It is not evidence for restructuring this sub-project, though it's a legitimate idea to file away for later if OpenDiscourse ever needs sophisticated bill-text-amendment-diffing (a separate, already-relationally-handled corner of the schema: `core.document`/`core.document_chunk`/`core.bill_document`).

**Evidence against graphs, for this problem:** every actual production system surveyed above (GovTrack, Voteview, LegiScan, OpenStates/Plural) uses relational or flat tabular storage for the exact entities we're linking (people, bills, votes, districts), at real scale, for years to decades. None uses a graph database for this.

**Verdict: keep the relational/PostGIS model.** No architecture change warranted. The existing `core.geography`/`core.geography_boundary`/`core.membership` design (vintage-aware, GIST-indexed, provenance-tracked) is consistent with what the field's actual production systems do, and represent-boundaries' widespread adoption for point-in-district lookup specifically validates the PostGIS-boundary-table pattern already in place.

## 4. What this changes in the design we drafted

1. **No architecture change** — relational/PostGIS confirmed, not reconsidered further.
2. **No crosswalk-source change** — Census's own `tab20_cd*_zcta520_*` relationship files remain the right call; this research adds independent corroboration (Geocorr itself is built from these same files; HUD's crosswalk is a derived product of the same underlying USPS/Census data) rather than surfacing a better alternative.
3. **Add: use `unitedstates/congress-legislators` explicitly as the federal member/district source**, not a generic "Congress.gov member API" — this is more precise than what was in the draft design and matches `docs/model.md`'s existing (previously unverified-by-us) citation.
4. **Add: an explicit MAUP/ecological-inference caveat** in the mart view's documentation and possibly as a SQL comment — this is new, not previously in the design.
5. **Noted for later, not this sub-project:** Plural's rebrand (docs housekeeping), MapLight/OpenSecrets as prior art for the future FEC sub-project.

## Addendum: `openstates/people` supersedes the planned two-loader approach

Follow-up research into MCP servers and reusable GitHub projects (2026-08-13) surfaced [`openstates/people`](https://github.com/openstates/people) — verified directly via the GitHub API, not just search results: CC0 public domain, pushed the same day as this research, 155 stars. Confirmed by reading a live sample record (`data/us/legislature/Adam-Smith-*.yml`):

- One consistent OCD-based YAML schema covers **both** state legislators and federal Congress members — the repo explicitly ports `unitedstates/congress-legislators` into the same schema ("New as of 2021: the data/us directory is also directly ported from the congress-legislators repo").
- Each person's `roles` list already carries **district + start_date + end_date per term** (e.g. `type: lower, district: WA-9, start_date: 1997-01-03, end_date: 1999-01-03`) — this is precisely the vintage-aware history `core.membership.district_geography_id` needs, pre-structured, no XML parsing required.
- Each person's `other_identifiers` block carries `bioguide`, `govtrack`, `icpsr`, `wikidata` — **and `fec` and `opensecrets`**. The latter two are out of scope for this sub-project but are a ready-made identity crosswalk for the not-yet-started FEC campaign-finance sub-project.

**Effect on the design:** Section 4 (Membership Population) originally proposed two separate paths — a transform-only step for state legislators (reading the already-staged OpenStates dump) and new federal ingestion work (via `congress-legislators`). `openstates/people` replaces both with a single new ingestion source and one loader, reducing this sub-project's federal-specific new-provider work substantially. The already-staged OpenStates dump (`openstatesstage.py`) remains the source for bill/vote data; `openstates/people` becomes the source for the person/membership/district data specifically.

## Sources

- [unitedstates/congress-legislators](https://github.com/unitedstates/congress-legislators)
- [unitedstates/congress](https://github.com/unitedstates/congress)
- [GovTrack.us](https://www.govtrack.us/) / [govtrack.us-web source](https://github.com/govtrack/govtrack.us-web)
- [Voteview](https://voteview.com/) / [Voteview data docs](https://voteview.com/articles/data_help_members)
- [LegiScan datasets](https://legiscan.com/datasets)
- [Open States is now Plural](https://pluralpolicy.com/blog/open-states-is-now-plural/) / [Open States docs](https://docs.openstates.org/) / [Plural bulk data](https://open.pluralpolicy.com/data/)
- [represent-boundaries (Open North)](https://github.com/opennorth/represent-boundaries) / [govtrack/boundaries_us](https://github.com/govtrack/boundaries_us)
- [MapLight (Wikipedia)](https://en.wikipedia.org/wiki/MapLight)
- [The Modifiable Areal Unit Problem in Political Science — Political Analysis, Cambridge Core](https://www.cambridge.org/core/journals/political-analysis/article/modifiable-areal-unit-problem-in-political-science/00960110D72C627020C8C7CD42B054E5)
- [Legislative Knowledge Management with Property Graphs — EDBT/ICDT 2025 TGD workshop](https://edbticdt2025.upc.edu/files/TGD/TGD-1.pdf)
- [MLegis: Property Graph-Based Information System for Legislative Analytics — Springer](https://link.springer.com/chapter/10.1007/978-3-032-27997-2_17)
- [Missouri Census Data Center — Geocorr](https://mcdc.missouri.edu/applications/geocorr.html) (context/corroboration from prior research turn)
- [HUD USPS ZIP Code Crosswalk Files](https://www.huduser.gov/portal/datasets/usps_crosswalk.html) (context/corroboration from prior research turn)
- [openstates/people](https://github.com/openstates/people) (verified via GitHub API; addendum research)
- [U.S. Census Bureau Data API MCP](https://github.com/uscensusbureau/us-census-bureau-data-api-mcp) (official Census Bureau org, verified via GitHub API)
- [census-geocoding-mcp](https://github.com/hesscl/census-geocoding-mcp) (installed this session)
- [@microsoft/postgres-mcp](https://www.npmjs.com/package/@microsoft/postgres-mcp) (installed this session)
