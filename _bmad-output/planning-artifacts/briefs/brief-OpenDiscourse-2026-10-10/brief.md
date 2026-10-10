---
title: OpenDiscourse vision brief
status: approved-by-operator
created: 2026-10-10
updated: 2026-10-10
supersedes_in_part: ../brief-opendiscourse-2026-09-14/brief.md
---

# OpenDiscourse: a free, local political research center

## What it is
A research workbench that does for one researcher, or a small organization, what
OpenStates and think tanks do: join official records on **people, votes, bill text,
money, places and time**, keep the evidence behind every number, and produce
**findings and politician report cards that can be published** (blog, Substack).
The reader is the researcher. The audience is whoever the researcher publishes to.
This replaces the September line "not a consumer app"; it is still not a voter-facing app.

## Why
Think-tank-grade analysis is paywalled or one-sided. The pieces (votes, text, donors,
district statistics) are public, but they sit in separate systems with different
identifiers and dates. Linking them correctly is the product.

## Tracks and priority
- **Core (must):** 1 legislation and votes; 2 bill and law text; 5 outcomes by place
  (income, housing, jobs, crime, taxes, health, population, immigration-related measures);
  8 report cards and summary sheets.
- **Important, weaker inference:** 3 donations and lobbying; 4 federal awards and
  regulation beneficiaries; 6 members' trades from required disclosures.
- **Hard, wanted:** 7 what members say versus how they vote. Sources, in order: floor
  speeches in the Congressional Record; news-reported quotes via GDELT (marked as
  reported, lower trust); social media only if legally and cheaply obtainable.

## Who gets a card
Any office-holder in the data: U.S. representatives and senators, president and vice president,
governors and other statewide officers, and state legislators (via OpenStates). One card model, with
metrics chosen by office type. The first published card is a U.S. House member.

## Report card (target content)
Party loyalty (with the member's stated reason for dissent where one exists); attendance;
position on a voting-derived left-right scale and on issue-specific scales; donor
breakdown (size mix, top-donor concentration, industry, state, other candidates the same
donors back); tenure and prior offices; committees; ethics actions; district change since
first elected (income, jobs, crime, housing, population, spending received); consistency of
positions over time with flagged reversals; each with its inputs one click away.

## Principles
1. **Evidence first.** Every number traces to an official file, checksum and run.
2. **Honest grading.** Each metric is labelled *established*, *estimated* or *exploratory*,
   with method and known limits shown. Uncertain metrics may be published only as labelled.
3. **Findings can go against the researcher.** Hypotheses and metric definitions are written
   before results are viewed; null and contrary results are published too. This is what makes
   a "deservedly right" claim credible.
4. **Timelines, not verdicts.** The tool shows "trade, then committee vote" or "donation,
   then bill"; it does not label "bribed", "insider trading" or "lie". It labels
   "statement inconsistent with recorded vote" with both items shown.
5. **Many explained metrics, never one opaque corruption score.**
6. **Time travel.** Facts carry an as-of date so a card can be regenerated for any past date.
7. **People joins by identifier only** (BioGuide), never by name. No doxxing: no home
   addresses, family finances or non-public data. Follow the law and each source's terms.
8. **Build the foundations now, decide the analysis later.** Linkages and workflows first;
   language-model extraction is added once its accuracy has been measured.

## Non-goals (for now)
Market-price data; news as an editorial product; automatic "truth" verdicts; voter-facing app;
claims of intent about a person; local-government officials and courts (until a source is chosen); any ingest of data that cannot be tied to a source.

## Success signals
- A researcher can regenerate any member's card as of any past date, and each figure drills to its sources.
- For the 119th House: cards exist with at least attendance, party loyalty, vote-based ideology,
  donor concentration and district change, each labelled by reliability.
- A published finding can be re-derived by another person from the repository alone.

## Open
How to measure dissent reasons and topic-level flip-flops reliably; which approval-rating and
crime sources are usable and licensed; a measurable definition for any "bias" research;
legal review before publishing named-person grades.
