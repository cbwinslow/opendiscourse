# Existing Congress research stack (2026-09-22)

What already exists so we wrap it instead of inventing a second Congress database.
Operator decision: no website now. Next loaders are committee membership, CBO columns, Voteview ideology. Scorecards later as derived tables over evidence.

## Plain finding

Nobody publishes one FOSS warehouse that is “our product, finished.” Several **maintained collectors and academic datasets** already do the hard parts (IDs, votes, committees, ideology). We keep official bytes in Postgres and wrap those projects.

## Wrap (do not rewrite)

| Project | What it is | How we use it |
|---|---|---|
| [unitedstates/congress](https://github.com/unitedstates/congress) | Public-domain collectors (GovTrack + Sunlight origin) | Already wrapped for vote/bill URLs |
| [unitedstates/congress-legislators](https://github.com/unitedstates/congress-legislators) | People + **current committee/subcommittee membership** YAML | People loaded; membership YAML is the next Connector |
| [Voteview](https://voteview.com/data) (UCLA; Poole/Rosenthal DW-NOMINATE) | Ideology scores, all Congresses, ICPSR ids | Download CSVs; join on ICPSR we already store |
| [BICAM](https://bicam.net/) (MIT, *Scientific Data* 2025) | Bills, committees, hearings, reports, 1789–present; Python downloader | Methods + completeness checklist; not our system of record |
| CBO | Cost estimates already in BILLSTATUS JSON | Type those fields; CBO’s XML index URL returned HTTP 403 to a scripted fetch (2026-09-22) |

## Look at, do not copy as the warehouse

- **GovTrack.us** (open site + GitHub): the original unitedstates/congress consumer. Website, not our schema.
- **TallyHQ**, BallotWatch, WeThePeople: similar product ideas; they still pull Clerk, GovInfo, FEC, congress-legislators. Proof the sources are right; we keep provenance.
- **OpenSecrets / CRP**, CQ, FiscalNote: useful methods, often license-restricted. Prefer FEC.gov and LDA.gov.
- **LCV / ADA / AFL-CIO scorecards**: advocacy grades. Fine as *later* comparison series, not as our facts.
- **ProPublica Congress API**: compiled from the same official sources; not a replacement for bulk files.

## Academic methods to piggyback

- **DW-NOMINATE** (Voteview): standard left–right from roll calls. This is the usual “bias/ideology” measure in political science.
- **Party unity / majority-party support**: computed from the votes we already have (CQ popularized the idea; we can compute it ourselves).
- **Policy Agendas / Comparative Agendas**: topic codes over time (hearings, laws, votes). Later, if we need a shared topic system beyond CRS subjects.
- **Center for Effective Lawmaking** (UVA): bill-progress metrics. Later.
- **BICAM paper**: how to link Congress.gov collections to Voteview and lobbying (LDA).

## Not now

STOCK Act trades, lobbying, crime series, USAspending: real, useful, and each needs its own Connector and ID rules. FEC *files* are already in `DATA_ROOT`; joining them to people stays gated until BioGuide/FEC IDs are reviewed.

## BMAD note

New loaders get an inventory row + a short story, then a Connector named like the others (`research-db sync-committee-membership`, `sync-voteview`, CBO typed from existing JSON). We do not rewrite the product spec for each download. Scorecards stay a later mart spec, built only from evidence-backed rows.
