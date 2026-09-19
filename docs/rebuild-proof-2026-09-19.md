# Rebuild proof: Congress 108 bills (2026-09-19)

Question: is "rebuildable from raw" true? One small dataset, tested end to end
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
