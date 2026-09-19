> **Not yet reviewed.** A ChatGPT review of skills and MCP servers to consider, supplied by the operator on
> 2026-09-19 and filed here unread so it is not lost. To be evaluated as a later step (see `docs/PROJECT-STATE.md`,
> next steps); nothing in it has been adopted.

Yes. There is now a surprisingly useful ecosystem around this, and **we should take advantage of it for OpenDiscourse**.

The key distinction is that a **Claude Code Skill** teaches Claude *how* to perform a workflow, while an **MCP server** actually gives Claude callable tools for accessing an API/database. For OpenDiscourse, I want both: skills for correct engineering patterns and MCPs for interactive exploration. For production bulk ingestion, though, we should still run deterministic Python/dlt/Airbyte pipelines rather than making Claude itself the ETL engine.

## The strongest reusable pieces I found

| Tool                                | Type                              | OpenDiscourse use                                                   | My take                |
| ----------------------------------- | --------------------------------- | ------------------------------------------------------------------- | ---------------------- |
| **U.S. Census Bureau Data API MCP** | Official MCP                      | Census/ACS discovery and querying                                   | **Install**            |
| **CongressMCP**                     | Community MCP                     | Congress.gov + GovInfo, bills, members, committees, votes, hearings | **Install**            |
| **OpenStates MCP**                  | Community MCP                     | State bills, legislators, committees, votes                         | **Install/test**       |
| **FEC MCP Server**                  | Community MCP                     | Candidates, committees, contributions, expenditures, Super PAC data | **Install/test**       |
| **FRED MCP**                        | Community MCP                     | FRED + ALFRED series/vintages/GeoFRED                               | **Install**            |
| **USAspending MCP**                 | Community MCP                     | Contracts, grants, awards, recipients, agencies                     | **Install**            |
| **Federal regulations MCP**         | Community MCP                     | Federal Register + eCFR + Regulations.gov                           | **Install**            |
| **CourtListener MCP**               | **Official Free Law Project MCP** | Court opinions, PACER/RECAP, judges, citations                      | **Install**            |
| **Microsoft Postgres Skills + MCP** | Microsoft agent skills/plugin     | PostgreSQL schema/query/index/security work                         | **Definitely install** |
| **dbt Agent Skills**                | dbt Labs official skills          | marts, models, tests, lineage                                       | **Definitely install** |
| **dlt Skill**                       | Data-engineering skill            | API→Parquet/Postgres pipelines                                      | **Definitely install** |
| **Airbyte Agent skills/CLI**        | Airbyte official                  | Discover/use existing connectors instead of writing adapters        | **Very useful**        |
| **DuckDB MCP**                      | MCP                               | Explore raw CSV/JSON/Parquet lake                                   | **Useful**             |
| **Federal-agent skill**             | Claude skill                      | USAspending + SAM.gov + FPDS acquisition patterns                   | **Very relevant**      |

The most notable one is that the **Census Bureau itself now publishes an MCP server** for its Data API. It connects AI assistants directly to official Census statistics and includes local setup/database tooling. That is much better than us inventing a Census-specific AI interface. ([GitHub][1])

### Congress

`amurshak/congressMCP` is very relevant to us. It gives Claude Code/Codex/etc. typed access to **Congress.gov and GovInfo** for bills, bill text, votes, members, committees, hearings, nominations and Congressional Record material. It can run locally and uses your government API credentials rather than some third-party database. ([GitHub][2])

I would use this primarily as an **exploration/schema-development tool** while keeping `unitedstates/congress`, Congress.gov APIs and GovInfo bulk files as the production acquisition layer.

### OpenStates

There is also a dedicated `openstates-mcp` with tools around OpenStates state-legislative data. It is community-maintained rather than an official Plural/OpenStates project, so I would audit it before depending on it, but it is directly applicable to OpenDiscourse. ([GitHub][3])

There are also generated Claude Code API skills for the OpenStates API itself, although I consider the actual OpenStates MCP/API more interesting than a generated instruction-only skill. ([LAP Registry][4])

### FEC

There are already FEC-specific agent tools.

`sh-patterson/fec-mcp-server` exposes candidate search, committee finances, receipts, disbursements, independent expenditures, donor search and other OpenFEC functionality. ([GitHub][5])

There are also standalone Claude Code skills specifically for FEC filings that understand FEC schedules, large-filings streaming and field mappings. ([ClaudSkills][6])

For OpenDiscourse, though, I'd keep your existing bulk FEC ingestion as authoritative and use these tools for **development, validation, discovery and spot checks**.

### FRED / ALFRED

`shanehull/fred-mcp` is unusually complete. It wraps the FRED API with typed MCP tools and includes FRED series, releases, sources, tags, GeoFRED and importantly **historical vintages / ALFRED-style queries**. ([GitHub][7])

That would fit OpenDiscourse very nicely because Claude could ask:

> Find the correct unemployment series for counties and inspect its available historical vintages.

…and then our deterministic connector can actually ingest the selected series.

### USAspending

There are several implementations. `boejucci/usaspending-mcp` provides about 25 tools around awards, recipients, agencies, NAICS/PSC and subawards. ([GitHub][8])

There are also more recent read-only implementations specifically designed for research and aggregation over geography/time. ([GitHub][9])

I'd pick **one**, audit it, and vendor/pin that choice rather than installing four overlapping USAspending servers.

### Regulation

`regulations-mcp` is almost exactly what I described in our previous discussion: one MCP covering:

```text
Federal Register
+
eCFR
+
Regulations.gov
```

It can search rules, read CFR sections, browse CFR structure, locate public comment periods and query regulatory dockets. ([GitHub][10])

There's also a simpler Federal Register-only MCP. ([GitHub][11])

For us, I'd choose the broader `regulations-mcp`.

### Courts

This one is particularly strong because it is no longer merely a hobby project.

**Free Law Project now operates an official CourtListener MCP server** providing access to CourtListener's case law, dockets, RECAP/PACER material, judges, oral arguments, citation tools and alerts. ([Free Law Project][12])

Claude Code can connect directly to it:

```bash
claude mcp add --transport http courtlistener https://mcp.courtlistener.com/
```

Free Law Project documents that exact Claude Code configuration. ([GitHub][13])

That is one I'd absolutely use rather than us building a CourtListener agent interface ourselves.

---

# The data-engineering skills are actually even more important

The domain MCPs are fun, but these may save us **more development time**.

### Microsoft PostgreSQL Skills

Microsoft has released a proper **Postgres Skills** plugin containing roughly 32 PostgreSQL-focused subskills along with a Postgres MCP server. It covers schema design, indexing, query performance, security, operations, RAG/vector functionality and graph-related work. ([GitHub][14])

Install for Claude Code:

```bash
claude plugin marketplace add microsoft/postgres-skills
claude plugin install postgres-skills@postgres-skills
```

For OpenDiscourse I would initially connect its MCP using a **read-only database role/profile**, then grant write access only where necessary.

This is a strong match for us.

---

# dbt has official Agent Skills now

dbt Labs publishes `dbt-agent-skills`.

They teach Claude how to:

* create/refactor dbt models
* inspect sources
* create tests
* debug dbt errors
* document models
* work with the semantic layer
* manage dependencies

([GitHub][15])

Install:

```text
/plugin marketplace add dbt-labs/dbt-agent-skills
/plugin install dbt@dbt-agent-marketplace
```

Given that OpenDiscourse already has `dbt/`, I would install this immediately.

---

# There is a dlt skill

This is especially relevant because OpenDiscourse already has `dlt` as an optional ingestion dependency.

`untitled-data-company/data-skills` provides:

```text
dlt-skill
dlt-dagster
uv
```

The `dlt-skill` teaches agents how to correctly construct data pipelines using `dlt`. ([GitHub][16])

Install:

```bash
npx skills add untitled-data-company/data-skills --skill dlt-skill
```

I would install **`dlt-skill`**, but not `dlt-dagster`, because we're already using Prefect and I don't want to introduce Dagster for no reason.

---

# Airbyte is now quite interesting for us

This changed more than I realized.

Airbyte now explicitly ships **agent skills for Claude Code/Codex and an Agent CLI/SDK**. Its agent can discover connectors, inspect schemas and build integrations from existing Airbyte connectors. ([GitHub][17])

The skills include concepts like:

```text
discovering-connectors
bootstrapping-agent
building-multi-connector-agent
airbyte-sdk-reference
```

([GitHub][18])

Claude Code installation:

```text
/plugin marketplace add airbytehq/airbyte-agent-sdk
/plugin install airbyte-agent-sdk@airbyte-agent-sdk
```

or cross-agent:

```bash
npx skills add airbytehq/airbyte-agent-sdk
```

([GitHub][19])

This is important because before writing **any generic REST API ingestion connector**, Claude could ask Airbyte:

> Is there already a maintained connector for this source?

That's exactly the behavior we want.

---

# One surprisingly relevant Claude skill

I found `JonGerhardson/federal-agent`, which is specifically a Claude Code skill for:

```text
FPDS
USAspending.gov
SAM.gov
```

and importantly documents **bulk extraction approaches that avoid API-rate-limit problems**. ([GitHub][20])

This one lines up very closely with OpenDiscourse's government-spending component.

I wouldn't blindly let it dictate architecture, but I'd absolutely install/read it as reusable domain knowledge.

---

# DuckDB MCP also makes sense for our lake

We don't need Claude connecting only to PostgreSQL.

A DuckDB MCP can let Claude inspect:

```text
raw/*.json
raw/*.csv
normalized/*.parquet
```

without first loading them into Postgres.

`mcp-server-duckdb` supports Claude Code directly and can expose DuckDB query/schema functionality. ([GitHub][21])

That would make workflows like this possible:

```text
Claude
  ↓
DuckDB MCP
  ↓
inspect GovInfo ZIP extraction
inspect OpenStates Parquet
inspect FEC partitions
inspect Census bulk files
  ↓
design/verify transform
  ↓
dbt / Python
  ↓
PostgreSQL
```

That's a very natural match for your lakehouse architecture.

---

# I would install this OpenDiscourse Claude stack

Rather than installing hundreds of random skills, I'd start with this set:

```bash
# PostgreSQL expertise + MCP
claude plugin marketplace add microsoft/postgres-skills
claude plugin install postgres-skills@postgres-skills

# dbt
claude plugin marketplace add dbt-labs/dbt-agent-skills
claude plugin install dbt@dbt-agent-marketplace

# dlt ingestion skill
npx skills add untitled-data-company/data-skills --skill dlt-skill

# Airbyte connector discovery/development
npx skills add airbytehq/airbyte-agent-sdk

# CourtListener
claude mcp add --transport http courtlistener https://mcp.courtlistener.com/

# Then project-scoped MCPs after review:
# CongressMCP
# Census Bureau MCP
# FRED MCP
# OpenStates MCP
# FEC MCP
# USAspending MCP
# regulations-mcp
# DuckDB MCP
```

The Skills CLI itself is now a useful cross-agent mechanism: `npx skills add owner/repo` can install Agent Skills into Claude Code, Codex and many other supported agent environments. ([Skills][22])

That matters for us because we don't have to maintain a separate Claude-only version and Codex-only version of everything.

---

## And then I think we should make **one OpenDiscourse-specific Skill**

This is where I think we can improve your project considerably.

Instead of loading your `AGENTS.md` with another 1,000 lines, create:

```text
.claude/
└── skills/
    └── government-data-ingestion/
        ├── SKILL.md
        └── references/
            ├── source-selection.md
            ├── acquisition-patterns.md
            ├── identity-resolution.md
            ├── provenance.md
            └── source-catalog.yaml
```

That skill wouldn't implement government APIs itself.

It would teach Claude/Codex:

```text
Before implementing an ingestion connector:

1. Search source catalog.
2. Check official API/bulk source.
3. Check known Python library.
4. Check Airbyte connector.
5. Check known MCP.
6. Check maintained GitHub acquisition project.
7. Prefer official bulk data for history.
8. Prefer APIs for incremental updates.
9. Never write a scraper if maintained acquisition exists.
10. Preserve raw response/file.
11. checksum artifact.
12. stage provider-shaped records.
13. validate.
14. COPY typed data into PostgreSQL.
15. retain source IDs.
16. never resolve people by name alone.
17. add tests + rerun/idempotency checks.
```

Then Claude could automatically combine the specialized tooling:

```text
OpenDiscourse Skill
        │
        ├── CongressMCP
        ├── Census MCP
        ├── OpenStates MCP
        ├── FEC MCP
        ├── FRED MCP
        ├── USAspending MCP
        ├── CourtListener MCP
        │
        ├── Airbyte skills
        ├── dlt skill
        ├── dbt skills
        │
        ├── DuckDB MCP
        └── Postgres Skills/MCP
```

That is **much more powerful than asking Claude to figure out every API from scratch every session**.

One caution: the Claude skill/plugin ecosystem is now very decentralized and there are huge public catalogs, so I would not indiscriminately install random `SKILL.md` files. Anthropic has official plugin directories and explicit security-review guidance; for community MCPs we should inspect source, pin versions/commits, use least-privilege credentials, and prefer read-only/local execution where possible. ([GitHub][23])

My next three moves for OpenDiscourse would therefore be: **add the mature engineering skills (Postgres/dbt/dlt/Airbyte), audit and select exactly one MCP for each government domain, and build our own small `government-data-ingestion` orchestration skill that knows when to use each of them.** That should eliminate a lot of custom acquisition code while making Claude Code and Codex considerably better at working on this repo.

[1]: https://github.com/uscensusbureau/us-census-bureau-data-api-mcp?utm_source=chatgpt.com "GitHub - uscensusbureau/us-census-bureau-data-api-mcp: The U.S. Census Bureau Data API MCP connects AI Assistants with official Census Bureau statistics. · GitHub"
[2]: https://github.com/amurshak/congressMCP?utm_source=chatgpt.com "GitHub - amurshak/congressMCP: An MCP server allowing AI agents and MCP clients to interface with the Congress.gov API · GitHub"
[3]: https://github.com/Travis-Prall/openstates-mcp?utm_source=chatgpt.com "GitHub - Travis-Prall/openstates-mcp · GitHub"
[4]: https://registry.lap.sh/apis/openstates-org?utm_source=chatgpt.com "Open States API v3 | LAP Registry"
[5]: https://github.com/sh-patterson/fec-mcp-server?utm_source=chatgpt.com "GitHub - sh-patterson/fec-mcp-server: MCP server for querying FEC campaign finance data - search candidates, track donations, analyze spending, and monitor Super PAC activity · GitHub"
[6]: https://claudskills.com/skills/fecfile/?utm_source=chatgpt.com "Fecfile — Analyze FEC (Federal Election | ClaudSkills"
[7]: https://github.com/shanehull/fred-mcp?utm_source=chatgpt.com "GitHub - shanehull/fred-mcp: MCP server for the Federal Reserve Economic Data (FRED) API. Covers the full API: series, categories, releases, sources, tags, and GeoFRED maps. · GitHub"
[8]: https://github.com/boejucci/usaspending-mcp?utm_source=chatgpt.com "GitHub - boejucci/usaspending-mcp: MCP for connecting to USA Spending, using endpoints for researching awards and awardees, not opportunities · GitHub"
[9]: https://github.com/haydentbs/usaspending-mcp-server?utm_source=chatgpt.com "GitHub - haydentbs/usaspending-mcp-server: Read-only MCP server for exploring USAspending.gov federal spending data · GitHub"
[10]: https://github.com/stark256-spec/regulations-mcp?utm_source=chatgpt.com "GitHub - stark256-spec/regulations-mcp: MCP server for live U.S. federal regulations — Federal Register, eCFR, Regulations.gov. Works with any LLM (Claude, GPT-4o, Gemini, Mistral, Llama, Ollama). · GitHub"
[11]: https://github.com/aml25/federal-register-mcp?utm_source=chatgpt.com "GitHub - aml25/federal-register-mcp: MCP server for accessing the Federal Register API - search executive orders, rules, and federal documents · GitHub"
[12]: https://free.law/2026/05/12/courtlistener-is-now-available-inside-claude/?utm_source=chatgpt.com "AI Tools and Assistants such as Claude Can Now Connect to CourtListener's Full Functionality | Free Law Project | Making the legal ecosystem more equitable and competitive."
[13]: https://github.com/freelawproject/courtlistener-api-client/blob/main/MCP_README.md?utm_source=chatgpt.com "courtlistener-api-client/MCP_README.md at main · freelawproject/courtlistener-api-client · GitHub"
[14]: https://github.com/microsoft/postgres-skills?utm_source=chatgpt.com "GitHub - microsoft/postgres-skills: Agent skills and plugins for PostgreSQL — vendor-agnostic best practices plus Azure-specific patterns that AI coding agents can't learn from training data · GitHub"
[15]: https://github.com/dbt-labs/dbt-agent-skills?utm_source=chatgpt.com "GitHub - dbt-labs/dbt-agent-skills: A curated collection of Agent Skills for working with dbt, to help AI agents understand and execute dbt workflows more effectively. · GitHub"
[16]: https://github.com/untitled-data-company/data-skills?utm_source=chatgpt.com "GitHub - untitled-data-company/data-skills · GitHub"
[17]: https://github.com/airbytehq/airbyte/blob/master/docs/ai-agents/get-started/developer-quickstart/readme.md?utm_source=chatgpt.com "airbyte/docs/ai-agents/get-started/developer-quickstart/readme.md at master · airbytehq/airbyte · GitHub"
[18]: https://github.com/airbytehq/airbyte/blob/master/docs/ai-agents/get-started/developer-quickstart/skills/codex.md?utm_source=chatgpt.com "airbyte/docs/ai-agents/get-started/developer-quickstart/skills/codex.md at master · airbytehq/airbyte · GitHub"
[19]: https://github.com/airbytehq/airbyte-agent-sdk/blob/main/README.md?utm_source=chatgpt.com "airbyte-agent-sdk/README.md at main · airbytehq/airbyte-agent-sdk · GitHub"
[20]: https://github.com/JonGerhardson/federal-agent?utm_source=chatgpt.com "GitHub - JonGerhardson/federal-agent: Coding agent skill to access federal contract and spending data from FPDS, USAspending.gov, and SAM.gov APIs · GitHub"
[21]: https://github.com/boettiger-lab/mcp-server-duckdb?utm_source=chatgpt.com "GitHub - boettiger-lab/mcp-server-duckdb · GitHub"
[22]: https://www.skills.sh/docs?utm_source=chatgpt.com "Documentation | Skills"
[23]: https://github.com/anthropics/claude-plugins-official?utm_source=chatgpt.com "GitHub - anthropics/claude-plugins-official: Official, Anthropic-managed directory of high quality Claude Code Plugins. · GitHub"
