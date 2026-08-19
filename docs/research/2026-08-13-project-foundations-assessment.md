# Project Foundations Assessment: Data Models, Database Engines, and Python Data-Access Patterns

Date: 2026-08-13
Status: Assessment only — no decisions made, no changes implemented, per explicit request.

## Why this document exists

The request behind this research: set aside every existing project convention and evaluate, from first principles, whether OpenDiscourse's foundational choices (PostgreSQL/PostGIS, raw `psycopg3` SQL in Python, the current schema shape) are actually the right ones — or whether this project is reinventing wheels that credible political-research infrastructure elsewhere has already built and proven. This is that evaluation. It makes recommendations but commits to nothing; every finding below is sourced and can be checked.

## 1. What comparable institutions actually do

This is the most important, and most humbling, finding: **almost none of the organizations that plausibly compare to this project publish a real architecture writeup.** Some initial candidates turned out not to be comparable at all. Here's the honest landscape, organized by how relevant each turned out to be.

### Directly comparable (civic-tech legislative data platforms)

| Project | Data model | Stack | What it tells us |
|---|---|---|---|
| [GovTrack](https://www.govtrack.us/) | Custom relational schema, OCD-adjacent | Django/Python | 20+ years running this exact domain (bills, votes, members) on a conventional relational DB. |
| [OpenStates / Plural](https://docs.openstates.org/) | Open Civic Data (OCD)-based | Django/Python, relational | Still Django + relational after the 2024 rebrand to Plural; the underlying data model hasn't changed. |
| [Voteview](https://voteview.com/) | Flat tabular (ICPSR IDs), not even a live app DB | Flat CSV/Stata distribution | The single most analytically sophisticated dataset in political science (DW-NOMINATE) ships as flat files, not a graph or exotic store. |
| [LegiScan](https://legiscan.com/) | Relational, per-session snapshots | — | All-50-states equivalent; weekly relational snapshots, not streaming/real-time infra. |
| **[mySociety](https://www.mysociety.org/) / [TheyWorkForYou](https://github.com/mysociety/theyworkforyou) / Pombola** (new this pass) | **[Popolo](http://www.popoloproject.com/) open standard** | Open source, self-hostable | UK/international parliamentary-monitoring equivalent of OpenStates. Popolo is the broader open standard that **Open Civic Data (OCD) — which this project's schema already targets — is closely related to.** A third independent region/org, same conclusion: standards-based relational modeling, not something exotic. |

**This is now a three-for-three finding** (US civic tech, and now international parliamentary monitoring): every real, actively-used, comparable system in this exact problem space — people, bills, votes, geography — uses a relational or flat-tabular model aligned to an open civic-data standard (OCD or Popolo). None uses a graph database, a NoSQL document store, or an exotic analytical engine as its system of record.

### Turned out not to be comparable (worth reporting honestly, not silently dropping)

- **ICPSR** (the world's largest social-science data archive) is an **archival file repository**, not a live queryable research database. It follows the OAIS preservation standard and distributes data as SAS/SPSS/Stata files for researchers to load into their own tools. Different problem: long-term preservation and distribution, not active cross-source querying.
- **MIT Election Data and Science Lab (MEDSL)** is similarly a **data-distribution project** (flat files + an R package), not an architecture to emulate for a live warehouse.
- **Quinnipiac University Poll and Marquette Law School Poll** — these are **telephone/online survey polling operations** (CATI phone banks, SSRS survey panels). They have nothing to do with legislative/geographic/demographic data linkage; naming them as comparables was a reasonable guess but doesn't hold up. Flagging this explicitly rather than force-fitting a connection.
- **Urban Institute** (policy research, Tax Policy Center) leans heavily on **R and Spark** (their `spark-social-science` project provisions AWS EMR clusters for RStudio/PySpark) for the *analysis* layer, and distributes data via R/Stata packages. This is a genuinely different point in the landscape: a serious, well-funded policy shop choosing R + Spark for analysis rather than Python + Postgres — but this is about their analysis/notebook layer, not evidence about how to structure a queryable warehouse.
- **NCSL** (National Conference of State Legislatures) — no published technical architecture found at all; they appear to run internal databases without public documentation.

**Bottom line for this section:** there is no missed "reference architecture" out there that this project should have copied. The actual credible prior art (GovTrack, OpenStates, mySociety/Popolo) already validates the relational/OCD-standard approach this project has taken. The gap isn't architecture — it's that this project hasn't been using a couple of specific tools that make that architecture easier to work with (see below).

## 2. Python data-access layer: does "raw SQL in Python" need to change?

Current state: this project uses `psycopg3` (the modern, actively-developed PostgreSQL driver — psycopg2's successor) with hand-written SQL, some inline as Python strings, some already pulled into separate `.sql` files under `sql/query/<area>/` and loaded at runtime (`repositories/legislation.py`'s `_query()` helper does this). So the project is not 100% "raw SQL in Python" today — it already has a partial pattern of separating SQL into files. The question is whether to go further, and how.

| Approach | What it is | Fit for this project |
|---|---|---|
| **Raw psycopg3** (current) | Direct driver, you write SQL, get rows back. No abstraction. | Full control, zero dependency weight, but SQL strings inline in Python are genuinely easy to typo, hard to statically check, and don't give autocomplete/type safety. |
| **SQLAlchemy ORM** | Maps Python classes to tables; `session.query(Bill).filter(...)`. | Biggest paradigm shift of any option here — would mean redesigning how every module touches the database. Given every comparable project (GovTrack, OpenStates) uses Django's ORM successfully, this isn't a fringe idea, but it's a rewrite, not an incremental fix. |
| **SQLAlchemy Core** | The *query builder* half of SQLAlchemy, without the ORM's class-mapping — you write `select(bills).where(...)` in Python instead of SQL strings, but there's no "Bill object," just table/column references. | A real middle ground: solves "SQL strings in Python" without a full ORM rewrite. Verified tradeoff from research: built-in SQL-injection protection via automatic escaping, cross-database portability (not needed here, but free), a small performance overhead (generally inconsequential outside very hot paths). |
| **sqlc** (new finding, real production tool) | You write SQL in plain `.sql` files — which this project *already does* for some queries — then run a generator that produces typed Python functions/dataclasses matching each query's actual input/output shape, validated against the real schema at generation time. | **The most natural fit given what's already in place.** It doesn't ask you to stop writing SQL — it takes SQL you're already writing in files and makes it type-safe and typo-proof automatically. Confirmed: supports `psycopg3` directly (the exact driver already in use), and benchmarks show it performs within 1-2% of hand-written SQL — "an order of magnitude faster than heavy ORMs" for cases where that matters. |
| **ibis** | A Python dataframe API that compiles to SQL for 20+ backends (Postgres, DuckDB, ClickHouse, BigQuery, etc.) via SQLGlot. | This is really a data-*science* interface (pandas-like) rather than an application data-access layer — better suited to an analysis notebook than to `research-db`'s ingestion/persistence code. Relevant if this project grows a serious ad-hoc-analysis workflow, not as a replacement for the ingestion layer's DB access. |

**Assessment:** the complaint "raw SQL in Python is sloppy" has a real, well-evidenced, *low-disruption* answer — **sqlc** — that builds on what the project already partially does (separate `.sql` files) rather than requiring a rewrite. SQLAlchemy Core is the next-most-natural option if a pure-Python query-building style (no separate `.sql` files at all) is preferred instead. A full SQLAlchemy ORM migration is the most disruptive option and would essentially be a from-scratch rewrite of every repository module — not something to take lightly even though it is what GovTrack/OpenStates themselves use (via Django, a bigger framework commitment than SQLAlchemy alone).

## 3. Database engine: is PostgreSQL/PostGIS actually the right choice?

Given the explicit instruction to not assume anything, this got checked directly against the project's real workload: heavy geospatial operations (district boundaries, ZIP-crosswalk overlaps, GIST-indexed polygon queries) plus a need for real transactional/provenance guarantees (every ingestion run recorded, idempotent re-runs, foreign-key integrity across dozens of related tables).

| Engine | What it's actually good at | Verdict for this project's core system |
|---|---|---|
| **PostgreSQL/PostGIS** (current) | Mature ACID transactions, concurrent multi-writer access, the most mature open-source geospatial SQL support of any system, KNN/nearest-neighbor spatial queries. | **Confirmed as the right choice for the system of record.** Direct, sourced finding: "PostGIS is usually the better fit for applications and long-lived shared geospatial systems," while DuckDB's spatial extension is explicitly described as "still maturing" by comparison, better suited to local/lightweight analytical work. |
| **DuckDB** | Extremely fast *local, embedded, single-machine* analytical queries (16-26x faster than Postgres for analytical workloads in one benchmark), zero setup, reads Parquet/GeoParquet natively. No concurrent multi-writer story, weaker geometry/SRID model than PostGIS. | **Not a replacement for the core system** — but a strong candidate as a *complementary* tool for ad-hoc local analysis (e.g., exporting a research question's data to Parquet and exploring it fast in a notebook) without touching the production database. |
| **ClickHouse** | Distributed, large-scale, real-time analytics; excellent compression; built for scale this project doesn't have (billions of rows, streaming ingestion, many concurrent analytical users). | Wrong shape for a personal/small-team project with the data volumes here (thousands to low millions of rows per table, not billions). Real operational overhead (distributed cluster) for no corresponding benefit at this scale. |
| **MySQL** | Solid general-purpose relational DB. | No compelling advantage over Postgres here, and materially weaker geospatial story than PostGIS — this would be a straightforward downgrade for this project's specific geospatial-heavy workload. |

**Assessment:** this is the one area where the evidence most clearly says "what you're already doing is correct," not because of inertia but because the workload (concurrent, transactional, geospatially complex, provenance-tracked) is close to a textbook case for PostGIS specifically. The genuinely interesting idea worth keeping in mind is DuckDB as an *additional*, complementary tool for fast local analysis — not a replacement.

## 4. Skills, plugins, and MCP servers for this kind of work

Covered and partly acted on in the prior research pass (see `docs/research/2026-08-13-district-geography-linking-evaluation.md`); summarized here for completeness:

- **Installed:** `census-geocoding` MCP (address/coordinate → Census geography, including congressional district), `postgres` MCP (direct schema/query access, via `@microsoft/postgres-mcp`), `openfec` MCP (FEC campaign-finance data, for the future FEC sub-project), `geosql` skill (PostGIS-aware agent skill with map-rendering, installed telemetry-off/no-cloud).
- **Identified, not installed:** the official U.S. Census Bureau Data API MCP server (needs Docker + a Census API key — both now becoming available).
- **Checked and rejected:** a dedicated GitHub MCP server (redundant with the `gh` CLI already in use), and several "PostGIS Claude Code skill" listings from unvetted marketplace-aggregator sites (couldn't verify their quality or authorship the way `openstates/people` or the Census Bureau's own repo could be verified).

No skill or MCP server was found this pass that changes the schema/architecture conclusions above — the tooling landscape mainly affects *how convenient* the work is, not *what the right foundational choices are*.

## 5. Addendum: direct answers to follow-up questions

### Does OpenStates use sqlc? Is OpenStates "outdated"?

No — OpenStates/Plural uses **Django's ORM**, not sqlc (confirmed: "the application is built in Django," per `blog.openstates.org`). And no, Django is not outdated: it's actively maintained, still the dominant choice for full-stack Python web apps in 2026, and its ORM is considered mature rather than legacy. The nuance worth knowing: **FastAPI has overtaken Django in raw popularity for pure API layers** (38% vs. 35% adoption per the 2024 JetBrains Python survey) — but FastAPI doesn't ship an ORM at all; it's a different category of tool (an API framework, not a full-stack framework with a database layer built in). OpenStates using Django isn't evidence of an outdated approach — it's evidence of a mature, boring, working choice, the same conclusion as the rest of this research.

**This means "imitate what OpenStates does" and "use sqlc" point in different directions** — OpenStates' actual answer to "raw SQL is sloppy" is "commit to a full ORM (Django's)," not "add a lightweight code generator (sqlc)." Worth being explicit about that tension rather than blurring it.

### What sqlc actually does, concretely, on this project's real code — not an abstract pitch

Here is real code from `src/opendiscourse_research/browser.py`, `sync_acs()`, exactly as it exists today:

```python
cur.execute(
    """INSERT INTO catalog.resource
       (dataset_id, resource_key, resource_type, title, summary, universe, release_year, metadata)
       VALUES ('census.acs_5', %(key)s, %(type)s, %(title)s, %(summary)s, %(universe)s, %(year)s, %(metadata)s)
       ON CONFLICT (dataset_id, resource_key) DO UPDATE SET ...""",
    {"key": ..., "type": ..., "title": ..., ...},
)
```

Nothing here checks, before you run it, that `catalog.resource` actually has a `universe` column, that `%(year)s` is really an integer, or that the dict you pass has every key the query needs. A typo in a column name, or a renamed column during a future migration, surfaces only at runtime, potentially only when that exact code path executes in production. This is the concrete shape of "raw SQL in Python is sloppy."

With sqlc, the same SQL lives in a `.sql` file (this project already does this in `sql/query/`, just not everywhere):

```sql
-- name: UpsertACSResource :exec
INSERT INTO catalog.resource (dataset_id, resource_key, resource_type, title, summary, universe, release_year, metadata)
VALUES ('census.acs_5', :resource_key, :resource_type, :title, :summary, :universe, :release_year, :metadata)
ON CONFLICT (dataset_id, resource_key) DO UPDATE SET ...;
```

Running `sqlc generate` reads this file **and the real database schema**, and produces a typed Python function — something like `upsert_acs_resource(conn, resource_key: str, resource_type: str, title: str, ...) -> None`. If `catalog.resource` doesn't have a `universe` column, generation fails immediately, before the code ever runs. If someone later renames a column in a migration, the next `sqlc generate` fails loudly instead of the bug waiting to be discovered at 2am during a real ingestion run. You keep writing exactly the SQL you already know how to write — sqlc doesn't ask you to learn a query-building API — it just stops trusting you to have spelled everything correctly.

This was a real recommendation, not something said to end the conversation. The honest caveat: it's a smaller, less-adopted tool than SQLAlchemy (real production usage exists, but a much smaller community and ecosystem), and it's a build-step tool (you regenerate code when schema or queries change) rather than something that runs at import time like an ORM does.

### dlt / Prefect / Airflow — these are two different layers, and the project already tried one of them

Worth separating clearly, because the original question ("dlt, prefect, airtable, or some heavy duty data ingestion program") blends two different jobs:

- **dlt** is an *extraction-and-load library* — code that pulls data from a source and writes it into a destination table, handling schema evolution and incremental loading for you.
- **Prefect / Airflow** are *orchestrators* — schedulers that decide *when* and *in what order* jobs run, retry failures, and give you a dashboard. They typically **call** tools like dlt, not replace them. (Confirmed directly: "Airflow triggers extraction and loading, kicking off tools like dlt... to pull data from source systems into the warehouse.")

**This project already has `dlt[postgres]` declared as an optional dependency** (`pyproject.toml`'s `ingest` extra) and mentions it conceptually in `docs/framework.md` ("`dlt` is optional staging machinery rather than the canonical database model") — **but it is not imported or used anywhere in the actual source code.** It was considered, declared, and never adopted. That's a genuine, concrete "trim the fat" candidate on its own: either actually use it somewhere, or stop declaring an unused dependency.

**Should it be adopted for real, or should Prefect/Airflow be added?** Honest read: this project's hand-rolled ingestion system (`ingestion/*.py`'s plan → preview → approve → download → stage → load pattern, with `IngestionRun` provenance tracking, the capacity-preview gate before bulk downloads, and reviewed YAML contracts gating what's allowed to run) already does something **more specific and more safety-conscious** than what dlt or Prefect give you out of the box — those tools are built around "move data reliably and observably," not "require an explicit, version-controlled, human-reviewed contract before a bulk download is allowed to start," which is this project's actual, deliberate design principle (see `docs/framework.md`'s staging/promotion rules). Swapping in a generic tool would mean either losing that safety-gate behavior or re-implementing it on top of the generic tool anyway — at which point the generic tool isn't saving the work it promises to.

If an orchestrator is wanted for *scheduling* (not extraction) — the project already has a lighter-weight answer in place: `research-db plan-due` run via cron/systemd timers (`ops/systemd/`). If that outgrows cron, **Prefect, not Airflow**, is the evidence-backed fit for a solo/small-team project — confirmed directly: "Prefect works well for solo projects because it's Pythonic... no server needed," while "Airflow tends to be heavier for small-scale projects," requiring dedicated scheduler infrastructure this project doesn't otherwise need.

### "Trim the fat" — `browser.py`, evaluated directly

Read the actual file (1,154 lines) rather than describing it abstractly. Verdict: **the capability is real and worth keeping, but the file is doing three jobs that should be three files.**

1. **Catalog-promotion logic** (`sync_acs`, `sync_fred`, `sync_fred_full`, ~250 lines) — business logic that promotes discovered metadata into the reusable catalog. Contains the rawest inline SQL in the project (the `sync_acs` example above).
2. **Catalog API** (`search`, `facets`, `providers`, `datasets`, `get_resource`, `toggle`, `basket`, `draft`, ~230 lines) — the functions `cli.py`'s `catalog-search`/`catalog-basket`/`catalog-draft` subcommands call.
3. **The actual interactive TUI** (`launch`, ~540 lines) — a real `textual`-based terminal app with 13 keybindings (select, write draft, write bulk plan, fetch, refresh, etc.). This is genuinely the documented flagship UX (`research-db browse` is literally step one of the README's Quick Start) — not dead code, not something to delete.

**Test coverage:** only one function (`acs_package_tables`) is exercised, indirectly, by `tests/test_census_bulk.py`. The other ~19 functions — including all the catalog-promotion SQL and the entire TUI — have zero test coverage. That's a real gap independent of any SQL-layer decision.

**Recommendation shape (not a decision):** split into three focused files along those three responsibilities, and add real test coverage to the promotion/API logic (the TUI itself is harder to unit test meaningfully and is lower priority). This is a good candidate to fold into the same pass as whichever SQL-access-layer choice gets made, since the promotion functions are exactly where that choice would show up first.

## 6. What a full SQLAlchemy conversion would actually mean for this codebase

Measured directly, not estimated: **25 of ~52 Python source files, 142 separate `cursor.execute()`/`conn.execute()` call sites**, touch the database directly today. Roughly half the codebase. This is the real size of the migration, not an abstract one.

**Two flavors, both viable, different tradeoffs:**

- **Plain SQLAlchemy 2.0 ORM** — define a `Mapped`/`mapped_column` class per table (~30 tables per the schema), matching Django's approach (what OpenStates actually uses, architecturally, just a different ORM).
- **SQLModel** — a thinner layer that makes each model class *both* a Pydantic model and a SQLAlchemy table mapping in one definition. This project already depends on Pydantic (`pydantic>=2.7`, currently only for config via `pydantic-settings`) — SQLModel would extend that existing investment to data records too, rather than maintaining two separate systems (Pydantic for config, something else for data). Confirmed actively used in production as of this year, migrations handled via Alembic (SQLModel wraps Alembic rather than replacing it).

**Geometry columns are not a blocker either way.** GeoAlchemy2 (confirmed mature, actively maintained) adds PostGIS geometry/geography support to SQLAlchemy, and integrates directly with Shapely — which this project already depends on via its `spatial` extra. The `core.geography_boundary.geom geometry(Geometry, 4326)` column and its GIST index would carry over cleanly.

**Migrations become a real decision point.** Right now this project's migrations are hand-written `sql/NNN_name.sql` files, applied directly. Adopting SQLAlchemy models conventionally means adopting **Alembic** alongside them (it can autogenerate migrations by diffing your models against the live schema) — which means either running Alembic *and* keeping the existing numbered-SQL-file convention in sync by hand (real ongoing duplication risk), or fully switching migration authorship to Alembic and treating the model classes as the source of truth instead of the SQL files. That's a bigger structural decision than just "how do I write queries" — it changes what the source of truth for the schema *is*.

**One honest caveat that cuts against the ORM being an obvious win here:** this project's persistence code is upsert-heavy (`INSERT ... ON CONFLICT DO UPDATE`, used constantly for idempotent re-ingestion — the exact `sync_acs` example above is one of dozens). In SQLAlchemy, a Postgres-specific upsert requires the dialect-specific `sqlalchemy.dialects.postgresql.insert()` construct plus `.on_conflict_do_update(...)`:

```python
stmt = pg_insert(CatalogResource).values(dataset_id="census.acs_5", resource_key=key, ...)
stmt = stmt.on_conflict_do_update(
    index_elements=["dataset_id", "resource_key"],
    set_=dict(resource_type=stmt.excluded.resource_type, title=stmt.excluded.title, ...),
)
session.execute(stmt)
```

This is not obviously shorter or clearer than the raw SQL version — arguably it's *more* ceremony for exactly the pattern this project uses most. This is a real, honest tradeoff, not a reason to avoid SQLAlchemy, but the case for it here rests more on schema-typo safety, IDE autocomplete, and long-term maintainability than on the code becoming visibly shorter or simpler for this project's specific, upsert-heavy style.

## 7. Synthesis

Three independent research passes (US civic tech, international parliamentary monitoring via mySociety/Popolo, and this pass's deeper look at academic/policy-research infrastructure) all converge on the same architectural answer: **a relational, standards-aligned (OCD/Popolo) schema is what real, proven, long-running systems in this exact domain use.** This project's core choice — PostgreSQL/PostGIS with an OCD-aligned schema — is not a case of reinventing the wheel; it's the same wheel everyone else in this space uses. That question is settled by the evidence, independent of anything below.

The Python data-access-layer question is genuinely open, and the evidence supports two different real answers rather than one:

- **`sqlc`** is the lower-disruption path — it builds directly on the `.sql`-file convention this project already partially uses, keeps `psycopg3`, and fixes the concrete typo/schema-drift problem demonstrated on real code above (§5). Its weakness is that it's a smaller, less-proven tool with a much smaller ecosystem than SQLAlchemy, and it's a build-step generator rather than something living examples like OpenStates actually run in production.
- **SQLAlchemy (plain ORM or SQLModel)** is the higher-disruption path — a real ~25-file, 142-call-site migration (§6), plus a migrations-tooling decision (Alembic vs. the existing `sql/NNN_name.sql` files), plus a real caveat that this project's upsert-heavy style doesn't get obviously simpler under an ORM. Its strength is that it's architecturally what the closest real comparable (OpenStates, via Django's ORM) has actually proven works at real production scale over years — not a smaller or less-tested choice, just a bigger one.

Both are legitimate. The honest tradeoff is disruption-now vs. proven-at-scale, not "one of these is obviously wrong." `browser.py` (§5) is a good, independent example of exactly where either choice would show up first if a decision gets made. `DuckDB` remains worth keeping in mind as a future complementary tool for fast local analysis, never as a replacement for the transactional core (§3).

Nothing here has been implemented. This is offered as the assessment requested — the next step, if any, is yours to choose.

## 8. Addendum: rewrite-from-scratch, the upsert problem, and the browser tool

### Should this be rewritten from scratch instead of migrated incrementally?

The classic, credible answer here is Joel Spolsky's 2000 essay ["Things You Should Never Do, Part I"](https://www.joelonsoftware.com/2000/04/06/things-you-should-never-do-part-i/), still widely cited: rewriting a working application from scratch is "the single worst strategic mistake" a team can make, because "the crufty-looking parts of an application's codebase often embed hard-earned knowledge about corner cases and weird bugs" — knowledge that took real-world usage, sometimes years, to discover, and that a rewrite silently throws away. His go-to cautionary example, Netscape, spent years on a from-scratch rewrite and the company died waiting for it. (Fair to note: this essay is 25 years old and has real, credible counterarguments — sometimes a rewrite is right, particularly when the *domain understanding* itself was wrong. That's the key test.)

**Does that test apply here?** No — and that's the important distinction. This research has independently validated that this project's domain model (OCD-aligned schema, provenance-first design) is *correct*, matching what every real comparable system in this space actually does. The thing in question isn't "we understood the problem wrong" — it's "how does Python talk to Postgres." That's a plumbing-layer question, not a domain-understanding one. A full rewrite would be the Spolsky mistake: throwing away real, working, tested logic (concretely: 64 passing tests today, several encoding genuinely hard-won edge cases — BILLSTATUS XML sponsor/cosponsor parsing quirks, the capacity-gate storage-preview math, OpenStates vote-resume cursor logic, the malformed-`sources.yaml` handling fixed earlier this session) to solve a problem that only touches how ~25 files execute queries.

**The lower-risk framing:** migrate module by module, keeping the existing test suite as the safety net at every step — not "start over," but "swap the layer underneath code that's already proven correct, one file at a time, without ever having a broken state." That's a fundamentally different risk profile than a from-scratch rewrite, even though both involve touching a lot of files.

### Is a rewrite actually easier for an AI agent, since it already knows the intended output?

Partially true, and worth being honest about which part. Yes — generating new code that *looks* correct is fast for an AI agent; that's not the bottleneck. What's *not* automatically preserved just because the agent "understands" the target behavior in the abstract is the specific, hard-won edge-case correctness described above — things like "this XML field is sometimes absent and must not raise," discovered through real iteration, not through reading a spec. The tests are literally the artifact that captures that knowledge. The good news: those tests need to keep passing regardless of which path is chosen, so they're not wasted effort either way — and an incremental, test-gated migration isn't slower for an AI agent than a rewrite would be; it's the same amount of file-touching, just with a safety net confirming nothing broke after each step instead of trusting that a fresh rewrite reproduced every edge case correctly. There's no real efficiency argument for skipping the safety net.

### Is there a better solution to the upsert/idempotency pattern than what was shown?

Real finding, and it's a genuinely useful one: **Django itself only got a clean, one-query upsert in version 4.1 (2022)** — `bulk_create(prices, update_conflicts=True, unique_fields=[...], update_fields=[...])`. Before that, Django ORM users hit the exact same awkwardness being weighed here. This confirms the upsert-in-an-ORM friction is a **general, well-documented ORM-world problem, not a SQLAlchemy-specific flaw** — even the ORM that OpenStates itself uses had this exact gap for over a decade. Separately confirmed: SQLAlchemy's current `on_conflict_do_update` has a known real limitation — Column-level `onupdate` defaults don't fire automatically and need manual handling — and no widely-adopted third-party library was found that smooths this over.

Three honest options, not a recommendation:
1. **Accept SQLAlchemy's upsert syntax as-is.** It's more verbose than raw SQL for this pattern, not broken.
2. **A deliberate hybrid:** use SQLAlchemy/SQLModel for straightforward reads and simple writes, but keep upsert-heavy ingestion code on raw SQL or sqlc specifically — using each tool where it's actually strongest, rather than forcing one tool to cover every pattern equally well.
3. **Reopen Django specifically for its ORM**, since `bulk_create(update_conflicts=True)` is now genuinely cleaner than SQLAlchemy's equivalent for this exact pattern — though adopting Django only for its ORM (not its web framework, templating, or admin, none of which this project needs) is an unusual, heavier commitment just to get nicer upsert syntax, and worth naming as a real but odd-fit option rather than a clear win.

### Should `browser.py` be kept, or is a better off-the-shelf tool out there?

Checked directly: **[Datasette](https://datasette.io/)** (Simon Willison's well-known, credible open-source tool) instantly turns a database into a browsable website + API — the closest real "don't reinvent this" candidate. Two honest limits on using it here: it's historically **SQLite-native**, with Postgres support existing but bolted-on/less mature (via plugins or bridging tools like `db-to-sqlite`), not a first-class experience the way it is for SQLite. More importantly, **Datasette has no concept of this project's actual workflow** — selecting resources into a named basket, then writing a reviewed bulk-download plan file for explicit approval before any large download starts. That's this project's own deliberate safety/provenance behavior, not something any generic data-browsing tool provides, because no generic tool is designed around "gate bulk access behind a human-reviewed plan."

**So the honest split:** the TUI *framework* choice (`textual`) is already the right "use what's proven" answer — that's the actual off-the-shelf library doing the heavy lifting, and it's a well-regarded, actively maintained choice for exactly this kind of rich terminal app. What's custom on top of it is the basket/draft/bulk-plan workflow, and that would need to be hand-written no matter what browsing tool sits underneath, because it's specific to this project's design. **Not stupid, not a waste of time** — but, as flagged in §5, the file mixing three responsibilities together with almost no test coverage is a real, separate problem worth fixing regardless of which SQL-layer path gets chosen.
