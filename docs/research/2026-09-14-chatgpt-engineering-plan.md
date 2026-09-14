Yes. I think this is the correct next phase for OpenDiscourse: **stop adding domains for a little while and make the repository itself exceptionally good at being developed by humans + AI agents**.

Your current `AGENTS.md` already has good principles around provenance, testing, persistence boundaries, commits, documentation, and agent delegation. What it lacks is an executable process: what artifacts get created, in what order, when a spec is required, which tests run when, what an agent must verify before declaring success, and what GitHub enforces.

There is also a lot we can improve without making development slower. Your current `pyproject.toml` already has a strong base—`uv`, pytest, Hypothesis, Polyfactory, Ruff, testcontainers, PostGIS tooling—but it does not yet have parallel pytest execution or a static type checker.  And your GitHub setup currently has a single workflow and no repository rulesets, so there's considerable room to make GitHub work harder for us.

# 1. The development methodology I recommend

There are a lot of fashionable names in AI software development right now. We should borrow the useful concepts without turning OpenDiscourse into a process-management experiment.

| Practice                          | What it means                                         | OpenDiscourse decision                                   |
| --------------------------------- | ----------------------------------------------------- | -------------------------------------------------------- |
| **Spec-Driven Development (SDD)** | Define intended behavior before implementation        | **Primary workflow**                                     |
| **TDD**                           | Write failing tests before implementation             | **Use for deterministic behavior and bugs**              |
| **BDD**                           | Express requirements as scenarios/acceptance behavior | **Use inside specs**                                     |
| **ADRs**                          | Permanent records of architectural decisions          | **Use for important architecture/schema decisions**      |
| **RFCs**                          | Larger proposals that need discussion before approval | Use only for large/cross-cutting changes                 |
| **Trunk-based development**       | Main stays releasable; short-lived branches           | **Yes**                                                  |
| **Docs-as-code**                  | Docs versioned/reviewed beside implementation         | **Definitely**                                           |
| **Data contracts**                | Explicit schema/grain/provenance expectations         | **Core OpenDiscourse practice**                          |
| **Property-based testing**        | Generate many input cases automatically               | **Yes; Hypothesis is already installed**                 |
| **Contract testing**              | Verify adapters conform to shared interfaces          | **Very important for connectors**                        |
| **Risk-based testing**            | Test depth depends on change risk                     | **Central to keeping CI fast**                           |
| **Mutation testing**              | Check whether tests actually catch broken behavior    | Nightly/periodic, not every PR                           |
| **Continuous delivery**           | Main is always deployable                             | Yes, once packaging stabilizes                           |
| **GitOps**                        | Declarative infrastructure controlled from Git        | Useful later for deployment, not necessary for basic dev |

The important distinction is that **SDD does not replace TDD**.

SDD answers:

> What are we building and what must be true?

TDD answers:

> How do we prove this individual behavior works?

ADRs answer:

> Why did we choose this architecture?

CI answers:

> How do we automatically prove the repository remains healthy?

GitHub answers:

> How do we enforce and preserve the process?

That combination is excellent for AI-assisted development.

---

# 2. OpenSpec vs Spec Kit vs BMAD

I researched the current versions rather than relying on older impressions.

GitHub's **Spec Kit** has matured substantially. Its current core flow is Constitution → Specify → Plan → Tasks → Implement → Converge, and it now supports dozens of coding-agent integrations. ([GitHub Documentation][1])

**OpenSpec** is somewhat lighter and especially attractive for existing/brownfield repositories. Its structure revolves around persistent system specs and change-specific proposals/design/tasks, and it supports Codex through Agent Skills as well as many other coding tools. ([github.com][2])

**BMAD** is more of an AI-driven software-development methodology with specialized product/architect/dev/test roles. It's sophisticated and can scale its planning depth, but it's considerably more machinery than I think OpenDiscourse needs for normal work. ([GitHub][3])

My choice would be:

**Use OpenSpec as the primary SDD engine.**

Borrow Spec Kit's excellent idea of a permanent **constitution**, but put ours in `AGENTS.md` and the operating contract rather than maintaining two competing specification frameworks.

Do **not** install OpenSpec + Spec Kit + BMAD simultaneously. That creates competing task plans, competing specs and lots of AI-generated Markdown.

For OpenDiscourse:

```text
AGENTS.md
    ↓
permanent project constitution

openspec/specs/
    ↓
current behavioral truth

openspec/changes/
    ↓
proposed change
    ├── proposal
    ├── requirements/scenarios
    ├── design
    └── tasks

docs/adr/
    ↓
important decisions that survive individual changes

GitHub issue
    ↓
tracking / discussion

PR
    ↓
implementation + verification evidence
```

OpenSpec supports project-specific context and rules in `openspec/config.yaml`, including rules such as requiring rollback plans or Given/When/Then scenarios. That's particularly useful here. ([GitHub][4])

---

# 3. Right-size the process instead of requiring a spec for everything

This matters enormously.

If fixing a typo requires five AI-generated design documents, the system has failed.

I would use four change classes:

| Change   | Examples                                                                  | Required process                                                                  |
| -------- | ------------------------------------------------------------------------- | --------------------------------------------------------------------------------- |
| **XS**   | typo, docs wording, tiny dependency bump                                  | direct branch → focused checks → PR                                               |
| **S**    | clear bug, small refactor                                                 | issue/spec sentence + regression test → implementation                            |
| **M**    | new connector capability, CLI behavior, export feature                    | OpenSpec proposal + requirements + tasks                                          |
| **L/XL** | schema changes, connector framework, identity model, architectural change | OpenSpec proposal + requirements + design + ADR + migration/rollback plan + tasks |

That means the upcoming **Connector abstraction** is an L change.

Fixing one Census parser bug is S.

Adding an FBI connector is M/L depending on whether it introduces new canonical entities.

This keeps SDD useful instead of bureaucratic.

---

# 4. The test strategy is how we get both speed and confidence

A modern test suite should **not run every possible test after every keystroke**.

Your current CI runs everything in one job: PostGIS starts, ingestion and spatial extras install, migrations are checked, then the entire pytest suite runs.

The latest successful run took roughly 53 seconds from workflow start to finish. That's actually pretty respectable today.

But if we keep the current shape, 53 seconds eventually becomes 5 minutes, then 15 minutes.

Instead, create a test pyramid with explicit lanes.

| Layer                 | What it tests                      |  Database? | When               |
| --------------------- | ---------------------------------- | ---------: | ------------------ |
| Lint/format           | syntax/style/import issues         |         No | every edit/PR      |
| Types                 | incorrect interfaces/contracts     |         No | every PR           |
| Unit                  | pure functions/parser behavior     |         No | every edit/PR      |
| Property              | invariants/input edge cases        | Usually no | PR                 |
| Fixture contract      | source payload → parser            |         No | PR                 |
| DB repository         | SQL/persistence/idempotency        |        Yes | affected changes   |
| Migration             | Alembic upgrade/schema constraints |        Yes | DB/schema changes  |
| Connector integration | connector pipeline → staging/core  |        Yes | affected connector |
| E2E                   | CLI bootstrap/query/export         |        Yes | main/nightly       |
| Live-source smoke     | provider compatibility             |    Network | scheduled/manual   |
| Data quality          | dbt constraints/relationships      |        Yes | merge/nightly      |
| Mutation              | quality of the tests themselves    |     Varies | nightly/manual     |

Normal PRs should mostly exercise the **top half**.

Live government APIs should never be required for ordinary CI.

Save representative official payloads as fixtures and test parsers deterministically.

---

# 5. Put explicit pytest markers in the project

I would establish:

```toml
[tool.pytest.ini_options]
markers = [
    "unit: fast tests with no external services",
    "db: requires PostgreSQL/PostGIS",
    "integration: crosses multiple application layers",
    "slow: intentionally expensive tests",
    "live: contacts a real provider",
    "e2e: end-to-end application workflow",
]
```

Then the normal developer loop becomes approximately:

```bash
uv run pytest -m "not db and not slow and not live and not e2e"
```

Database verification:

```bash
uv run pytest -m "db"
```

Full:

```bash
uv run pytest
```

Live:

```bash
uv run pytest -m live
```

The agent therefore knows exactly how much testing a change requires.

---

# 6. Parallel testing is an obvious win

Add `pytest-xdist`.

It supports:

```bash
pytest -n auto
```

and distributes tests across CPU cores. ([pytest-xdist][5])

For pure unit/parser tests, I'd probably use:

```bash
pytest -n auto --dist worksteal
```

A current Microsoft Python project uses almost exactly this architecture: PR unit tests are separated from integration tests, larger suites use xdist/work-stealing, and affected integration jobs are selected based on changed paths. ([GitHub][6])

That's an excellent model for OpenDiscourse.

One caveat: **don't blindly parallelize DB tests against the same mutable database**.

Either keep them serial initially or give every worker an isolated database/schema.

For example:

```text
pytest worker gw0 → opendiscourse_test_gw0
pytest worker gw1 → opendiscourse_test_gw1
pytest worker gw2 → opendiscourse_test_gw2
```

Then we can parallelize DB integration safely later.

---

# 7. Add `ty` for extremely fast static typing

Since you're already standardized on Astral's `uv` and Ruff, I think **Astral `ty`** is a particularly interesting fit.

It is now an extremely fast Python type checker with incremental analysis and a watch mode, from the same organization behind Ruff and uv. ([Astral Docs][7])

I'd add:

```bash
uv add --dev ty
```

and require:

```bash
uv run ty check
```

for PRs.

This gives us a very fast stack:

```text
uv
ruff
ty
pytest
```

All optimized for quick feedback.

---

# 8. Add only a few testing libraries

You already have Hypothesis and Polyfactory, so don't add Factory Boy or another property-testing framework.

My Python development dependency set would converge toward:

```text
pytest
pytest-cov
pytest-xdist
pytest-timeout
hypothesis
polyfactory
respx
ruff
ty
testcontainers[postgres]
sqlfluff
```

`respx` would mock `httpx` cleanly for connector tests.

`pytest-timeout` prevents hanging API/database tests from burning CI minutes.

`sqlfluff` is worth using because this repository has meaningful standalone SQL and dbt will become increasingly important.

Mutation testing such as `mutmut` can come later, but it belongs in scheduled CI rather than normal PRs.

---

# 9. CI should have four speeds

This is the CI architecture I recommend.

| CI lane                     | Goal                               |                 Target |
| --------------------------- | ---------------------------------- | ---------------------: |
| **Local**                   | immediate developer/agent feedback |              ~5–15 sec |
| **PR Fast**                 | always required                    |             <45–60 sec |
| **PR Affected Integration** | only relevant DB/domain checks     |                <90 sec |
| **Main/Nightly**            | exhaustive confidence              | minutes are acceptable |

**PR Fast** should include Ruff lint, Ruff format check, `ty check`, OpenSpec/spec validation, inventory/contract validation, documentation link checks and non-DB pytest.

The **affected integration** lane gets PostGIS and only runs the database areas touched by the change.

A change under:

```text
src/opendiscourse_research/connectors/fred/
```

would not need ACS bulk integration tests.

A change under:

```text
src/opendiscourse_research/core/db.py
migrations/
models/
```

would run all database integration tests.

GitHub Actions supports native changed-path filtering, although workflow-level path filtering needs care when the workflow is a required check. ([GitHub Docs][8])

I would actually create our own tiny:

```text
scripts/ci/classify_changes.py
```

rather than adding some random third-party "changed files" Action.

It can emit:

```text
python=true
database=true
census=false
legislation=true
docs=false
```

That gives us complete control and avoids another Actions supply-chain dependency.

---

# 10. Local CI should mirror GitHub CI

Agents should never have to guess which commands GitHub will run.

I'd define canonical commands such as:

```text
check-fast
check-db
check-full
check-live
```

Whether those are implemented with a `justfile`, shell scripts, or a small Python dev CLI matters less than having **one source of truth**.

I slightly prefer a `justfile` for developer ergonomics:

```bash
just check
just unit
just db
just full
```

But if minimizing external tooling is more important, `scripts/dev.py` can provide the same interface using Python already present in the repository.

The important rule:

> CI invokes the same commands humans and agents invoke locally.

No giant opaque YAML command duplicated only inside GitHub Actions.

---

# 11. GitHub should become the project-management system

I don't think you need Jira, Linear and GitHub Projects simultaneously.

For this project:

```text
GitHub Issues
     ↓
GitHub Project
     ↓
OpenSpec change
     ↓
branch
     ↓
draft PR
     ↓
automated checks
     ↓
AI/human review
     ↓
squash merge
     ↓
main
```

Your `.github` directory currently only contains the test workflow.

I would add:

```text
.github/
    ISSUE_TEMPLATE/
        bug.yml
        feature.yml
        connector.yml
        architecture.yml

    pull_request_template.md

    dependabot.yml

    workflows/
        ci.yml
        integration.yml
        security.yml
        nightly.yml
        release.yml
```

Not all five workflows need to run on every PR.

---

# 12. Add a repository ruleset

Your repository currently reports **no GitHub rulesets**.

GitHub rulesets can require PRs, status checks, block force-pushes, enforce code scanning and other controls. ([GitHub Docs][9])

I would eventually protect `main` with:

```text
Require pull request
Require PR-fast
Require relevant integration result
Block force pushes
Block branch deletion
Resolve conversations before merge
Allow squash merge
```

Because you're often the only human developer and AI agents do a lot of the work, I would **not** require another human approval.

That would only slow you down.

CI + independent AI review + your merge decision is appropriate.

---

# 13. Dependabot + Dependency Review + CodeQL

These are cheap leverage.

GitHub's dependency review action can reject a PR when it introduces a vulnerable dependency. ([GitHub Docs][10])

Add Dependabot for:

```text
uv/Python dependencies
GitHub Actions
```

And enable CodeQL for Python.

Security analysis can run separately from the fast test lane.

GitHub also specifically recommends dependency review and keeping Actions references updated. ([GitHub Docs][11])

---

# 14. The AI-agent workflow should be explicit

I strongly recommend this model:

```text
Human/Lead Agent
       │
       ├── scope/specification
       │
       ├── architecture decisions
       │
       └── integration judgment
               │
               ▼
        Implementation Agent
               │
               ▼
       focused verification
               │
               ▼
        Independent Reviewer
               │
        ┌──────┴──────┐
        │             │
     approve       findings
                      │
                      ▼
                 implementation
```

Don't have five AI reviewers making overlapping comments.

Two roles are usually enough:

**Builder** and **Reviewer**.

The reviewer receives:

```text
spec
design
diff
test results
architecture contract
```

and is told to find correctness/provenance/security/design problems rather than rewrite stylistic details.

---

# 15. `AGENTS.md` should become the constitution

AGENTS.md is now a broadly adopted open convention for coding-agent instructions; the project describes it as essentially a README for agents and reports usage across tens of thousands of open-source projects. ([Agents][12])

So your existing choice was good.

I would **not** maintain independent full copies of:

```text
AGENTS.md
CLAUDE.md
CODEX.md
GEMINI.md
GROK.md
```

They will drift.

Use:

```text
AGENTS.md
```

as canonical.

Tool-specific files, if required, should be extremely short and point back to `AGENTS.md`.

---

# 16. Skills are actually becoming more important than MCP for some jobs

This ecosystem has matured a lot.

The open Agent Skills ecosystem uses `SKILL.md` packages that Codex, Claude and many other agents can consume, and the `skills` CLI can install skills into supported agents. ([Skills][13])

More importantly, we should create **OpenDiscourse-specific skills**.

Generic models already know Python.

They do not know our precise rules about provenance, staging, connector discovery, identities, or PostGIS boundaries.

I would eventually build skills such as:

```text
.agents/skills/
    opendiscourse-connector/
    opendiscourse-schema-change/
    opendiscourse-provenance/
    opendiscourse-testing/
    opendiscourse-research-mart/
```

For example, `opendiscourse-connector` could teach an agent:

```text
inspect existing source inventory
identify authoritative publisher
define source grain
define stable identifiers
implement metadata discovery
define fixture payloads
implement staging
implement canonical mapping
record provenance
write contract tests
write DB integration tests
update source progress
```

That is vastly more useful than repeatedly explaining those requirements in chat.

---

# 17. Skills I would borrow today

One especially relevant project I found is Microsoft's **PostgreSQL Agent Skills** project. It includes 32 expert-curated PostgreSQL skills and integration with `postgres-mcp`. ([GitHub][14])

That is directly relevant to OpenDiscourse.

I would evaluate/install that before creating our own generic Postgres instructions.

The Skills ecosystem also has reusable TDD and "verification before completion" skills, which are exactly the kind of procedural behaviors we want agents to follow. ([Skills][15])

The best approach is:

```text
generic industry knowledge
       ↓
external skills

OpenDiscourse-specific knowledge
       ↓
our own skills

permanent behavioral rules
       ↓
AGENTS.md

change-specific intent
       ↓
OpenSpec
```

That's a very clean AI context architecture.

---

# 18. MCP servers I recommend

MCP is useful, but we shouldn't connect every MCP server on GitHub.

Each tool adds schemas, context and an additional security surface.

My short list is:

| MCP/tool                  |  Priority | Purpose                                     |
| ------------------------- | --------: | ------------------------------------------- |
| **GitHub MCP**            |     ⭐⭐⭐⭐⭐ | issues, PRs, Actions, repository operations |
| **Postgres MCP**          |     ⭐⭐⭐⭐⭐ | schema/query/database inspection            |
| **Context7**              |      ⭐⭐⭐⭐ | current library documentation               |
| **Playwright CLI/skill**  |       ⭐⭐⭐ | browser testing once UI/API exists          |
| Filesystem MCP            |         ❌ | coding agent already has filesystem         |
| Memory MCP                |         ❌ | repo/specs should be durable memory         |
| "Sequential thinking" MCP |         ❌ | unnecessary                                 |
| Separate web MCP          | Usually ❌ | agent often already has web/search          |

GitHub now maintains an **official GitHub MCP Server**, including repository, issues, PRs, Actions, code-security and other toolsets. It also supports read-only and lockdown modes. ([GitHub][16])

That's the one I'd use rather than a third-party GitHub MCP.

**Context7** is also useful because it supplies current library docs to coding agents instead of relying on model training data. ([GitHub][17])

For database MCP access:

> Default agents to **read-only** access.

Give write permissions only to the agent currently performing an explicitly authorized database task.

Never point normal coding agents at production with unrestricted mutation rights.

---

# 19. Playwright: use the skill/CLI before MCP

This is an interesting development.

Microsoft's current Playwright MCP documentation itself now notes that coding agents may benefit from **CLI + Skills** because that can consume substantially less model context than loading the larger MCP tool surface. ([GitHub][18])

So once OpenDiscourse gets a web interface, I'd use:

```text
Playwright
+
Playwright CLI skill
+
normal Playwright test files
```

and only enable persistent Playwright MCP where exploratory/browser-agent interaction is genuinely useful.

That's an example of the principle:

> MCP when an agent needs an interactive external capability; Skills when it mostly needs procedural knowledge.

---

# 20. A ready-to-use operating contract

I would turn your existing creed into something closer to this. It deliberately doesn't replace all your existing domain-specific documentation; it governs how work is performed.

# OpenDiscourse Engineering Operating Contract

## Purpose

OpenDiscourse is a provenance-first research data platform. Development must optimize for correctness, reproducibility, maintainability, transparent provenance, safe evolution of stored data, and fast feedback for developers and coding agents.

The repository is developed using spec-driven, test-guided, AI-assisted engineering. Process depth is proportional to change risk; small changes remain lightweight while architectural, schema, provenance, and data-model changes require explicit design and verification.

## Sources of Truth

`AGENTS.md` defines permanent engineering principles and agent behavior.

Active OpenSpec specifications define required system behavior.

Architecture Decision Records under `docs/adr/` record significant architectural decisions and their rationale.

`inventory/sources.yaml` defines the authoritative dataset/source catalog.

Database migrations define persisted schema history.

Automated tests encode executable behavioral and regression expectations.

Implementation code must conform to these higher-level contracts. When these sources disagree, the discrepancy must be resolved explicitly rather than silently choosing whichever representation is convenient.

## Change Classification

Every change is classified before significant implementation begins.

XS changes are mechanical or documentation-only and may proceed directly to focused verification.

S changes are bounded bug fixes or small refactors. They require a clear behavioral statement and regression coverage when behavior changes.

M changes introduce a meaningful capability. They require an OpenSpec proposal, behavioral requirements, acceptance scenarios, and implementation tasks.

L and XL changes alter architecture, persistent schemas, canonical domain models, cross-provider contracts, security boundaries, provenance semantics, or major operational behavior. They require an OpenSpec proposal, requirements, technical design, implementation plan, verification strategy, rollback or migration strategy where applicable, and an Architecture Decision Record when the decision will remain relevant after the change is archived.

Process artifacts exist to reduce ambiguity. Agents must not generate planning documents that provide no decision-making value.

## Standard Change Lifecycle

Work begins by inspecting existing code, specifications, architecture decisions, issues, tests, dependencies, and reusable upstream projects relevant to the problem.

The change is then specified at the minimum depth required by its classification.

Requirements describe observable behavior and constraints before implementation details. Important requirements include explicit success, failure, idempotency, provenance, recovery, and compatibility scenarios where applicable.

Implementation planning identifies affected modules, persistence boundaries, test layers, migrations, operational effects, and documentation.

Implementation proceeds in small cohesive increments. Existing abstractions and proven libraries are preferred over new local machinery when they satisfy the requirement without compromising project contracts.

Focused verification runs continuously during implementation.

An independent review evaluates the final diff against the specification, architecture, security and provenance rules rather than merely reviewing style.

The change is complete only when its specification, implementation, tests, documentation, migrations, and operational behavior agree.

## AI Agent Contract

Agents inspect before editing and search for existing implementations, libraries, utilities, tests, specifications, and upstream projects before creating new abstractions.

Agents do not rewrite working subsystems merely because another design is possible.

Agents do not broaden task scope without recording the reason and updating the associated plan or issue.

Agents prefer small cohesive commits and short-lived branches.

Agents must not expose credentials, API keys, tokens, private data, or provider secrets in code, logs, fixtures, prompts, commits, issues, or test output.

Delegated agent output is treated as untrusted engineering input until reviewed and verified.

An agent must not declare a task complete solely because code was generated or a command exited successfully. Relevant linting, typing, tests, migrations, runtime checks, and specification acceptance conditions must be evaluated.

Generated code is held to the same quality requirements as human-authored code.

## Architectural Boundaries

Provider connectors own provider-specific transport, authentication, pagination, rate limiting, metadata discovery, and source parsing.

Generic ingestion infrastructure owns run state, artifacts, checksums, provenance, retries, capacity safety, resumability, and shared execution semantics.

Repositories own PostgreSQL/PostGIS persistence.

Domain services own canonical normalization and identity resolution.

Provider-shaped records remain in staging boundaries until explicitly normalized.

Canonical schemas never evolve automatically from an upstream provider response.

Research transformations and analytical marts belong in dbt or dedicated analysis layers rather than provider connectors.

CLI and UI surfaces invoke application services and must not become repositories for provider logic or persistence behavior.

## Reuse Policy

Before introducing significant custom acquisition, parsing, orchestration, database, search, export, or analytical infrastructure, contributors must evaluate maintained libraries and open-source projects that already solve the problem.

Reuse is preferred when the upstream project has an appropriate license, active maintenance, adequate correctness, acceptable security, and an interface compatible with OpenDiscourse's provenance and architecture requirements.

External acquisition systems may produce source data, but OpenDiscourse retains control over evidence, canonical normalization, provenance, identity resolution, and research schemas.

Dependencies are added deliberately. Duplicate libraries serving substantially the same purpose are avoided.

## Testing Contract

Tests are designed alongside behavior rather than after implementation is considered finished.

Fast deterministic unit and parser tests form the default development loop.

Property-based tests are used for important invariants and input-shape boundaries where generated cases improve confidence.

Provider contract tests use deterministic fixtures and must not require live internet access during ordinary pull-request CI.

PostgreSQL/PostGIS integration tests verify persistence semantics, constraints, idempotency, migrations, provenance, and important SQL behavior.

Live provider tests are isolated from ordinary CI and run only in explicit smoke, scheduled, or manual workflows.

End-to-end tests are reserved for critical workflows where lower-level tests cannot provide equivalent confidence.

Slow and expensive checks must be marked explicitly.

A test should fail because behavior is incorrect, not because an unrelated network provider, clock, global state, or shared mutable database happened to change.

Coverage is evidence, not the objective. New and changed critical behavior must be meaningfully tested; trivial code must not receive meaningless tests merely to increase a percentage.

## CI Contract

Local and pull-request feedback must be fast.

The fast CI lane performs formatting, linting, static typing, specification validation, inventory/contract validation, documentation integrity checks, and deterministic non-database tests.

Database and connector integration checks run only when affected code or critical shared infrastructure changes.

The exhaustive suite runs on main, scheduled workflows, releases, or explicit manual invocation.

Parallel execution is used where tests are isolated.

Database test parallelism requires worker isolation; tests must never concurrently mutate an unintentionally shared schema.

Ordinary CI must not contact production systems or live external providers.

Commands executed by GitHub Actions must reuse the same project commands available to developers and agents locally.

CI performance is treated as an engineering metric. Material increases in the fast-path duration require justification.

## Git and GitHub Contract

`main` remains releasable and protected.

Normal work occurs in short-lived topic branches.

Pull requests link their issue or OpenSpec change when one exists and summarize intent, important decisions, risk, and verification evidence.

Draft pull requests are encouraged for substantial AI-assisted work because they make progress, CI state, and review context visible early.

Commits remain cohesive and independently understandable.

Squash merging is preferred for ordinary feature and maintenance branches unless preserving individual commits has clear value.

Force pushing or bypassing failed required checks is exceptional and must not become the normal workflow.

GitHub Issues track user-visible work, defects, architectural tasks, and independently actionable follow-up work.

Specifications describe behavior; issues track work. They must not become duplicate competing task systems.

## Database and Data Safety

Schema changes use reviewed migrations.

Canonical data is never silently reinterpreted.

Destructive migrations require an explicit migration and rollback or recovery strategy.

Provider snapshots and canonical warehouse data remain separately owned systems.

Every canonical record or relationship that requires source evidence must retain deterministic provenance to an immutable provider response or artifact.

Identity resolution uses stable source identifiers and explicit mappings rather than names or probabilistic guesses unless a separately reviewed entity-resolution process authorizes otherwise.

Ingestion is idempotent wherever the upstream source and model permit it.

Resumable workflows persist safe checkpoints.

Unknown or ambiguous provider behavior fails visibly instead of silently fabricating a result.

## Documentation Contract

Behavior, schema, interface, operational, and architectural changes update their relevant documentation in the same pull request.

Permanent architectural reasoning belongs in an ADR rather than being left only in a chat session or pull-request conversation.

Provider quirks that materially influence correctness belong near the connector and in appropriate tests or source documentation.

Completed OpenSpec changes are archived according to the project's specification workflow so current system behavior remains discoverable.

## Definition of Done

A change is done when the implementation satisfies its approved behavioral contract; focused and risk-appropriate automated verification passes; affected migrations and database semantics have been validated; provenance and idempotency requirements are satisfied; documentation and specifications reflect the implemented state; no unresolved high-confidence review finding remains; no secret or unsafe data has entered version control; and the resulting code remains understandable to the next human or agent without requiring access to the original conversation.

## Optimization Principle

The project optimizes for the smallest amount of process and infrastructure that reliably preserves correctness.

Automation should eliminate repetitive effort, not introduce ceremony.

Fast feedback is a feature.

Every new development tool must earn its maintenance and cognitive cost.

That can become either `docs/engineering/operating-contract.md` or the basis for a rewritten `AGENTS.md`.

I prefer keeping `AGENTS.md` reasonably compact and linking from it to this more detailed contract.

---

# 21. A proposed repository organization for development/process files

I would target:

```text
AGENTS.md

openspec/
    config.yaml
    specs/
    changes/

docs/
    architecture/
    adr/
        0001-postgresql-system-of-record.md
        0002-open-civic-data-legislative-model.md
        0003-connector-runtime-boundary.md

    engineering/
        operating-contract.md
        testing.md
        ci.md
        releases.md

    runbooks/

.agents/
    skills/
        opendiscourse-connector/
        opendiscourse-schema-change/
        opendiscourse-provenance/
        opendiscourse-testing/

.github/
    ISSUE_TEMPLATE/
    pull_request_template.md
    dependabot.yml
    workflows/

scripts/
    ci/
        classify_changes.py
        check_fast.py
        check_database.py
```

Notice what's missing:

```text
random task-log files
multiple competing agent instructions
five planning systems
AI-generated progress diary committed after every operation
```

GitHub already records execution history.

We don't need to turn the repo into an AI transcript.

---

# 22. What I would install and what I would avoid

| Tool                          | Recommendation                                   |
| ----------------------------- | ------------------------------------------------ |
| OpenSpec                      | **Install**                                      |
| GitHub Spec Kit               | Learn from; don't install simultaneously         |
| BMAD                          | Don't use as default                             |
| Ruff                          | Already correct                                  |
| uv                            | Already correct                                  |
| ty                            | **Add**                                          |
| pytest-xdist                  | **Add**                                          |
| pytest-timeout                | **Add**                                          |
| respx                         | **Add**                                          |
| Hypothesis                    | Already correct                                  |
| Polyfactory                   | Already correct                                  |
| SQLFluff                      | **Add**                                          |
| pre-commit                    | Optional; I lean **yes** once commands stabilize |
| testcontainers                | Keep for local/isolated DB tests                 |
| CodeQL                        | **Enable**                                       |
| Dependabot                    | **Enable**                                       |
| Dependency Review             | **Enable**                                       |
| GitHub ruleset                | **Enable after CI refactor**                     |
| GitHub Projects               | **Use**                                          |
| Linear/Jira                   | Don't add yet                                    |
| GitHub MCP                    | **Use**                                          |
| Microsoft Postgres skills/MCP | **Use**                                          |
| Context7 MCP                  | **Use**                                          |
| Playwright CLI skill          | Later, when UI exists                            |
| Generic filesystem MCP        | Don't add                                        |
| Generic memory MCP            | Don't add                                        |

---

# 23. One particularly important rule for AI agents

I want this added very prominently:

> **Search before build.**

Before writing a substantial subsystem, an agent must answer:

```text
Does this already exist in this repository?
Does a dependency we already have do it?
Does PostgreSQL/PostGIS already do it?
Does Python's standard library do it?
Does a mature Python library do it?
Does an authoritative open-source project already do it?
Can we adapt or wrap that implementation?
What unique value would our custom implementation provide?
```

This one rule would have prevented a lot of unnecessary complexity in many AI-built repositories.

For OpenDiscourse it's especially important.

We're integrating knowledge and systems.

Our competitive advantage is **integration and research semantics**, not the number of lines we wrote ourselves.

---

# 24. I would implement this in a specific sequence

1. **Create `docs/engineering/operating-contract.md`** from the contract above and slim `AGENTS.md` so it acts as the constitution and points to detailed policies.

2. **Initialize OpenSpec** and configure it for the XS/S/M/L change model, Given/When/Then behavioral scenarios, explicit test strategy, and migration/rollback requirements for persistent changes. Don't add Spec Kit or BMAD alongside it.

3. **Refactor the test taxonomy** with pytest markers, then establish `fast`, `db`, `full`, and `live` commands before changing GitHub Actions.

4. **Add `ty`, `pytest-xdist`, `pytest-timeout`, `respx`, and SQLFluff**. Parallelize deterministic tests immediately; leave mutable DB tests serial until worker database isolation exists.

5. **Split CI** into a fast always-running check and affected integration checks. Preserve a full main/nightly suite. Add runtime reporting so we can see which tests are making CI slower over time.

6. **Add the GitHub development surfaces**: issue forms, PR template, Dependabot, dependency review, CodeQL, sensible labels and a basic GitHub Project. The PR template should link the OpenSpec change and record actual verification performed.

7. **Add a `main` ruleset only after the new checks are stable**, requiring the fast check and appropriate integration gateway rather than requiring every expensive job independently.

8. **Install the official GitHub MCP and Microsoft PostgreSQL skills/MCP in your coding-agent environment**, plus Context7. Keep DB credentials scoped and default Postgres agent access to read-only. Microsoft's PostgreSQL Agent Skills project is especially relevant to what we're building. ([GitHub][14])

9. **Create our own OpenDiscourse Agent Skills** for connector development, schema changes, provenance and testing. This converts the best knowledge currently buried across docs into reusable agent procedures.

10. **Use the Connector refactor as the first full OpenSpec-driven change.** That will test the whole operating model on a real architectural task before we expand OpenDiscourse further.

The result would give you something I think is unusually valuable: **a repository designed not only to contain a good research platform, but to be safely and efficiently evolved by Codex, Claude, Gemini, Grok, or whatever agent comes next without each one rediscovering the architecture or making up its own development process.**

And the CI objective I would put in writing is: **routine local feedback under ~15 seconds, required PR feedback around a minute, affected PostGIS checks under ~90 seconds when possible, and expensive/exhaustive testing moved off the critical development path.** That gives us strong testing without making you sit around watching databases boot all day.

[1]: https://github.github.com/spec-kit/?utm_source=chatgpt.com "GitHub Spec Kit | Spec Kit Documentation"
[2]: https://github.com/t1seungy/openspec?utm_source=chatgpt.com "GitHub - t1seungy/openspec: Spec-driven development (SDD) for AI coding assistants. · GitHub"
[3]: https://github.com/bmad-code-org/BMAD-METHOD?utm_source=chatgpt.com "GitHub - bmad-code-org/BMAD-METHOD: Breakthrough Method for Agile Ai Driven Development · GitHub"
[4]: https://github.com/Fission-AI/OpenSpec/blob/main/docs/customization.md?utm_source=chatgpt.com "OpenSpec/docs/customization.md at main · Fission-AI/OpenSpec · GitHub"
[5]: https://pytest-xdist.readthedocs.io/en/latest/distribution.html?utm_source=chatgpt.com "Running tests across multiple CPUs — pytest-xdist documentation"
[6]: https://github.com/microsoft/agent-framework/blob/main/python/.github/skills/python-testing/SKILL.md?utm_source=chatgpt.com "agent-framework/python/.github/skills/python-testing/SKILL.md at main · microsoft/agent-framework · GitHub"
[7]: https://docs.astral.sh/ty/type-checking/?utm_source=chatgpt.com "Type checking | ty"
[8]: https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/trigger-a-workflow?utm_source=chatgpt.com "Triggering a workflow - GitHub Docs"
[9]: https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/about-rulesets?utm_source=chatgpt.com "About rulesets - GitHub Docs"
[10]: https://docs.github.com/en/code-security/how-tos/secure-your-supply-chain/manage-your-dependency-security/configure-dependency-review-action?utm_source=chatgpt.com "Configuring the dependency review action - GitHub Docs"
[11]: https://docs.github.com/en/actions/reference/security/secure-use?utm_source=chatgpt.com "Secure use reference - GitHub Docs"
[12]: https://agents.md/?utm_source=chatgpt.com "AGENTS.md"
[13]: https://www.skills.sh/docs?utm_source=chatgpt.com "Documentation | Skills"
[14]: https://github.com/microsoft/postgres-skills?utm_source=chatgpt.com "GitHub - microsoft/postgres-skills: Agent skills and plugins for PostgreSQL — vendor-agnostic best practices plus Azure-specific patterns that AI coding agents can't learn from training data · GitHub"
[15]: https://www.skills.sh/topic/testing?utm_source=chatgpt.com "Testing skills — skills.sh"
[16]: https://github.com/github/github-MCP-server?utm_source=chatgpt.com "GitHub - github/github-mcp-server: GitHub's official MCP Server · GitHub"
[17]: https://github.com/upstash/context7/blob/master/packages/mcp/package.json?utm_source=chatgpt.com "context7/packages/mcp/package.json at master · upstash/context7 · GitHub"
[18]: https://github.com/microsoft/playwright-mcp?utm_source=chatgpt.com "GitHub - microsoft/playwright-mcp: Playwright MCP server · GitHub"
