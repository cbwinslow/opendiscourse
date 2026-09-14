Yes — I would pivot to **BMAD**.

Given that you want to learn an AI-native SDD methodology, expect OpenDiscourse to become much larger, and care about architecture/testing/DevOps rather than just having an agent generate code, BMAD is a better experiment for us than keeping the workflow ultra-minimal.

And BMAD has evolved since some of the earlier criticism of it. The current v6.12 release specifically added **adaptive ceremony**: Build investigates a change before deciding how much process it needs, and straightforward changes can use a very small spec instead of going through the entire lifecycle. It also now respects an existing handwritten `AGENTS.md` rather than trying to replace it. ([GitHub][1])

There is also a very good answer to your context-window question, but it is not one magical "lossless compression" program.

## First: BMAD makes sense for OpenDiscourse

BMAD describes itself as an AI-driven development process spanning product thinking, architecture, implementation, testing and review rather than just code generation. It is specifically designed to carry decisions forward as durable context and adjust planning depth to the work. ([GitHub][2])

That's almost exactly what we're trying to establish.

I would use:

```text
BMAD Method
    │
    ├── Product / requirements
    ├── Architecture
    ├── Epics / stories
    ├── Implementation workflow
    └── Review
            │
            └── BMAD TEA
                  ├── risk analysis
                  ├── test design
                  ├── ATDD
                  ├── test automation
                  ├── CI optimization
                  ├── test review
                  └── traceability

Durable engineering truth
    │
    ├── AGENTS.md
    ├── ADRs
    ├── migrations
    ├── tests
    └── source code

Execution / audit
    │
    └── GitHub
          ├── Issues
          ├── PRs
          ├── Projects
          └── Actions
```

That is a much stronger system than making BMAD artifacts themselves the ultimate authority.

---

# BMAD TEA is especially interesting for you

This part made me much more comfortable recommending BMAD for OpenDiscourse.

BMAD's **Test Engineering Architect (TEA)** isn't simply a "write me some tests" agent. It has a risk-based testing model, P0–P3 priorities, acceptance-test-driven development, test review, requirements-to-test traceability, NFR evidence, and CI design. ([GitHub][3])

It even specifically has a CI workflow aimed at:

* selective testing,
* parallel execution,
* sharding,
* burn-in/flakiness detection,
* GitHub Actions integration. ([GitHub][4])

That maps directly onto your concern about not waiting forever for Postgres tests.

I would install **BMAD Method + TEA**, but not necessarily turn every TEA feature on from day one.

Start approximately here:

```text
BMAD
├── project context
├── architecture
├── feature / epic planning
├── build
└── review

TEA
├── test-design
├── CI
├── ATDD for important stories
├── automate
└── test-review
```

Then later add NFR gates and full traceability as the project becomes more mature.

---

# BMAD also addresses context bloat better than I expected

Its current guidance for existing projects says something very important:

> Don't repeatedly feed an agent prose describing things it can inspect directly from the codebase.

BMAD explicitly warns that doing that creates contradictions, ambiguity and **context-window bloat**. ([BMad Method][5])

It now has a `bmad-project-context` workflow that maintains a **small verified block** in the project's existing `AGENTS.md`, rather than stuffing the whole project description into every session. ([BMad Method][6])

That is the right mental model.

---

# About "lossless context compression"

There is one important limitation to understand:

**There is no general-purpose tool that can compress arbitrary natural-language/code context dramatically with literally zero information loss while preserving every possible future inference.**

That's essentially impossible unless it retains an equivalent representation of all of the original information.

What we *can* do extremely effectively is something better:

### Don't compress everything. Externalize it and retrieve only what matters.

Instead of this:

```text
200,000 tokens history
        ↓
compress
        ↓
50,000 token summary
```

build this:

```text
                CONTEXT STORE

Architecture ─────┐
Decisions ────────┤
Specifications ───┤
Code ─────────────┤
Git history ──────┤
Past sessions ────┤
Research ─────────┘
        │
        │ retrieval
        ↓
  current task
        ↓
  ~10–30k useful
  tokens rather
  than 200k noise
```

That reduces tokens **without requiring us to destroy the original information**.

This is one of the biggest ideas in context engineering.

---

# There are really five different context problems

People often call all of these "memory", but they're different.

| Problem              | Example                                  | Best approach             |
| -------------------- | ---------------------------------------- | ------------------------- |
| Project knowledge    | How OpenDiscourse works                  | Git + BMAD + AGENTS       |
| Code context         | Which classes/functions matter right now | Serena                    |
| Conversation history | What did we decide 20 sessions ago?      | Letta / Supermemory / Git |
| Large repo transfer  | Give Grok a compact view of repo         | Repomix                   |
| Library knowledge    | What's the current SQLAlchemy API?       | Context7                  |

Trying to solve all five with one giant vector database usually produces worse results.

---

# The context tool I think you should investigate first: Serena

**Serena** is particularly interesting for you.

Instead of dumping complete Python files into an LLM, Serena uses language-server semantics to let the agent work in terms of:

```text
symbol
class
method
references
call relationships
definition
usage
```

It essentially acts like an IDE for a coding agent. The maintainers specifically position it as a way to make coding agents faster and more context-efficient on large repositories. ([GitHub][7])

Instead of sending:

```text
Here are 1,800 lines of legislation.py...
```

the agent could effectively ask:

```text
find symbol BillRepository
find references to upsert_bill
show body of normalize_bill
show symbols calling normalize_bill
```

That is **context reduction through retrieval**, not lossy summarization.

Much better.

---

# Serena also has project memory

Serena supports Markdown memories under:

```text
.serena/memories/
```

and global memories under:

```text
~/.serena/memories/global/
```

The model receives the list of memories and retrieves whichever is appropriate rather than automatically dumping all memory content into every request. ([GitHub][8])

We could maintain things like:

```text
.serena/memories/

architecture-summary.md
database-conventions.md
connector-contract.md
provenance-rules.md
testing-strategy.md
common-provider-gotchas.md
research-model.md
```

But here's an important rule:

**Don't duplicate authoritative BMAD/ADR content in Serena memory.**

The memory should often contain an index/pointer:

```text
Canonical connector architecture:
docs/architecture/connectors.md

Important decisions:
docs/adr/0012-connector-interface.md
docs/adr/0014-provenance-model.md
```

instead of copying 4,000 words.

---

# Repomix is perfect for what you just did with Grok

You said you're currently taking my analysis and pasting it into Markdown for Grok.

**Repomix** is almost purpose-built for that workflow.

It can:

* package a repository into an AI-friendly artifact,
* count tokens,
* show which directories/files consume the most tokens,
* respect `.gitignore`,
* include git history/diffs,
* scan for secrets,
* and use Tree-sitter to produce a structurally compressed version of source code. ([GitHub][9])

Example:

```bash
repomix --compress
```

Instead of including full function implementations, compression can retain things like:

```python
class CongressConnector:
    def discover(...):
        ⋮

    def extract(...):
        ⋮

    def normalize(...):
        ⋮
```

while preserving structural information.

And:

```bash
repomix --token-count-tree
```

will show you where your token budget is going.

That's extremely useful for sharing OpenDiscourse with:

* Grok,
* Claude web,
* Gemini,
* ChatGPT web,
* independent reviewers.

I would absolutely add a checked-in:

```text
repomix.config.json
```

for this project.

---

# For actual persistent agent memory, Letta is fascinating

If you're specifically interested in:

> context window clearing
> compaction
> remembering across sessions
> avoiding context drift
> managing what stays in context
> learning from previous work

then **Letta Code** is probably the most interesting current project to experiment with.

Letta is the successor to MemGPT and is now built around long-lived coding agents with persistent memory. ([GitHub][10])

Its architecture separates:

```text
CURRENT CONTEXT
recent conversation
important memory blocks

        +

EXTERNAL MEMORY
project knowledge
skills
historical context
past interactions
```

Older conversation material can be summarized/evicted while remaining searchable through recall. ([GitHub][11])

---

# Letta's MemFS concept is especially clever

Letta stores durable memory in a **Git-backed memory filesystem**.

Important memory gets included directly in context.

Larger reference material remains outside the context and gets retrieved as necessary. ([GitHub][12])

Conceptually:

```text
MemFS/

system/
    identity.md
    project-current-state.md
    development-rules.md

reference/
    architecture-history.md
    provider-notes.md
    research.md

skills/
    opendiscourse-connector/
    db-migration/
    test-design/
```

The `system/` part is precious context real estate.

Everything else is on-demand.

This is exactly how I think coding-agent context should work.

---

# And Letta has the commands you're describing

Current Letta supports things like:

```text
/init
/remember
/doctor
/search
/clear
```

and **dreaming**.

`/doctor` audits memory placement, duplication and system-prompt token usage.

Dreaming uses background agents to review recent conversations, consolidate useful information and restructure memory—including when context has been compacted. ([GitHub][13])

That's unusually close to what you were describing.

Essentially:

```text
conversation
conversation
conversation
conversation
      ↓
context fills
      ↓
summarize / compact
      ↓
extract durable learning
      ↓
update memory
      ↓
clear transient noise
      ↓
continue
```

That is a much more sophisticated memory architecture than a simple `MEMORY.md`.

---

# But I would NOT switch OpenDiscourse development entirely to Letta yet

BMAD + Letta + Codex + Claude + Serena simultaneously could become its own project.

I'd separate experiments.

### Primary coding workflow

```text
Codex / Claude / Gemini
        │
        ├── BMAD
        ├── TEA
        ├── Serena
        ├── GitHub
        └── Context7
```

### Experimental persistent-agent workflow

```text
Letta Code
     │
     ├── MemFS
     ├── recall
     ├── dreaming
     └── skills
```

Try Letta on a few isolated OpenDiscourse stories and see whether the persistence actually helps you.

It may eventually become your favorite coding environment, but we shouldn't redesign OpenDiscourse around it.

---

# There is also Supermemory

If what you primarily want is:

> "I use Grok today, Claude tomorrow, Codex later—can they share memory?"

then **Supermemory** is worth investigating.

Its current MCP exposes memory/recall/context facilities and is explicitly intended to carry persistent memory across compatible AI tools. It supports project-scoped memory and has integrations for several coding clients. ([GitHub][14])

That could give you:

```text
                    Shared Memory
                         │
       ┌─────────────────┼──────────────────┐
       ↓                 ↓                  ↓
     Claude             Codex             Grok*
       ↓                 ↓                  ↓
     Cursor            OpenCode           etc.
```

where clients supporting its interface can retrieve the same context.

This is simpler than adopting Letta as your entire agent runtime.

The tradeoff is that now you're trusting another system to decide which memories to capture and retrieve.

For important OpenDiscourse decisions:

**Git must still be authoritative.**

---

# Mem0 is another strong memory system

Mem0 is more interesting if we eventually build our **own agent infrastructure**.

Its current memory system supports multi-signal retrieval combining semantic search, keyword matching, entities and temporal reasoning. The project reports substantial reductions in the token budgets needed for its memory benchmarks. ([GitHub][15])

I would classify it as:

```text
Good for:
custom agents
OpenDiscourse AI services
research agents
multi-user apps

Less necessary for:
our immediate Codex development workflow
```

In other words, don't add Mem0 just to remember which branch we're working on.

But OpenDiscourse may someday have very good use cases for it.

---

# Graphiti is even more interesting long-term

There is another approach: **temporal knowledge-graph memory**.

Graphiti maintains facts as relationships that evolve over time and preserves provenance and historical state. ([GitHub][16])

That means it can represent:

```text
2026-07
OpenDiscourse
    uses
psycopg repositories

2026-09
OpenDiscourse
    migrates toward
SQLAlchemy Core

ADR #17
    supersedes
ADR #5
```

rather than retrieving both facts and letting the model accidentally use the old one.

That is precisely the sort of thing that helps with **context drift**.

And interestingly, the ideas behind Graphiti—temporal relationships, provenance, source evidence—are philosophically very aligned with OpenDiscourse itself.

But again:

**later**, not day one.

---

# My recommended context architecture

If I designed our entire AI engineering context stack today, it would look like this:

```text
                      ┌─────────────────┐
                      │     AGENTS.md   │
                      │ permanent rules │
                      └────────┬────────┘
                               │
                     always very small
                               │
                               ▼
                 ┌────────────────────────┐
                 │       BMAD             │
                 │ current requirements   │
                 │ architecture + story   │
                 └────────────┬───────────┘
                              │
                              ▼
                  ACTIVE CONTEXT WINDOW
                    current task only
                              │
          ┌───────────────────┼───────────────────┐
          │                   │                   │
          ▼                   ▼                   ▼
       Serena             Context7             GitHub
   source symbols       library docs       issues/PR/history
          │
          └───────────────────┬───────────────────┘
                              │
                        retrieve as needed
                              │
                              ▼
                    persistent knowledge
                              │
              ┌───────────────┴───────────────┐
              │                               │
             Git                         optional memory
       ADRs/specs/tests                Letta/Supermemory
        architecture
```

And for handing the project to web-based AI:

```text
repository
    ↓
Repomix
    ↓
compressed/token-budgeted snapshot
    ↓
Grok / Gemini / ChatGPT / Claude
```

---

# How I'd specifically prevent context drift

I'd establish **context tiers**.

### Tier 0 — always loaded

Maximum perhaps 2–5K tokens.

```text
AGENTS.md
current BMAD story/spec
critical active constraints
```

Nothing else belongs here.

### Tier 1 — retrieved frequently

```text
architecture spine
relevant ADRs
database conventions
connector contract
test strategy
```

### Tier 2 — retrieved precisely

Through Serena:

```text
classes
symbols
callers
implementations
tests
```

### Tier 3 — historical memory

```text
old stories
old PR discussions
past decisions
retrospectives
provider research
conversation summaries
```

Only retrieved when needed.

### Tier 4 — archive

```text
superseded PRDs
old architecture documents
completed BMAD artifacts
historical experiments
```

Not discoverable during ordinary work unless explicitly requested.

That last piece is important because BMAD itself now recommends keeping obsolete greenfield planning material out of the normal context path for established projects. ([BMad Method][5])

---

# Context clearing should become normal, not scary

With durable context done correctly, we shouldn't try to keep a single AI conversation alive forever.

That actually contributes to drift.

Instead:

```text
Story starts
    ↓
agent loads story + relevant context
    ↓
work
    ↓
commit
    ↓
tests
    ↓
PR/update story
    ↓
record durable decision
    ↓
CLEAR CONTEXT
    ↓
next story starts fresh
```

A fresh context window with **good retrieval** is often better than a 150,000-token conversation full of obsolete reasoning.

This is an important shift:

> Long conversation history is not the same thing as good memory.

---

# What should survive a context reset?

Only things like:

```text
WHAT
current task and acceptance criteria

WHY
important design decisions

WHERE
files/modules affected

STATE
what has been implemented

VERIFICATION
tests/checks that passed

BLOCKERS
remaining known problems

NEXT
next actionable step
```

That can often fit into **500–1,500 tokens**.

Everything else should remain accessible but off-context.

---

# BMAD is actually useful here too

BMAD's own current architecture seems to understand this distinction increasingly well.

Its repository instructions make an excellent point: prompt/workflow text is consumed repeatedly, so **every unnecessary instruction costs tokens every time an agent runs**. Their guidance is explicitly to avoid bloating permanent prompts with exotic edge cases. ([GitHub][17])

That's exactly the philosophy we should copy.

---

# My revised tool stack for OpenDiscourse

I would now recommend this combination:

| Tool               | Purpose                              |             Adopt |
| ------------------ | ------------------------------------ | ----------------: |
| **BMAD Method v6** | AI-native SDD lifecycle              |           **Yes** |
| **BMAD TEA**       | testing strategy + CI + ATDD         |           **Yes** |
| **AGENTS.md**      | permanent engineering constitution   |           **Yes** |
| **Serena MCP**     | semantic code retrieval/editing      |           **Yes** |
| **GitHub MCP**     | issues/PR/Actions/repo               |           **Yes** |
| **Context7**       | current library/API docs             |           **Yes** |
| **Repomix**        | efficient repo → external AI context |           **Yes** |
| **Letta Code**     | persistent stateful coding agent     |    **Experiment** |
| **Supermemory**    | cross-tool memory                    |        Experiment |
| **Mem0**           | memory for agents/apps we build      |             Later |
| **Graphiti**       | temporal decision/context graph      |             Later |
| Spec Kit           | alternative SDD                      | No alongside BMAD |
| OpenSpec           | alternative SDD                      | No alongside BMAD |
| BMAD Loop          | autonomous epic building             |        Much later |

This gives us a fairly sophisticated system without overlapping five tools that all do the same thing.

---

# I would also use BMAD's "architecture spine" idea

BMAD's recent architecture workflow moved toward a lean **architecture spine** rather than repeatedly feeding huge architecture documents to agents. ([GitHub][1])

I like that a lot.

OpenDiscourse could eventually have:

```text
AGENTS.md
     ~2K tokens
     engineering rules

ARCHITECTURE.md
     ~3-5K tokens
     system map + boundaries

_bmad/
     detailed active work

docs/adr/
     decisions retrieved as necessary

.serena/memories/
     indexes + useful operational knowledge

docs/
     detailed reference
```

An agent starts with maybe 5–10K tokens of highly valuable context, **not 100K**.

Then retrieval fills gaps.

---

# A slightly surprising recommendation: don't make memory too automatic

I would be careful with systems that automatically save everything.

Bad memory can be worse than no memory.

Suppose an agent says:

> "Maybe we'll use Qdrant."

An automatic memory system saves:

```text
OpenDiscourse uses Qdrant.
```

Six months later an agent retrieves it and begins building around Qdrant even though we decided on pgvector.

That's context drift generated by memory itself.

For architectural knowledge, I want:

```text
PROPOSED
DECIDED
SUPERSEDED
EXPERIMENTAL
```

distinguished explicitly.

That's why Git + ADRs + BMAD should remain the highest-authority memory.

Letta/Supermemory should be convenience layers beneath that.

---

# The resulting hierarchy of truth

I would encode this directly into `AGENTS.md`:

```text
1. Current code + tests
2. Current database migrations/schema
3. Accepted ADRs
4. Active BMAD specification/story
5. Current architecture documentation
6. GitHub issue/PR state
7. Agent/project memory
8. Historical conversations
9. Model assumptions
```

Lower levels are **not allowed to override higher levels**.

That one rule will prevent a lot of hallucination and context drift.

---

# What I'd do next

Instead of continuing to design this abstractly, I think our next project-management change should be a real **"AI development infrastructure" epic** for OpenDiscourse.

I'd structure it roughly as:

```text
EPIC: AI-Native Development System

Story 1
Install/configure BMAD Method v6

Story 2
Run BMAD brownfield project-context analysis

Story 3
Reconcile BMAD output with existing AGENTS.md

Story 4
Create architecture spine + ADR system

Story 5
Install/configure BMAD TEA

Story 6
Classify existing tests and establish test architecture

Story 7
Create fast/selective CI

Story 8
Integrate Serena MCP

Story 9
Add Repomix configuration + context budgets

Story 10
Create first OpenDiscourse-specific agent skills

Story 11
Add GitHub issue/PR/project automation

Story 12
Run Connector refactor as our first complete
BMAD-driven feature lifecycle
```

And I actually like this better than the OpenSpec direction I recommended previously. BMAD gives you an opportunity to **learn an AI-native software-development methodology while simultaneously improving a project substantial enough to exercise the methodology properly**. OpenDiscourse isn't just a toy CRUD app, so product thinking, architecture, data integrity, provenance, integration testing and CI genuinely matter.

For the token/context problem, my strongest initial combination would be **BMAD + Serena + Repomix**. I'd experiment separately with **Letta Code** because it is the closest thing I found to the sophisticated "clear/compact/retrieve/dream/maintain agent memory" system you're imagining; its `/doctor`, git-backed MemFS, recall and dreaming mechanisms are particularly interesting. ([GitHub][13])

Then, after we've experienced the pain points firsthand, we can decide whether adding Supermemory, Mem0, or eventually Graphiti actually solves something rather than just giving us another memory system to maintain.

[1]: https://github.com/bmad-code-org/BMAD-METHOD/releases?utm_source=chatgpt.com "Releases · bmad-code-org/BMAD-METHOD · GitHub"
[2]: https://github.com/bmad-code-org/BMAD-METHOD?utm_source=chatgpt.com "GitHub - bmad-code-org/BMAD-METHOD: Breakthrough Method for Agile Ai Driven Development · GitHub"
[3]: https://github.com/bmad-code-org/bmad-method-test-architecture-enterprise/?utm_source=chatgpt.com "GitHub - bmad-code-org/bmad-method-test-architecture-enterprise: Test Architect Full BMad Method Enhancement · GitHub"
[4]: https://github.com/bmad-code-org/bmad-method-test-architecture-enterprise/blob/main/docs/how-to/workflows/setup-ci.md?utm_source=chatgpt.com "bmad-method-test-architecture-enterprise/docs/how-to/workflows/setup-ci.md at main · bmad-code-org/bmad-method-test-architecture-enterprise · GitHub"
[5]: https://docs.bmad-method.org/existing-codebases/start-in-an-existing-codebase/?utm_source=chatgpt.com "Start in an Existing Codebase | BMad Method"
[6]: https://docs.bmad-method.org/existing-codebases/set-and-maintain-project-context/?utm_source=chatgpt.com "Set and Maintain Project Context | BMad Method"
[7]: https://github.com/oraios/serena/blob/main/README.md?utm_source=chatgpt.com "serena/README.md at main · oraios/serena · GitHub"
[8]: https://github.com/oraios/serena/blob/main/docs/02-usage/045_memories.md?utm_source=chatgpt.com "serena/docs/02-usage/045_memories.md at main · oraios/serena · GitHub"
[9]: https://github.com/yamadashy/repomix?utm_source=chatgpt.com "GitHub - yamadashy/repomix: 📦 Repomix is a powerful tool that packs your entire repository into a single, AI-friendly file. Perfect for when you need to feed your codebase to Large Language Models (LLMs) or other AI tools like Claude, ChatGPT, DeepSeek, Perplexity, Gemini, Gemma, Llama, Grok, and more. · GitHub"
[10]: https://github.com/letta-ai/letta/blob/main/README.md?utm_source=chatgpt.com "letta/README.md at main · letta-ai/letta · GitHub"
[11]: https://github.com/letta-ai/letta-code/blob/main/src/agent/prompts/letta.md?utm_source=chatgpt.com "letta-code/src/agent/prompts/letta.md at main · letta-ai/letta-code · GitHub"
[12]: https://github.com/letta-ai/letta-docs-md/blob/main/concepts/memfs/index.md?utm_source=chatgpt.com "letta-docs-md/concepts/memfs/index.md at main · letta-ai/letta-docs-md · GitHub"
[13]: https://github.com/letta-ai/letta-docs-md/blob/main/configuration/memory/index.md?utm_source=chatgpt.com "letta-docs-md/configuration/memory/index.md at main · letta-ai/letta-docs-md · GitHub"
[14]: https://github.com/supermemoryai/supermemory-mcp?utm_source=chatgpt.com "GitHub - supermemoryai/supermemory-mcp: Your memories are in ChatGPT... But nowhere else. Universal Memory MCP makes your memories available to every single LLM. No logins or paywall. One command to set it up. · GitHub"
[15]: https://github.com/mem0ai/mem0?utm_source=chatgpt.com "GitHub - mem0ai/mem0: The Memory Layer for AI Agents - Drop-in memory infrastructure for AI agents and apps. Context that persists. Built for production. · GitHub"
[16]: https://github.com/getzep/graphiti/blob/main/mcp_server/README.md?utm_source=chatgpt.com "graphiti/mcp_server/README.md at main · getzep/graphiti · GitHub"
[17]: https://github.com/bmad-code-org/BMAD-METHOD/blob/main/AGENTS.md?utm_source=chatgpt.com "BMAD-METHOD/AGENTS.md at main · bmad-code-org/BMAD-METHOD · GitHub"
