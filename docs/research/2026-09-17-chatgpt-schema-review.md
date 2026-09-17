Yes — after reviewing the current OpenDiscourse schema, Alembic baseline, blueprint, BMAD canonical spec, architecture spine, PRD, scope document, and epics, **the project is on the right track**. More importantly, the architecture is substantially cleaner than the earlier versions of OpenDiscourse.

I would **keep this architecture and refine it rather than redesigning again**. There are a handful of inconsistencies and schema details I would fix now, before we pile more ingestion onto it.

## Overall assessment

The strongest decision you've made is this separation:

**source → immutable evidence → staging → canonical core/facts → marts → access**

The architecture spine states essentially that exact flow and makes Postgres/PostGIS authoritative while keeping immutable source artifacts outside the curated database.

The blueprint reinforces an equally important principle:

> don't create one gigantic generic JSON facts table; use typed grains for bills, votes, sponsors, GIS, measurements, etc.

That is exactly the direction I would recommend for a serious reusable research warehouse.

And your persistence layer has matured considerably. Alembic is now explicitly the canonical schema owner for `catalog`, `core`, `fact`, `ingest`, and `stage`, while the numbered SQL files are legacy/history.

So I would frame the current state as:

**Architecture: strong**
**Schema foundation: strong**
**BMAD structure: strong**
**Consistency between them: needs a cleanup pass**

---

# 1. The schema is fundamentally structured correctly

Your baseline has sensible bounded domains:

* `catalog` — what data exists / selections / plans
* `ingest` — execution and evidence
* `stage` — provider-shaped temporary/replaceable data
* `core` — durable identities/entities
* `fact` — analytical observations/events
* `mart` — researcher-oriented models
* `leg` — legislative compatibility/read surface

The baseline explicitly creates those schemas.

That gives us a much better foundation than either of the two extremes we previously discussed:

**Bad extreme #1:** reproduce every provider's database schema inside OpenDiscourse.

**Bad extreme #2:** normalize absolutely everything into a generic `entity / attribute / value` system.

You're now in the useful middle: preserve provider data before normalization, but promote well-understood concepts into domain-specific typed tables.

That is the right model.

---

# 2. OpenStates is being handled correctly now

I'm especially happy with this part.

The BMAD spec explicitly says:

* OpenStates remains a separate database.
* It is accessed read-only through FDW.
* OpenDiscourse doesn't mutate it.
* OpenStates/OCD identifiers are preserved.

And the OpenStates baseline migration makes the distinction explicit:

> these are Open Civic Data-compatible dimensions owned by OpenDiscourse, not copies of the OpenStates Django schema.

That's exactly what we wanted after reevaluating the project from first principles.

The `leg.*` compatibility views are also a clever boundary. They give applications a relatively stable legislative interface over both OpenStates data and OpenDiscourse-native data without requiring the upstream database to become your canonical warehouse.

**I would absolutely keep this design.**

---

# 3. Identity is being treated as a first-class architectural problem

This is probably the most consequential improvement in the whole design.

You have:

* `core.person`
* `core.person_identifier`
* `core.organization`
* `core.organization_identifier`
* `core.membership`
* OCD identifiers
* BioGuide identifiers
* explicit unresolved identity exceptions

And the BMAD architecture has the excellent constraint:

> Identity before money or crime.

That's important because otherwise we eventually wind up joining:

`"Robert Smith"` ↔ `"Bob Smith"` ↔ `"Robert J. Smith"`

and silently creating garbage political-finance relationships.

The BMAD PRD correctly says that federal member joining is done through BioGuide rather than names.

I would retain **internal UUIDs + external identifier tables** exactly as you have them.

That's much more extensible than making a BioGuide/OCD/FEC ID itself the physical primary key.

---

# 4. Provenance has become a real architectural invariant

This is another major strength.

The canonical BMAD spec requires loaded facts to resolve back to:

* ingest run
* source URL
* checksum/evidence

and the architecture explicitly declares provenance non-optional.

A lot of the canonical legislative tables enforce:

```text
source_artifact_id IS NOT NULL
OR
source_payload_id IS NOT NULL
```

For example, membership and legislative sessions do this.

Votes do too.

That's exactly what makes OpenDiscourse potentially valuable as a **research database**, rather than merely a collection of scraped data.

---

# 5. Typed fact tables are the correct move

This is another area where I think the schema has substantially improved.

You now have things such as:

* `fact.measurement`
* `fact.population_estimate`
* `fact.business_pattern`
* `fact.acs_bulk_estimate`
* `fact.decennial_dhc_value`
* `fact.member_vote`

rather than trying to jam Census, votes, population, business data, etc. into one universal observation structure.

Keep `fact.measurement` for things naturally represented as:

```text
dataset
field
geography
period
value
```

FRED/BLS/API-style statistical series fit that wonderfully.

But ACS bulk tables, votes, election results, donations, disclosures, crime, and other strongly structured datasets deserve specialized grains.

Your blueprint already expresses exactly this principle.

**Do not reverse this decision.**

---

# 6. The schema/BMAD mismatch I would fix first: duplicate legislative identity

There is one structural issue I would address before legislative ingestion gets much larger.

`core.bill` currently carries both:

```text
jurisdiction TEXT
legislative_session TEXT
```

and:

```text
legislative_session_id UUID
```

Likewise `core.roll_call` contains the legacy textual:

```text
jurisdiction
legislative_session
```

while also having:

```text
legislative_session_id
organization_id
```

You can see this transitional state in the current baseline.

This was completely reasonable while adopting the existing schema.

But long-term it creates the possibility that:

```text
bill.legislative_session = "119"
```

while its FK points at some other session.

### I recommend

Treat these textual columns as **legacy compatibility columns** now.

Eventually canonicalize:

```text
core.bill
    bill_id
    legislative_session_id FK
    identifier / bill_number
    classification
    title
    ...
```

and obtain jurisdiction through:

```text
bill
 -> legislative_session
 -> jurisdiction
```

Do something equivalent for `roll_call`.

You don't need to rip them out immediately. In fact I wouldn't.

But add a formal deprecation/adoption ADR so nobody builds new logic around both representations.

---

# 7. Tighten provenance consistency

Most provenance design is excellent, but the invariant isn't universally enforced yet.

For example, `core.geography_boundary` has:

```text
source_payload_id
source_artifact_id
```

but from the baseline I reviewed, it doesn't impose the same:

```sql
CHECK (
    source_artifact_id IS NOT NULL
    OR source_payload_id IS NOT NULL
)
```

that legislative sessions, memberships and votes use.

`core.document` similarly allows both evidence references to be absent.

Yet BMAD's AD-3 says provenance is not optional.

So we should decide one of two things:

**A.** Every canonical record must have direct evidence.

or

**B.** Some canonical objects may derive provenance transitively through another object/run.

I prefer **A for source-derived entities**, with carefully documented exceptions for system-generated entities.

Then enforce it consistently at the DB level.

---

# 8. There is a genuine BMAD/documentation inconsistency around crime

This one should be fixed.

`v1-scope.md` says:

**v1**

* identities
* TIGER
* legislation
* Census/housing
* FRED/Treasury/bounded BLS

and puts:

* FEC
* politician disclosures
* elections
* FBI/crime

into **v1.1**, blocked on identity.

The PRD agrees with that.

The epics agree with that too: Epic 7 is explicitly blocked on Epic 3.

But `docs/blueprint.md` still says in its initial delivery order:

> Add TIGER geography and an FBI agency/coverage loader, then ACS/PEP/BEA/BLS.

That's stale.

### Fix

Change the blueprint sequence so it agrees with BMAD:

```text
identity
→ legislation
→ TIGER/geography
→ Census/housing/economic
→ marts/access

then

→ FEC
→ disclosures
→ elections
→ crime
```

The BMAD version should win because it's newer and explicitly canonical.

---

# 9. The market/stock schema is another small specification mismatch

The canonical BMAD spec explicitly says:

> stocks are not an OpenDiscourse schema domain.

The PRD also lists quant/market functionality outside the product.

Yet the Alembic schema still contains:

```text
core.instrument
core.instrument_symbol
fact.market_bar
```

The persistence document also describes them as adopted.

This isn't dangerous, but the intent needs clarifying.

I would **not spend effort ripping them out**.

Instead document them as:

> legacy/general-purpose financial primitives retained for compatibility; not part of OpenDiscourse v1 product scope and no new ingestion work should target market-price functionality.

Later, investment disclosures can still refer to a security/instrument without OpenDiscourse becoming Bloomberg.

That distinction is actually useful:

```text
politician purchased AAPL
```

requires identifying the instrument.

It does **not** mean:

```text
download every AAPL daily market bar
```

belongs in OpenDiscourse.

---

# 10. `stage.fec_row` is okay, despite FEC being v1.1

You may notice the baseline already has:

```text
stage.fec_row
```

even though FEC is identity-blocked.

I don't consider that a problem.

A staging contract existing isn't the same thing as allowing FEC ingestion to run.

Your architecture says staging is provider-shaped and replaceable, while FEC **loads** are deferred.

I'd simply make that explicit in the relevant docs:

```text
Schema support != authorized ingest scope.
```

This is an important distinction for the whole project.

---

# 11. `api` needs clarification in the architecture

The architecture spine describes:

```text
ingest / stage / core / fact / mart / api
```

as the layer model.

But the current Alembic baseline creates:

```text
catalog
core
fact
ingest
stage
leg
mart
```

and not yet `api`.

This is not a schema failure because Epic 6.1 explicitly says PostgREST/API views are still a future story.

But change the architecture wording from:

> Layers map to schemas...

to something like:

> Target layers map to schemas... `api` is introduced by Epic 6.

That eliminates ambiguity for agents.

---

# 12. `mart` should remain dbt-owned

Your BMAD design says researchers should primarily interact with dbt marts such as:

* `district_year`
* `legislator_vote`
* bill timelines

rather than reconstructing research datasets manually.

I strongly agree.

I'd formalize the ownership boundary as:

```text
Alembic:
catalog
ingest
stage
core
fact

dbt:
mart

published SQL/views:
api

FDW compatibility:
leg
```

That's simpler than having both Alembic and dbt independently "own" mart objects.

---

# 13. I would strengthen geography before much more research data lands

Current geography is:

```text
geography_id
geography_type
geoid
name
parent_geoid
state_fips
county_fips
```

with vintage-aware boundaries.

The vintage boundary model is good.

But the conceptual question we should settle is whether:

```text
parent_geoid
```

should remain a loose string forever.

For serious longitudinal research, geography relationships get complicated:

* congressional districts change
* Census tract definitions change
* county subdivisions vary
* ZCTAs aren't strict administrative parents
* one geography can overlap another without being a parent

Long-term I'd introduce something like:

```text
core.geography_relationship

source_geography_id
target_geography_id
relationship_type
valid_from
valid_to
weight_population
weight_area
source_artifact_id
```

Not immediately—but this will eventually make the project dramatically more useful for longitudinal policy research.

---

# 14. The BMAD setup itself is quite good

I reviewed the relationship between:

**SPEC**
→ **architecture spine**
→ **PRD**
→ **v1 scope**
→ **epics/stories**

and it is mostly coherent.

The canonical spec is appropriately small. It defines seven capabilities rather than becoming another enormous requirements dump.

The architecture turns them into seven explicit architectural decisions.

The PRD converts those into FR-1 through FR-19.

And the epics contain a traceability table from FRs to implementation epics.

That's good requirements engineering.

I would **not add another specification framework**.

BMAD + ADRs + inventory/contracts is enough.

---

# 15. One small PRD cleanup

There's a stale persona/name in the PRD:

> “Chris runs `research-db plan-due`...”

That should simply say:

> “The operator runs…”

That's minor, but these kinds of remnants confuse coding agents later.

---

# 16. Persistence documentation itself is stale

`docs/persistence-migration-status.md` says:

> Last verified: 2026-08-19

while the BMAD architecture/spec were finalized September 14.

The persistence document contains a lot of authoritative-sounding state, so I would update/revalidate it now rather than allowing two different generations of "current truth."

---

# What I would change now

I would do **one focused alignment PR**, not another architectural rewrite:

1. **Resolve spec drift**

   * Blueprint FBI ordering → match v1/v1.1.
   * Explain retained market tables.
   * Explain `stage.fec_row`.
   * Clarify `api` is target/future.
   * Replace stale “Chris” persona.
   * update persistence verification date.

2. **Create a Schema Invariants ADR**
   Define:

   * canonical UUID vs external IDs
   * direct provenance requirement
   * staged vs canonical ownership
   * historical/vintage rules
   * idempotency keys
   * schema ownership by Alembic/dbt/FDW
   * no name-based entity reconciliation

3. **Clean up transitional legislative identity**
   Mark the textual `bill.jurisdiction`, `bill.legislative_session`, and equivalent `roll_call` fields as compatibility/deprecated and establish the eventual FK-only model.

4. **Audit provenance constraints**
   Programmatically inspect every `core` and `fact` table and classify it:

   * source-derived → evidence mandatory
   * derived → derivation lineage mandatory
   * reference/system-generated → documented exception

5. **Add schema contract tests**
   Don't just test migrations execute. Test invariants such as:

   ```text
   source-less membership → rejected
   source-less vote → rejected
   duplicate external person ID → rejected
   duplicate artifact row → rejected
   invalid embedding dimensions → rejected
   historical TIGER boundary preserved
   ```

---

# Where I think we are

I would **stop revisiting the fundamental architecture now** unless new evidence exposes a real limitation.

Earlier, I was worried OpenDiscourse was growing into a giant collection of sources, custom crawlers, schemas, agents, databases, and abstractions without a stable center.

It has a center now:

```text
                 INVENTORY / CONTRACTS
                         │
                         ▼
SOURCE ──► CONNECTOR ──► EVIDENCE
                         │
                         ▼
                       STAGE
                         │
                   reviewed transform
                         │
              ┌──────────┴──────────┐
              ▼                     ▼
             CORE                  FACT
              │                     │
              └──────────┬──────────┘
                         ▼
                        MART
                         │
                 ┌───────┴───────┐
                 ▼               ▼
                API        DuckDB/Parquet
```

And orthogonally:

```text
OpenStates DB
     │
 read-only FDW
     ▼
openstates_source
     │
     ├──► reconciliation → core/fact
     │
     └──► leg compatibility views
```

That is a coherent architecture.

### The most important thing from here

**Don't expand horizontally yet.**

I would resist adding FEC, crime, disclosures, elections, DOJ, etc. until the current vertical slice is proven:

```text
source
→ connector
→ evidence
→ stage
→ canonical identity
→ canonical fact
→ dbt mart
→ researcher query
```

For example:

```text
Congress/GovInfo/OpenStates
        ↓
bill/person/session/roll-call
        ↓
legislator_vote mart
        ↓
actual research query
```

Once **one complete slice** works beautifully, adding Census, FEC, crime, housing, economics, and everything else becomes repetitive rather than architectural experimentation.

So yes: **we are on the right track.** I would approve the current architectural direction, but I would do the alignment/invariant cleanup above **before calling the schema and BMAD artifacts fully settled**.
