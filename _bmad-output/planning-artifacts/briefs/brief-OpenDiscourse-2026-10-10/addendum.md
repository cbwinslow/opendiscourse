---
title: OpenDiscourse vision brief addendum (metric, source and method catalog)
created: 2026-10-10
status: draft
---

Reliability tiers: **E** established (published method, official data), **S** estimated
(modelled or probabilistic joins), **X** exploratory (needs validation before publishing).

## 1. Additional sources (beyond what is loaded)

| Purpose | Source | Notes |
|---|---|---|
| Floor speeches, dissent explanations | Congressional Record (GovInfo CREC) | Official, structured by speaker; start here for track 7 |
| Hearings, witnesses, markups | GovInfo CHRG, committee sites | Who testified, which industries |
| Ethics actions | House Ethics Committee, Office of Congressional Conduct, Senate Ethics statements | Small, public, official |
| Trades and assets | House Clerk periodic transaction reports, Senate disclosures | Values are ranges, not exact |
| Lobbying | Lobbying Disclosure Act database | **Filings name specific bills**: direct link bill -> lobbyist -> client |
| Foreign agents | DOJ FARA eFile | The honest route to "foreign influence", instead of donor country |
| Federal money | USAspending, SAM.gov, grants.gov | Awards by place and recipient |
| Rules and beneficiaries | Federal Register, regulations.gov (comments) | Who commented, who gained |
| Waste and fraud | Payment-accuracy (improper payments) and Inspector General reports | The only official measures of waste |
| Constituent opinion by district | Cooperative Election Study (open, Harvard Dataverse) | Lets us compare votes with what the district says it wants |
| Elections | MIT Election Data + Science Lab results | Needed for close-election comparisons and tenure |
| State campaign donors | Each state's campaign-finance filings (or an aggregator such as the National Institute on Money in Politics) | **FEC covers federal candidates only.** State legislators and governors need this; coverage and formats differ by state |
| Alternative ideology | Bonica DIME / CFscores (donor-based), Volden-Wiseman legislative effectiveness | Cross-check on DW-NOMINATE |
| Topic taxonomy | Comparative Agendas Project codes | Standard way to say which bills are the same issue (needed for flip-flops) |

Outcomes by place (track 5), each by county/district where published:
income and poverty (Census SAIPE, ACS), jobs and wages (BLS LAUS, QCEW; BEA regional), taxes (IRS SOI by
ZIP/county), housing cost (HUD fair-market rents, FHFA house price index, ACS rent burden),
homelessness (HUD count), crime (FBI NIBRS; coverage gaps must be flagged, not zero-filled),
health (CDC PLACES/WONDER, CMS), education (NCES), environment (EPA), mobility (Opportunity Insights),
immigration (CBP encounters, DHS yearbook, immigration court backlog, ACS foreign-born share),
disasters (FEMA). Approval ratings: pollster licences must be checked first.

## 2. Additional metrics for the card
- Bipartisanship (share of cosponsors and votes across parties; published method).
- Legislative effectiveness (bills advanced per stage versus expected for seniority).
- Vote alignment with district opinion (CES) and with the president.
- Absences split by reason where recorded, and by whether they were decisive.
- Donor concentration: top-donor share, small-dollar share, in-state share, industry mix (E/S).
- Same donor, many candidates (S, because individual donors have no stable id).
- Trades timed against committee activity and votes (timeline, not verdict).
- Money received by the district from federal awards (E).
- Consistency over time at topic level (X until a human-checked sample passes).
- Statement-to-vote consistency (X; published only with a measured accuracy rate).

## 3. Methods and cautions
1. **District change is context, not credit.** A member's effect on local crime or income is small and
   confounded. Compare the district to peer districts and the national trend, label it context, and
   use difference-in-differences or close-election comparisons only for specific, stated questions.
2. **Donor matching is probabilistic.** FEC individual donors have no stable id. The rule "never match by
   name" protects politician joins; donor grouping must be a separate, labelled (S) layer with its
   error rate measured.
3. **Language models must be measured before they are trusted.** Hand-label a sample (around 200),
   measure agreement and error, and publish the rate. Keep the extracted claim, its source passage and
   the model/version.
4. **Versioned methodology.** Every metric has a definition, version and changelog; a card records
   which versions produced it. Hypotheses are committed before results are viewed.
5. **Bitemporal facts.** Store when a fact was true and when we learned it, so cards can be rebuilt
   for any date. Redistricting makes district-based tenure comparisons need the Epic 10 boundary years.
6. **Corrections policy and legal review** before publishing named-person grades.
7. **Scope: every office-holder, one model.** Cards are keyed by person, office and term, with the
   outcome geography taken from the office (district, state or nation): U.S. representatives, senators,
   president and vice president, governors and other statewide officers, and state legislators. Metrics
   are defined per office type (legislators vote; governors sign, veto and appoint). The first card is a
   U.S. House member because that data is ready; state legislators come with the approved OpenStates
   promotion (issue #102), not after everything else. Local officials (mayors, councils) are not in the
   OpenStates snapshot and need a separate source. Courts are out of scope for now.
   Cross-office history (state legislator who became a member of Congress) joins only on reviewed
   identifiers, never on name.
