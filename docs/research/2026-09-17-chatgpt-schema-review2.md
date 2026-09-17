Yes. I have been reviewing **`cbwinslow/opendiscourse` specifically**, including the current `main` branch, the Alembic schema, BMAD artifacts, ingestion code, OpenStates FDW work, GovInfo BILLSTATUS pipeline, congressional health checks, inventory/contracts, current PRs, and the recent legislative-schema work. The latest `main` already includes PR #21, which added the owned `core.post` / `core.division` primitives and attached posts to memberships.

After doing another deeper pass, including checking the actual current federal source systems, I have **more confidence in the fundamental architecture than I did before**. I would not restart this repository, replace BMAD, replace PostgreSQL, copy the OpenStates schema, or invent another abstraction framework.

What I would do is **harden several research-integrity details before we dramatically expand the political dataset catalog**.

## The goal is now clear

I would phrase OpenDiscourse very simply:

> **OpenDiscourse is a provenance-first research database that makes public-policy and political data reproducibly ingestible, maintainable, joinable, and analyzable.**

The product is really four things working together:

```text
source registry + contracts
          ↓
      connectors
          ↓
immutable source evidence
          ↓
stage → typed core/fact → research marts
```

The database itself should answer questions such as:

```text
Who represented this district at this date?
What party/caucus were they affiliated with then?
What bills did they sponsor?
What actions happened to those bills?
What roll calls occurred?
What exactly was being voted on?
How did each member vote?
What did the source actually say at the time?
What demographics/economic conditions existed in the represented area?
Can I reproduce this result later?
```

That is a coherent product. The current architecture already reflects most of it: Postgres/PostGIS as system of record, immutable lake/raw evidence, replaceable staging, reviewed typed `core`/`fact`, dbt-owned marts, and connectors as the source-extension mechanism.

The Connector protocol is also appropriately simple: discover → select → plan → extract → evidence → stage → normalize → validate → publish → checkpoint, with a checkpoint even on failure. I would finish proving that with FRED rather than redesigning it again.

## The political-data architecture I would commit to

There should **not** be one provider that becomes “truth.”

That was the biggest conceptual wording problem I found. One existing operations plan still said:

> “OpenStates supplies the canonical reference baseline…”

That is too strong for federal political research. I corrected that in the PR I created.

For federal legislation, I would use this source model:

| Domain                       | Primary evidence/acquisition                                 | Role of other sources                              |
| ---------------------------- | ------------------------------------------------------------ | -------------------------------------------------- |
| Bills, status, actions       | GovInfo BILLSTATUS bulk + Congress.gov incremental API       | OpenStates for reconciliation/interoperability     |
| Bill text/version documents  | GovInfo BILLS/BILLSUM/packages                               | Congress.gov metadata and links                    |
| Federal people               | Congress.gov/BioGuide                                        | `congress-legislators` crosswalk + OCD identifiers |
| Seats/terms/party/caucus     | official member data + temporal `congress-legislators` terms | OpenStates membership/post semantics               |
| House roll calls             | House Clerk chamber-native records                           | wrapper + Congress.gov/OpenStates reconciliation   |
| Senate roll calls            | Senate LIS chamber-native records                            | wrapper + Congress.gov/OpenStates reconciliation   |
| State/local legislative data | OpenStates/OCD                                               | jurisdiction-native sources where needed           |

GovInfo currently exposes bulk Congressional Bills, Bill Status, and Bill Summaries; its developer documentation says BILLSTATUS goes back to the 108th Congress and bill text to the 113th. ([GovInfo][1]) Congress.gov's API is currently v3, exposes bills, amendments, members, committees and many other congressional entity types, and its House vote API remains marked **beta**. ([GitHub][2])

So your current **bulk bootstrap + API incremental** rule is exactly the right pattern.

OpenStates remains extremely valuable, but as an OCD-aligned interoperability layer and particularly as the state-legislative foundation. Its data model explicitly centers jurisdiction, session, bill, vote, person, organization, post and membership, and treats political parties as organizations as well. ([Open States][3])

That matches the direction we've now taken with `core.post`, `core.division` and `core.membership`.

## One serious implementation issue I found

This is the biggest thing I want fixed.

Your architecture says source evidence is immutable.

But right now `ingest.artifact` is unique on:

```text
(dataset_id, artifact_key)
```

and `register_artifact()` performs an `ON CONFLICT ... DO UPDATE` that can replace `checksum_sha256`.

Consider GovInfo:

```text
BILLSTATUS-119-hr.zip
```

today has:

```text
SHA256 = AAA
artifact_id = X
```

Tomorrow GovInfo refreshes that same logical ZIP:

```text
BILLSTATUS-119-hr.zip
SHA256 = BBB
```

Currently we can make the same `artifact_id = X` mean the new bytes.

That breaks a very important research property:

> an evidence ID should forever identify the same evidence.

The model should instead conceptually distinguish:

```text
logical artifact
BILLSTATUS-119-hr.zip
        │
        ├── version A → checksum AAA → artifact UUID 1
        ├── version B → checksum BBB → artifact UUID 2
        └── version C → checksum CCC → artifact UUID 3
```

Then a historical `bill_action` can point to exactly the bytes from which it came.

I added **BMAD Story 1.7 — Immutable artifact versions** for this rather than sneaking a migration into an unrelated PR.

This is not evidence that the architecture is wrong. It's actually the opposite: **the architecture's invariant is right; the implementation hasn't completely caught up with it yet.**

## I found the same issue in PR #22

PR #22's overall design is good. It promotes a bounded federal OpenStates slice into owned `core`, joins people through OCD identifiers rather than names, remains idempotent, and keeps the OpenStates database read-only.

But the current branch creates synthetic evidence like:

```text
openstates_source://federal-promote
```

rather than tying those promoted rows directly to the actual checksum-backed monthly OpenStates dump.

The good news is that you already wrote the infrastructure needed to do this correctly. `openstatessnapshot.py` creates manifests containing period, byte count, SHA-256, source URL and required relations, and validates the dump against them.

So we should connect:

```text
OpenStates monthly pg_dump
       ↓
approved manifest
       ↓
checksum/versioned ingest.artifact
       ↓
FDW restored snapshot
       ↓
promoted core rows
```

rather than:

```text
current FDW relation
       ↓
synthetic "federal-promote" artifact
```

I left that exact review feedback on PR #22 rather than changing its schema underneath the authoring branch.

I also caught a subtler issue: some of the `INSERT ... ON CONFLICT` promotion SQL updates current canonical values while keeping the **old** `source_artifact_id` with `COALESCE(existing, new)`. If a later OpenStates snapshot changes a membership/session/post, the row could contain the new value while its evidence pointer still identifies the old snapshot.

For research integrity:

```text
current value
     ↓
evidence supporting that current value
```

must remain true.

Historical evidence stays immutable separately.

## Votes need one more modeling pass

This is probably the most important political-schema improvement after provenance.

Right now:

```text
core.roll_call
    bill_id nullable
```

is fine as a starting point.

But a roll call is **not necessarily a vote on a bill**.

The House Clerk has a March 27, 2026 roll call simply on a motion to adjourn. ([House Clerk][4]) House roll calls can also be specifically on amendments. ([House Clerk][5])

The Senate provides an even clearer example: many current roll calls are votes on nominations rather than bills, and the Senate page provides the nomination number, question, result, counts and individual positions. ([U.S. Senate][6])

Therefore I would eventually add something along the lines of:

```text
core.roll_call_reference
────────────────────────
roll_call_id
reference_type
namespace
external_id
relation
label
source_artifact_id / source_payload_id
```

So a roll call can reference:

```text
bill
amendment
nomination
treaty
motion
resolution
procedural question
```

without stuffing every political thing into `core.bill`.

That keeps `core.bill` typed while letting votes remain universal.

I would also add a separate typed tally grain:

```text
fact.roll_call_count
────────────────────
roll_call_id
option
count
source evidence
```

because official House and Senate sources publish vote totals, and they provide an excellent integrity check against the number of loaded member votes.

For example:

```text
SUM(member_vote)
          ==
SUM(roll_call_count)
```

modulo specifically documented exceptions.

That's exactly the sort of invariant that makes a political research database trustworthy.

## Keep raw and normalized vote positions

Another subtle issue: never discard the source vocabulary.

House can say:

```text
Aye
No
Present
Not Voting
```

while another source may normalize that to:

```text
yea
nay
abstain
not-voting
```

OpenStates explicitly provides normalized vote options and vote counts. ([Open States][7])

I'd eventually represent both:

```text
source_position = "Aye"
position = "yea"
```

The normalized field makes cross-source research easy.

The source field lets us prove we normalized correctly.

Same philosophy applies to bill classifications, action classifications, party names, committee roles, etc.

## Party affiliation needs to become temporal data

I would **not create a special giant `party` subsystem**.

Your existing abstractions can handle it elegantly:

```text
core.organization
    organization_type = party

core.membership
    person
    organization
    start_date
    end_date
```

OpenStates already treats political parties as organizations and memberships as person↔organization relationships. ([Open States][8])

This matters because:

```text
person.party = "Republican"
```

is not a historically valid research representation.

Instead:

```text
Person A
 ├─ Democratic   2001–2009
 ├─ Independent  2009–2011
 └─ Republican   2011–...
```

The `congress-legislators` dataset is particularly useful here: its term records contain state, district, party and caucus, and explicitly supports `party_affiliations` when affiliation changes within a term. It also provides BioGuide and numerous other crosswalk identifiers.

So Story 3.1 should eventually do more than simply import BioGuide IDs.

It should become our federal **identity + term crosswalk**, while carefully retaining provenance.

## Organization hierarchy is another later improvement

Right now OpenStates organization parentage is partly being carried through metadata.

Long-term, for real congressional research, we should be able to ask:

```text
Congress
  ├─ House
  │   ├─ Committee
  │   │   └─ Subcommittee
  │   └─ ...
  └─ Senate
      └─ ...
```

OpenStates itself models parent/child organizations. ([Open States][7])

Eventually I would make this relational via either:

```text
organization.parent_organization_id
```

or, better if we need time/versioning:

```text
core.organization_relationship
```

But **not yet**. It's not blocking the current vertical slice.

## `core.post` is correct, but incomplete for state-scale use

PR #21 was a good change. The migration gives us:

```text
division
post
membership.post_id
```

and protects the invariant that a membership's post belongs to the same organization.

However Open Civic Data posts also have:

```text
startDate
endDate
maximumMemberships
```

and explicitly allows some posts to have more than one active member. ([Open States][7])

For Congress, the simpler current shape is adequate.

Before we promote every state legislature, I would add those semantics. Otherwise something like a multi-member legislative district could eventually force us into an incorrect uniqueness rule.

## Bills are on a good track

I am fairly comfortable with the bill side.

GovInfo parsing already gives us separate typed concepts for:

```text
bill
bill identifiers
actions
sponsorships
committees
subjects
documents
```

rather than one giant JSON object.

And the actual save path writes that graph transactionally.

That's good design.

The next refinements should be historical rather than structural:

```text
cosponsor added date
cosponsor withdrawn date
original cosponsor
multiple titles
text/package versions
related bills
amendments
source corrections
```

Do not turn these into one generic political EAV table.

Add typed grains as the use cases demand them.

## Amendments, nominations and treaties should come later—but votes must tolerate them now

Congress.gov currently exposes endpoints for amendments and many other congressional entity families alongside bills, members, committees and House votes. ([GitHub][2])

I don't think we need to create twenty more tables tomorrow.

The better progression is:

```text
roll_call_reference
        ↓
can safely preserve:
bill / amendment / nomination / treaty / motion
        ↓
then create core.amendment
or core.nomination
when research requirements need them
```

That's exactly how we avoid rebuilding the giant overengineered project you were worried about.

## Your OpenStates strategy is now right

The right mental model is:

```text
OpenStates database
        =
replaceable provider snapshot

OpenDiscourse core/fact
        =
our stable research model
```

OpenStates/OCD gives us excellent language and proven concepts. We should absolutely borrow that language.

We should **not** make their Django/Postgres implementation our public schema.

That's what AD-8 now says, and PR #22 follows that direction.

For later state expansion, I would promote one jurisdiction/session at a time through reviewed contracts rather than immediately copying ~all states and every table merely because they're available.

## “Complete” needs a stricter definition

This is another thing I would fix before making OpenDiscourse publicly authoritative.

`congresshealth.py` currently has some hardcoded declarations such as:

```text
votes:
  118: complete
  119: partial
```

and organizations as complete.

“Complete” needs to mean:

```text
source
+ entity type
+ scope
+ time range
+ source manifest/version
+ as-of timestamp
+ validation rule
```

For example:

```text
OpenStates 118th federal vote snapshot:
complete relative to snapshot X

House Clerk 118th roll calls:
complete according to chamber manifest/count X

GovInfo BILLSTATUS 119:
complete as of snapshot timestamp Y
```

Those are defensible statements.

“118th votes complete” without saying **against what source definition** is not.

This becomes especially important once House Clerk + Senate LIS replace OpenStates as the federal vote acquisition baseline.

## Your testing/CI direction is good

I don't see a reason to change the basic testing strategy.

Current CI has:

```text
fast:
    locked uv env
    ruff + isolated pytest

database:
    PostgreSQL 17 / PostGIS
    baseline DDL fingerprint
    deterministic DB/integration tests
```

That's appropriate for this project.

The important new classes of tests I want are **research invariants**, not merely code coverage:

```text
same source bytes → same evidence
changed source bytes → new evidence version
external ID cannot silently move to another person
unresolved identity cannot be name-matched
member-vote totals reconcile with roll-call totals
canonical current value points at supporting evidence
old evidence remains queryable
rerun produces no duplicate semantic records
partial coverage can never be declared complete
```

Those tests are arguably more valuable than chasing 100% line coverage on every helper.

## Let me grill the design

These are the questions I think every future OpenDiscourse change should have to answer.

1. **What exactly identifies this thing?** If the answer is a display name, stop. We need a stable source ID or a documented unresolved identity.

2. **What is the grain?** One row must have an unambiguous meaning: person-term, member-vote, bill-action, district-year estimate, committee membership, etc.

3. **Can the source revise this later?** If yes, are we preserving the old evidence and the new evidence separately?

4. **Which source is authoritative for this particular field?** Not “which source wins globally?” GovInfo might be strongest for a package; House Clerk for a House vote; BioGuide for a federal person identity.

5. **What happens when two sources disagree?** The answer cannot be “last writer wins.” Store the disagreement, choose a reviewed canonical projection if needed, and retain both observations/evidence.

6. **Is time part of the identity?** Party affiliation, representation, committee membership, districts, Census geography, elected office, and disclosures almost always require time.

7. **Can I reproduce the answer six months from now?** If not, provenance isn't complete.

8. **Does schema existence authorize ingestion?** No. We already encoded this rule. A table being present is not permission to ingest unbounded data.

9. **Is this source data or analysis?** “Member voted Yea” belongs in `fact`. “Member usually votes with party” is a derived mart/model and needs methodology/versioning.

10. **Are we writing custom code when a maintained upstream project already solves acquisition?** If yes, we need a reason. `unitedstates/congress` already handles official bulk bill status, GovInfo files and House/Senate vote acquisition and is still maintained by GovTrack/community contributors.

Those ten questions would catch most of the ways this project could go wrong.

## What I actually changed today

I didn't just leave this as review prose.

I opened **PR #23 — `docs: harden political source and provenance contracts`**.

It:

* corrects the stale OpenStates-as-federal-canonical wording;
* defines source roles for GovInfo, Congress.gov, House Clerk, Senate LIS, `congress-legislators`, and OpenStates;
* explicitly says source conflicts remain inspectable;
* adds **Story 1.7: immutable artifact versions**;
* updates BMAD to reflect that Story 8.1 is already landed and Story 8.2 is PR #22;
* strengthens Epic 4's House/Senate vote acceptance criteria;
* removes a duplicated FR-20 traceability row;
* updates our next-build ordering.

PR #23 currently has successful CommitCheck, CodeRabbit and Qlty status, but **pre-commit.ci currently reports an error**, so I would not merge it blindly yet.

I also reviewed PR #22 and left a concrete provenance comment there instead of changing its branch behind the implementation work.

## Where I stand now

I would describe the project status this way:

**Architecture:** keep.

**Database choice:** keep PostgreSQL/PostGIS.

**BMAD:** keep.

**Alembic + dbt ownership:** keep.

**Connector concept:** keep and finish proving it.

**OpenStates strategy:** now correct.

**Political typed schema:** direction is correct.

**Identity strategy:** correct, but Story 3.1 becomes important soon.

**Political provenance:** concept correct, implementation needs the artifact-version fix.

**Vote model:** needs one more small expansion before I would call it research-grade.

**State/local scalability:** good foundation; don't bulk-promote everything yet.

**Need to restart:** absolutely not.

The biggest risk now is actually **adding too many new sources before finishing these invariants**, not architectural failure.

### The next sequence I would follow

1. **Finish PR #22 correctly**, tying OpenStates promotions to the real checksum-backed snapshot and making sure changed current values point to supporting current evidence.

2. **Merge the BMAD alignment from #23 after its check is clean.**

3. **Implement Story 1.6 + Story 1.7:** provenance contract tests and immutable artifact versions.

4. **Complete the Connector FRED vertical slice** (#18 → #20) without redesigning the protocol.

5. **Complete federal identity from `congress-legislators` / BioGuide**, including temporal term/party/caucus information.

6. **Implement Epic 4 votes from chamber-native evidence**, adding roll-call references and tally counts while retaining OpenStates as reconciliation.

7. **Build the first real `legislator_vote` mart** and prove that a researcher can go from member → seat → district → affiliation → vote → subject → source evidence.

8. Only after that, broaden aggressively into FEC/disclosures/elections/crime and the full state legislative universe.

If we can execute that sequence, then we will have proven the central thesis of OpenDiscourse once, end-to-end. At that point adding Census, FEC, disclosures, election results, crime, more state data, hearings, nominations, committees, and new connectors becomes **extension work rather than architecture invention**.

That is where I want this project to get. And based on what is actually in the repository now, **we are much closer to that point than to needing a restart**.

[1]: https://www.govinfo.gov/sitemaps?utm_source=chatgpt.com "Sitemaps | GovInfo"
[2]: https://github.com/LibraryOfCongress/api.congress.gov/blob/main/Documentation/openapi.json?utm_source=chatgpt.com "api.congress.gov/Documentation/openapi.json at main · LibraryOfCongress/api.congress.gov · GitHub"
[3]: https://docs.openstates.org/data/?utm_source=chatgpt.com "Understanding the Data - Open States"
[4]: https://clerk.house.gov/Votes/2026106?utm_source=chatgpt.com "Office of the Clerk, U.S. House of Representatives"
[5]: https://clerk.house.gov/Votes/2026258?utm_source=chatgpt.com "Office of the Clerk, U.S. House of Representatives"
[6]: https://www.senate.gov/legislative/LIS/roll_call_votes/vote1192/vote_119_2_00204.htm?utm_source=chatgpt.com "U.S. Senate: U.S. Senate Roll Call Votes 119th Congress - 2nd Session"
[7]: https://docs.openstates.org/api-v2/types/?utm_source=chatgpt.com "Data Types - Open States"
[8]: https://docs.openstates.org/api-v2/examples/?utm_source=chatgpt.com "Examples - Open States"
