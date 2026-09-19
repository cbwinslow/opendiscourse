# Rebuild proof: bills, people, population estimates (2026-09-19)

Question: is "rebuildable from raw" true? Small datasets, tested end to end
before building the rebuild kit (`_bmad-output/specs/spec-rebuild-kit/SPEC.md`).

## What was run

Scratch database (a fresh `postgis/postgis:17-3.5` container) and a scratch lake inside
the project (`./data-lake/rebuild-proof/raw`, gitignored). Nothing touched the live
warehouse or lake.

```
DATABASE_URL=postgresql://postgres:proof@localhost:55433/opendiscourse \
DATA_ROOT=./data-lake/rebuild-proof/raw \
  uv run research-db init-db                          # 3 s, all Alembic revisions
  uv run research-db sync-billstatus --congress 108   # 5 m 50 s, exit 0, coverage complete
  uv run research-db sync-billstatus --congress 108   # rerun
```

## Result

| Check | Outcome |
|---|---|
| Downloaded files | 8 zips, 38 MB; **same names, and therefore the same sha256, as the zips downloaded weeks ago into the live lake** (GovInfo has not changed them) |
| Rows | bill 10,667; actions 73,002; source records 10,667; sponsorships 156,547; subjects 242,020 |
| Content vs live | for all five tables, row counts **and** an order-independent md5 of the natural-key and content columns (no surrogate ids) are identical to the live warehouse |
| Rerun | 0 loaded, 0 downloaded, 8 artifacts and 8 zips unchanged, fingerprint unchanged |

## What it does not prove

- People links: the fingerprint uses each sponsor's source identifier, not the
  `person_id` join, which depends on the legislators load. Order in the kit: people first, then compare joins.
- Only bills. Census, OpenStates and FEC are untested from empty.
- Interrupt-and-resume was not exercised here (it is covered by the connector tests).
- 8 `*.zip.lock` sidecars were left behind (known debt, audit finding 8).

## Findings for the kit

- A bills rebuild needs only `init-db` then one command per Congress; no plan files, no
  hand steps. Extrapolating from 108 (38 MB, 6 min), Congresses 108 to 119 is roughly an
  hour or two; this is an estimate, not a measurement.
- The fingerprint query is the seed of the kit's verify step (CAP-3); it must be
  parameterised per Congress and per table before it ships.

## Round 2: people, sponsor links, population estimates

Same scratch database and lake (fresh container, `init-db`, then the commands below).

| Step | Outcome |
|---|---|
| `load-legislators` | 12,770 people and 97,319 identifiers loaded from the same two YAML files (same sha256) as live. **Then failed cleanly**: terms need the House and Senate organizations, which come from `load-openstates-organizations`, so OpenStates must be restored before terms. People stayed loaded; the run is marked failed. |
| `sync-billstatus --congress 108` after people | bills, actions, records, sponsorships, subjects identical to live. **Sponsor-to-person links identical** (156,547 rows, same hash). |
| PEP 2010-2020 from a hand-written *draft* plan: `pep-bulk-preview`, `-approve --geography nation --geography state --geography county`, `-download`, `-stage`, `-load` | stage 3,247 rows (as live), 35,717 estimates; **fact rows and hash identical to live**; source CSVs have the same sha256. No interactive catalog was needed: a draft plan is a small YAML of URLs. |

Queries: `sql/query/verify/` (`psql -v congress=108 -f ...`); the bills query reproduces the live hash.

### Differences, all explained

- **People names and extra identifiers.** 246 people have different display names (live "Robert Aderholt", rebuilt "Robert B. Aderholt") and live has 2,048 more identifiers (`ocd` 722, `twitter` 579, `facebook` 371, `youtube` 340, a few others). The legislators loader documents social media as out of scope, so these come from the OpenStates people load layered on top. Not a rebuild defect, but **it cannot be proven until OpenStates is restored in scratch**, and it shows a rule is missing: which source's name wins for a federal person (today the last writer).
- **Geography names.** The same 3,196 geography ids exist; 3,141 names differ ("Autauga" live, "Autauga County" from the PEP load) because another loader overwrote the name. Same lesson: last writer wins, so load order changes names.

### Findings for the kit

1. Order: schema, people (identifiers), OpenStates restore, organizations, terms, then bills and everything else. Terms cannot run before OpenStates.
2. A fresh Docker Postgres answers `pg_isready` before its init restart finishes; the first `init-db` failed. The kit must retry until a real query works.
3. Tracked config for Census can be the small draft plans (URLs only), committed under `inventory/`; the kit copies them into `meta/bulk-plans` and runs the five steps. The approval step's geography choice must be recorded too.
4. Decide a name-precedence rule (people and geography) before the kit, or two rebuilds of the same data can differ in display names. Proposal: BioGuide-based legislators data owns federal person names; TIGER/Census own geography names; OpenStates and PEP add identifiers only.
5. Tests of the kit should compare fingerprints excluding fields with no precedence rule until one exists.
