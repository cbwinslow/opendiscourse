# Legislative workflow north star

Decided 2026-09-25. This is the done-state for **bills, official votes, and members**
in Congresses **108–119** (2003 through the current Congress). A check is met only
when the evidence named here is written down. A source with a silent field, or a
count nobody compared to the publisher, is not done.

The scoreboard is `research-db coverage` plus one field checklist per dataset in
`inventory/fields/`. Rules for every source stay in `inventory/DATA-SPEC.md`.

## Bills

Met when all of these are true:

1. GovInfo BILLSTATUS for Congresses 108–119 is loaded, and `research-db coverage`
   says the loaded bill count matches GovInfo. Any surplus or shortfall is a named
   exception, not a shrug.
2. Every BILLSTATUS field group is on
   `inventory/fields/congress.govinfo_billstatus.yaml` as `typed`,
   `whole_record_only` (with why it is not a column yet), or `not_stored` (with why
   it is out of scope).
3. These are real columns a researcher can filter, each row pointing at the retained
   GovInfo file and the run that wrote it: bill identity, dates, title, actions,
   sponsors and cosponsors, committees, subjects, CRS summaries, laws, related
   bills, the per-bill amendment list, and CBO cost estimates (publication date,
   title, link, description).
4. The full BILLSTATUS record stays in `core.bill_source_record`. Typing a column
   never deletes that record or the zip.
5. GovInfo bill text for Congresses 113–119 is attached to those bills. Congresses
   108–112 have no BILLS bulk; that absence is recorded. Unreadable files are named.
6. Running the bill sync again on an unchanged zip downloads nothing and changes no
   row. A newer zip replaces the derived rows and keeps the old file.

## Votes

Met when all of these are true:

1. Official House roll calls (Clerk XML) and Senate roll calls (senate.gov XML) for
   Congresses 108–119 match the publisher's own menus in `research-db coverage`.
2. Every member's vote on those roll calls is stored and linked to a person by
   BioGuide (House) or the Senate's member id. Display names are never the join.
3. House and Senate field checklists list every offered field. The roll-call header
   and each member's position are columns in both chambers. House party totals are
   columns. The Senate file has no party totals, and none are invented. The original
   XML is kept whole.
4. Known publisher quirks are written down and do not get "fixed" by dropping the
   file. Today those are: House BioGuide `L000555` (Letlow, died before being sworn
   in) on the opening roll call of the 117th; Senate roll 2003-262 (menu date and
   file date disagree); Senate roll 2020-216 (blank totals, 100 Not Voting).
5. UCLA Voteview is an extra layer: left–right scores, its roll-call index, and
   party medians, joined to people on the ICPSR number already stored. It does not
   replace Clerk or Senate votes. Its individual-vote file (`HSall_votes.csv`) is
   not downloaded. Voteview is met only after `research-db sync-voteview` has run
   on the live database and the unmatched people are listed.

## Members

Met when all of these are true:

1. Every person from `unitedstates/congress-legislators` has a BioGuide id.
   Other ids (Thomas, LIS, GovTrack, FEC, ICPSR, and the rest of that file) are
   stored as identifiers on that person. People are never matched by name.
2. Terms and seats for Congresses 108–119 are loaded, and `research-db coverage`
   says memberships are complete for that range. A term that cannot be placed
   (unknown district or jurisdiction) is counted and listed.
3. Current committee and subcommittee seats are loaded and linked on BioGuide.
   A repeated short code under two parent committees stays two committees.
4. Combining two person records moves every seat, vote, sponsorship, and
   committee assignment that pointed at the duplicate.
5. The legislator files have a field checklist. Every field the files offer —
   including biography, leadership, office contact, and social media — is typed,
   kept on a per-person whole record, or listed as `not_stored` with a reason.
   Keeping only the YAML file in `DATA_ROOT` is not enough: bills already keep a
   per-bill record in the database, and members must meet that same rule.

## The workflow

Met when, for each of the datasets above:

- One tracked command downloads from the original publisher into `DATA_ROOT`,
  registers the file, and loads it. No loader reads a machine-specific folder.
- A second run of unchanged input changes nothing. A killed run can be started
  again and finishes at the same result. A newer file replaces derived rows in
  one transaction and never overwrites the retained file.
- The run ledger records what was written: which table, which Congress, how many
  rows, and whether the run finished, needs a look, or failed.
- `inventory/progress.yaml` says `loaded` only after the live database matches
  the checklist and the coverage comparison. Code on `main` is not "loaded".

## Not this goal

A website, scorecards, embeddings, FEC donor joins, crime data, and downloading
CBO's own PDFs or XML. Those stay later work. CBO's publication date, title,
link, and description already sit inside BILLSTATUS and belong to the bill goal
above.

## Where this stands (2026-09-25)

| Check | State |
|---|---|
| Bills 108–119 loaded, full record kept | Met (172,736 bills). Six surplus 119th bills are the named exception. |
| Bill field checklist | Met. Committee reports, recorded votes named on actions, alternate titles, text-version links, notes, and 13 old-style files are still whole-record only, each with a reason. |
| CBO date, title, link, description as columns | Pull request #79 (migration `e8c2a9d14b59`). Not on `main`. Not in the live database. |
| Bill text 113–119 | Met (135,136 versions, none unattached). Six unreadable 113th XML files are named in `docs/PROJECT-STATE.md`. No bulk text for 108–112. |
| Official votes 108–119, both chambers | Met (23,359 roll calls, about 7.4 million member votes). Letlow and the two Senate quirks above are the exceptions. |
| Voteview scores on the live database | Not met. The command is on `main` (pull request #78). The live database has no Voteview tables. |
| People, BioGuide, terms 108–119 | Met for identity and terms (12,770 people, 45,535 memberships). |
| Current committee seats | Met (559 committees, 3,895 assignments, every seat linked on BioGuide). |
| Merging two people moves committee seats | Not met on the live database. The fix is on branch `feat/person-merge-committee-seats`, not merged. |
| Member field checklist and per-person whole record | Not met. No `inventory/fields/` file for `congress.legislators`. Biography, leadership, contact, and social media are not in a per-person database record. |
| Progress register matches the live database | Not met. House and Senate votes are still marked `ready` in `inventory/progress.yaml` even though they are loaded. |

Next work, in order: finish and ship the CBO columns, load Voteview on the live
database, then write the member field checklist and close whatever it shows is
missing. Do not start FEC person joins or a website to get this goal across the
line.
