# Sprint Change Proposal: from warehouse to research center (report cards and publishable findings)

Date: 2026-10-10. Status: **approved by operator 2026-10-10** (rule amendments applied). Scope class: **Major** (PRD, epics, architecture),
implemented as a **direct adjustment** (add epics, no rollback). Epic 10 and Story 10.3 stay on the path.

Inputs: `briefs/brief-OpenDiscourse-2026-10-10/` (brief + addendum), `docs/data-audit-2026-10-10.md`.

## 1. Issue summary
The approved PRD (2026-09-14) calls the user "a researcher/operator, not a consumer app" and treats scorecards,
stocks and money as later or out of scope. The operator has now set the goal: a free local political research
center that produces **published findings and politician report cards** across eight tracks. Core: votes,
bill text, outcomes by place, report cards. Important: donations/lobbying, federal awards, members' trades.
Hard: statements versus votes. The current plan builds the data spine well but has no epic for
report cards, time-travel facts, metric definitions, NLP evaluation, or publishing, and several rules
forbid parts of the vision.

## 2. Impact
**Epics.** Epic 10 unchanged, proceeds 10.3 to 10.6. Epic 7 ("v1.1 money, elections, crime", stories TBD) is
replaced by Epics 14, 16, 17 below. Epic 5 (marts) is absorbed into Epics 13 and 19. Epic 9 (ingestion contract) is
the template every new source uses.
**PRD.** Section 2.2 non-users, section 5 non-goals, section 6 MVP, section 7 metrics need edits (see 4).
**Architecture.** Four new decisions (AD-12 to AD-15, see 4). No change to AD-1 to AD-11.
**Code.** Existing code unaffected. New: as-of columns on new fact tables, metric registry, evaluation harness.
**Rules (`AGENTS.md`, `v1-scope.md`).** Three amendments need operator approval (see 5).

## 3. Recommended approach
Direct adjustment: keep the identity, provenance and legislation foundation; finish the district slice; then build
the **first report card** from data already loaded before widening any source. Reason: it proves the end-to-end
path (as-of facts, metric definitions, evidence drill-through, publishing) early and shows what the data can
honestly support. Effort is large but incremental; risk is scope growth, mitigated by the gates below.

## 4. Detailed change proposals

### New epics (each needs its own spec before starting; a roadmap row is not authorization)
| Epic | Name | Tracks | Contents |
|---|---|---|---|
| 12 | Time-aware facts and method registry | foundation | As-of (knowledge-date) columns and view pattern; versioned metric definitions with reliability tier (established / estimated / exploratory); hypothesis log committed before results; evaluation harness for text models |
| 13 | Politician profile and vote metrics, any office | 1, 8 | One person-office-term card model (representatives, senators, president, governors, state legislators); office-specific metrics (votes for legislators; signs, vetoes for governors); tenure, prior offices, committee history; attendance; party loyalty; bipartisanship; vote-based ideology (Voteview); legislative effectiveness |
| 14 | Outcomes by place and opinion | 5 | District ACS (Story 10.4), PUMS all years typed with weights (see 6), LAUS, QCEW, BEA, IRS SOI, HUD, FHFA, NIBRS, CDC PLACES, immigration measures, Cooperative Election Study, election results |
| 15 | Text analytics | 2 | Policy topic taxonomy (Comparative Agendas), bill chunks and embeddings (ADR first), text reuse, accuracy-measured claim extraction |
| 16 | Money in and out | 3, 4 | FEC typed cycles and identity bridge (issues #103, #104), donor grouping layer (estimated), Lobbying Disclosure Act, FARA, USAspending, rules and comments |
| 17 | Disclosures and ethics | 6 | House/Senate disclosures, ethics actions; timeline views, no verdict labels |
| 18 | Statements | 7 | Congressional Record speeches, GDELT reported quotes (lower trust), consistency check with measured accuracy; social media only if legally and cheaply available |
| 19 | Report cards and publishing | 8 | Card generator, as-of regeneration, methodology and corrections pages, evidence drill-through, findings export, legal review gate |

### Architecture additions (ADRs to write)
- AD-12 bitemporal facts (valid time and knowledge time).
- AD-13 metric registry: definition, version, inputs, reliability tier; a card records the versions used.
- AD-14 model-output rule: any text-derived claim stores the passage, model and version, and has a published error rate.
- AD-15 publishing exports: Postgres remains the record; Parquet/CSV extracts are derived and rebuildable.

### PRD edits
- 2.1/2.2: add "publishes findings and report cards"; keep "not a voter-facing app".
- 5 Non-goals: replace "scorecards later" with "no single opaque score; no verdict labels such as bribed or lie".
- 7 Metrics: add SM-5 (first card regenerates for any past date and every figure drills to source), SM-6 (every
  published metric carries a tier and version).

### OpenStates promotion is part of this plan, not later
The snapshot holds about 22,700 people, 1.19 M vote events and 1.56 M bills across all states, with 254
executive-office membership records (not yet confirmed to be all governors). The already-approved
programme (issues #100 to #105) promotes this into owned tables. Epic 13 depends on #102 for state
legislators and governors; it does not wait for the other epics.

### First report-card slice (the next milestone after Epic 10 slice_proven)
Epic 12 (minimum) then Epic 13 then Epic 19 (minimum), for the 119th House: tenure, attendance, party loyalty,
vote-based ideology, committees, district context. Money, outcomes beyond Census, trades and statements follow in
the order 16, 14, 17, 18, 15.

## 5. Rule amendments for operator decision (not applied)
1. `AGENTS.md`: "Do not invent news, stocks, or corruption scores as schema domains" becomes: member disclosures
   (STOCK Act trades) are an allowed source domain; market prices stay out; GDELT news is allowed only as reported
   statement evidence; scorecards are derived marts with versioned metrics, no single opaque score.
2. `AGENTS.md` and `v1-scope.md`: "Do not start Epic 7" becomes: Epics 14, 16, 17, 18 open only after Epic 10
   `slice_proven` and the gates below.
3. `v1-scope.md` "Not a product domain" section: update to match item 1.

## 6. Sequencing and gates
1. Story 10.3 now, then 10.4 to 10.6 (unchanged).
2. Parallel, not blocking: Postgres query tracking and tuning (needs restart); PUMS typed load design (ADR-0006
   style, all years 1- and 5-year, 80 replicate weights, measured size first; no drop until reconciled).
3. Epics 12, 13, 19 (first card). Gate: operator reviews a real card before anything is published.
4. Then 16, 14, 17, 18, 15. Gate for each: source contract (coverage, licence, size), capacity preview, and for
   person-linked data the identity gate. Legal review before any named-person grade is published.

## 7. Handoff
Architect: ADRs AD-12 to AD-15. PM: PRD edits and Epic 12, 13, 19 specs. Developer: continue Story 10.3.
Scrum master: rerun sprint planning after approval. Success: the first card exists, regenerates for a past date,
and the operator can trace each number.

## 8. Operator decisions needed
- Approve this proposal (yes / revise).
- Approve the three rule amendments in section 5 (they change what the project forbids).
- Confirm the card sections in the first-card slice.
