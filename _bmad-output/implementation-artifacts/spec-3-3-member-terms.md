---
title: 'Story 3.3 - Member terms, state and district posts'
type: 'feature'
created: '2026-09-19'
status: 'in-review'
baseline_commit: '7b9cba2'
route: 'spec-then-build'
context:
  - '{project-root}/docs/PROJECT-STATE.md'
  - '{project-root}/_bmad-output/implementation-artifacts/spec-3-1-bioguide-identity.md'
  - '{project-root}/docs/adr/0002-schema-invariants.md'
  - '{project-root}/docs/data-source-map.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** `core.membership`, `core.post` and `core.division` are empty. The 12,770 people loaded in Story 3.1 have no terms, so nothing says who served in which chamber, for which state or district, from when to when, or for which party. Votes, sponsorships and donations cannot be attributed to a state or district, and `research-db coverage` reports 0 memberships for every Congress.

**Approach:** Extend the existing `congress.legislators` Connector (same two retained YAML artifacts, no new command) to promote every term into `core.membership`, with the state or district as a `core.post` attached to a `core.division` (`ocd-division/country:us/state:xx[/cd:n]`). One membership per term, keyed to its person by BioGuide and to its source artifact.

## Boundaries & Constraints

**Always:** People are matched by BioGuide only, through `core.person_identifier`; a term whose BioGuide is unknown is counted and reported, never matched another way. House and Senate organizations are looked up (type `lower`/`upper`, jurisdiction `us`, exactly one each); if they are absent or ambiguous the load fails with a message naming `load-openstates-organizations`. A division id is written only where it is defined: states, `cd:N`, `cd:at-large` (district 0), DC (`district:dc`), the territories (`territory:pr|gu|vi|as|mp`) and the historical `territory:dt|ot|pi` (Dakota, Orleans, Philippines), all of which exist in the OCD registry we already hold. A term with an unknown district (`-1`) gets a membership with no post; state and district stay in `metadata`. A division id names a place, not a boundary: geometry differs by redistricting vintage, and this story loads none. Set-based load in one transaction. Rerun with the same bytes changes nothing; a new upstream version updates end dates, party and evidence of existing terms and adds new ones (evidence moves to the latest asserting artifact). The run ledger records `core.membership` inserted, updated and skipped.

**Never:** No name, birthday or district matching to find a person. No committee membership, social media or district offices (later stories). No district geometry or crosswalks. No fake OCD ids for anything the registry does not define. No change to people or identifiers.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| First load | 12,770 people, 45,535 terms | one membership per term, posts and divisions created once, all with `source_artifact_id` | organizations missing: fail before any write |
| Rerun, same bytes | unchanged | 0 inserted, 0 updated | N/A |
| Upstream change | a member's `end` or party edited, a new term added | the term is updated (evidence moves to the new artifact), the new term inserted, others untouched | N/A |
| House, district N | `type: rep`, `district: 7`, `state: WA` | post on `ocd-division/country:us/state:wa/cd:7` | N/A |
| At-large | `district: 0` | post on `.../state:xx/cd:at-large` | N/A |
| Senate | `type: sen`, `class: 1` | post `Senator, Class 1` on the state division | N/A |
| Delegate or commissioner | `state: DC/PR/GU/VI/AS/MP` | post on the territory or DC division | N/A |
| Unknown district | `district: -1` | membership with no post, `metadata.district = -1` | N/A |
| Historical territory | `state: DK/OL/PI` | division `territory:dt/ot/pi` | N/A |
| Multi-member at-large | two members, same state, district 0 | two memberships on one post | N/A |
| Missing party | term without `party` | membership with `party` absent from metadata | N/A |
| Unknown state code | code not in the table | the term is skipped, counted and listed in the result; run `partial` | never guessed |
| Term with a BioGuide not in the warehouse | cannot happen after 3.1 promote | counted as unresolved; run `partial` | N/A |

</frozen-after-approval>

## Code Map

- `src/opendiscourse_research/ingestion/legislator_terms.py` -- new: `Term`, division and post rules, staged rows.
- `src/opendiscourse_research/ingestion/legislators.py` -- `Legislator.terms`, parse, `publish` calls `promote_terms`.
- `src/opendiscourse_research/repositories/people.py` + `sql/query/people/*terms*.sql` -- set-based promotion.
- `migrations/versions/` -- unique indexes for idempotency (`membership` term key, `post` key).
- `src/opendiscourse_research/repositories/coverage.py` -- memberships counted by term/Congress date overlap, the rule its expectation already uses.
- `tests/test_legislators_parse.py`, `tests/test_legislator_terms.py`, `tests/test_legislators_load.py`, `tests/test_coverage_db.py`.
