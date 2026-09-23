---
title: 'Technical research: OpenDiscourse public-policy source-tool adoption'
type: technical
topic: 'OpenDiscourse public-policy source-tool adoption'
decision: 'Choose a repeatable reuse policy and prioritized adoption path for future public-data sources.'
source: native web research
status: complete
preset: standard
validation: normal
created: '2026-09-23'
updated: '2026-09-23'
---

# Source-tool adoption research

## Executive summary

Use other projects to reduce acquisition and parsing work, but do not import
their databases or let their internal models become OpenDiscourse’s model. The
right boundary is: **official source bytes → retained evidence → a small source
Connector → typed OpenDiscourse tables**. This preserves reproducibility while
allowing us to adopt well-maintained clients selectively.

The clearest immediate wins are already in reach: type CBO references already
present in BILLSTATUS, finish the official Voteview Connector, and later use
official FEC bulk files plus the API for reconciliation. `beaapi` is the only
researched package I recommend pre-approving for a future optional wrapper. The
largest projects—USAspending’s own service and CourtListener—are valuable
references and APIs, but not codebases to embed or self-host as dependencies.

The important caveat is that maximizing data does **not** mean loading every
available public corpus at once. Each additional source creates continuing work:
updates, licensing/terms, storage, identity links, coverage checks, and user
interpretation. We should maximize useful, traceable data one source at a time.

## Decision framework

Every candidate must pass these seven checks before implementation:

1. The original publisher supplies a stable API or bulk release.
2. The source has stable keys that can join without names.
3. Terms allow the intended research use and retention.
4. We can retain the exact supplied bytes and rerun the acquisition on a new
   machine.
5. We can measure completeness against a publisher count or manifest.
6. The data has a defined analytical use, not merely speculative future value.
7. A maintained tool materially saves work without hiding transformations or
   imposing its own database/service stack.

If a candidate fails any item, it stays catalogued but does not receive a
Connector. This is the practical guardrail against a cluttered, fragile system.

## Findings and adoption decisions

| Area | Decision | Why |
|---|---|---|
| CBO cost estimates | Adopt existing BILLSTATUS data first | CBO supplies XML metadata back to the 105th Congress, but bill files already retain the CBO links needed for the current task. Type those references before a second downloader. [1] |
| FEC | Official bulk files + API reconciliation | The FEC provides large transaction-level bulk files and a nightly-updated API tied to underlying report/file identifiers. Bulk is the evidence/history path; API helps discover and reconcile. Do not adopt a third-party database schema. [2] |
| Lobbying (LDA) | Direct official Connector later | LDA.gov exposes the official API for registration, activity, and contribution reports. A modest Python HTTP adapter is simpler than inheriting an unrelated client model. [3] |
| USAspending | Direct official API/bulk Connector; evaluate `usaspending-orm` as optional | The official service is a substantial multi-service application, so self-hosting or embedding it is needless complexity. The small ORM may save request/pagination work, but must be sandbox-evaluated and never replace retained responses. [4] [5] |
| Federal Register / Regulations.gov | Direct official Connectors later | Both publish usable APIs. FederalRegister.gov warns that legal reliance should be verified against the official GovInfo edition, so retain GovInfo evidence for legal claims. [6] [7] |
| CourtListener | Later, separately scoped evaluation | It offers API, bulk-data guidance, webhooks, and replication, but access/rate limits are membership-based. Do not budget a full-corpus load until scope, cost, and rights are explicit. [8] |
| BEA | Approve `beaapi` as an optional adapter | The package is published by BEA’s GitHub organization, supports metadata discovery, and is CC0. Configure or disable its local cache so project data stays under `DATA_ROOT`. [9] |
| BLS | Use direct HTTP with shared helpers | BLS’s own Python example is thin enough that a new package is not justified. Keeping our request/retention logic is clearer. [10] |
| Elections | Use OpenElections and MIT Election Lab as comparison/method sources | Both add useful standardized coverage, but source-level evidence and person links require separate verification. Do not make either the sole authority. [11] [12] |
| Financial disclosures / stock trades | Hold | The House portal states meaningful use restrictions, and the project still lacks a safe person-identifier bridge. No scraper or third-party aggregation should be adopted yet. [13] |

## Recommended organization standard

For each source, create exactly these owned pieces only when needed:

```text
inventory/fields/<dataset>.yaml       # every field and its disposition
providers/<source>.py                 # source HTTP/auth/download details
ingestion/<source>.py                 # Connector lifecycle and parsing
repositories/<source>.py              # database operations
sql/query/<source>/                   # named, testable SQL statements
tests/test_<source>_connector.py      # success, resume, failure, provenance
```

The source’s full record remains available beside the typed, query-friendly
columns. A shared helper may handle generic HTTP, pagination, compression, CSV,
or archive handling, but it must never contain source-specific branches. A
source package or upstream repo stays behind `providers/<source>.py`, making it
replaceable.

Naming rule: use the publisher/domain for the Connector (`voteview`, `fec`,
`cbo`, `lda`, `usaspending`), and the stable catalog key for its data set
(`congress.voteview`, `fec.*`). Avoid vague names such as `utilities`,
`helpers`, `data_loader`, or `politics`.

## Priority roadmap

1. **Now:** complete independent review of Voteview, merge it, then run its
   live load only with explicit approval.
2. **Next:** type CBO estimates, committee reports, and other already-retained
   BILLSTATUS fields. This is high value with no new download.
3. **Then:** finish field audits of current Congress, Census, FRED, Treasury,
   and FEC loads before adding more domains.
4. **After the identity gate opens:** FEC as a dedicated Connector; evaluate
   LDA lobbying and USAspending as separate scoped stories.
5. **Later:** regulatory and court sources, then elections. Financial disclosure
   data waits for a reviewed identifier bridge and terms analysis.

## Contrary evidence and limits

The tempting alternative is to self-host an existing end-to-end project. The
official USAspending codebase demonstrates why that is not the easy path: it
includes its own service, database, search, and container requirements. [5]
Likewise, CourtListener has valuable data but access conditions are not a
guarantee of a free, unlimited whole-corpus ingest. [8] These are reasons to
wrap their public interfaces, not to copy their systems.

## Open questions

- Before adopting `usaspending-orm`, inspect its current license, release
  cadence, error behavior, and API coverage in a small isolated proof.
- Before LDA, FEC, CourtListener, or disclosure implementation, record source
  terms, historical coverage, expected storage, and stable identifiers in the
  source specification.
- The reuse catalog contains an obsolete Voteview entry that says to use the
  old `unitedstates/congress` Voteview task. The approved implementation instead
  uses the three current official UCLA exports; correct the catalog in the
  Voteview cleanup.

## Source appendix

| Ref | Source | Accessed | Confidence |
|---|---|---:|---|
| [1] | [CBO Cost Estimates XML](https://www.cbo.gov/cost-estimates/xml) | 2026-09-23 | High |
| [2] | [FEC OpenFEC developer documentation](https://api.open.fec.gov/developers) | 2026-09-23 | High |
| [3] | [LDA.gov API](https://lda.gov/api/) | 2026-09-23 | High |
| [4] | [USAspending API](https://api.usaspending.gov/) | 2026-09-23 | High |
| [5] | [USAspending API source repository](https://github.com/fedspendingtransparency/usaspending-api) and [usaspending-orm](https://github.com/planetary-society/usaspending-orm) | 2026-09-23 | Medium |
| [6] | [Federal Register API documentation](https://www.federalregister.gov/developers/documentation/api/v1) | 2026-09-23 | High |
| [7] | [Regulations.gov API](https://open.gsa.gov/api/regulationsgov/) | 2026-09-23 | High |
| [8] | [CourtListener developer access overview](https://www.courtlistener.com/help/) | 2026-09-23 | Medium |
| [9] | [BEA `beaapi` repository](https://github.com/us-bea/beaapi) | 2026-09-23 | High |
| [10] | [BLS Python API guidance](https://www.bls.gov/developers/api_python.htm) | 2026-09-23 | High |
| [11] | [OpenElections repositories](https://github.com/openelections) | 2026-09-23 | Medium |
| [12] | [MIT Election Lab](https://electionlab.mit.edu/) and [2024 Precinct Project](https://electionlab.mit.edu/articles/inside-2024-precinct-project) | 2026-09-23 | Medium |
| [13] | [House Clerk financial-disclosure search](https://disclosures-clerk.house.gov/FinancialDisclosure/ViewSearch) | 2026-09-23 | High |

## Staleness map

Re-check package maintenance, source terms, API access, and rate limits before
the relevant Connector is specified; these change faster than the architectural
recommendation. Re-check the adoption table no later than 2027-03-23, and
re-check any source immediately before implementation.
