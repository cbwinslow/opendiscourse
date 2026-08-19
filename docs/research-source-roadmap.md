# Research source roadmap

OpenDiscourse is a provenance-first research database, not a claim that every
public dataset is already loaded. `inventory/sources.yaml` is the authoritative
source catalog and `inventory/progress.yaml` is the operational truth. This
roadmap helps researchers choose a defensible starting panel and helps agents
add coverage without bypassing contracts, capacity checks, or provenance.

## Current research spine

| Domain | Primary sources | Current position | Next governed action |
| --- | --- | --- | --- |
| Demography and housing | Census ACS 5-year, Decennial DHC, PEP, TIGER | Broad ACS/CBP/PEP/TIGER coverage is loaded; ACS comprehensive housing deltas are downloaded but not loaded. | Stage and load only the already-approved ACS delta plans after capacity and health checks. |
| Economy and labor | FRED/ALFRED, Treasury, BLS, BEA | FRED core and Treasury curves are loaded; BLS is a small, stale national pilot; BEA is registered only. | Define a reviewed LAUS/CPI geography and time scope before loading; then add BEA regional contract(s). |
| Business and public finance | Census CBP, Treasury Fiscal Data, USAspending | Historical CBP is loaded; Treasury yields are loaded; fiscal/award data is registered but unloaded. | Approve a bounded fiscal/debt or award contract with grain and retention rules. |
| Politics and policy | Congress.gov, GovInfo, OpenStates, FEC | OpenStates snapshot is isolated/read-only; congressional and GovInfo evidence has validation paths; FEC staging is partial. | Use bounded official contracts; do not promote FEC facts until identity resolution is reviewed. |
| Elections and disclosures | FEC, official state results, licensed partner datasets | Sources are registered; national result normalization is not yet approved. | Establish licensing, official-source coverage, and a stable election/contest identity model first. |
| Crime, health, education, environment | FBI CDE, CDC/CMS, NCES, EPA, HUD | FBI is registered; other sources are candidates, not active ingestion commitments. | Add one provider at a time using `docs/adding-a-provider.md`, a reviewed contract, and source-specific validation. |

## Rules for adding a source

1. Prefer the authoritative publisher and retain its identifiers, URL, and
   immutable response/file checksum.
2. Define grain, coverage, cadence, licensing/access constraints, and an
   idempotency key in `inventory/sources.yaml` before writing a connector.
3. Add a disabled, bounded contract before any live observation download.
4. Run the capacity gate for bulk sources. Never treat a legacy cache as
   authoritative until it is compared against the publisher.
5. Keep provider transport/pacing in `providers/`, persistence in
   `repositories/`, and provider-shaped bulk work in `stage`/COPY paths.
6. Add real PostgreSQL/PostGIS tests for the resulting canonical transform,
   provenance, resume, and rerun behavior.

## Recommended researcher starting panels

- **Place-year social conditions:** ACS 5-year + PEP + CBP + TIGER, with ACS
  estimate and margin-of-error fields retained separately.
- **Macro/financial conditions:** FRED/ALFRED + Treasury yield curves; use
  ALFRED vintages for revision-aware analysis.
- **Policy and representation:** congressional bills/actions, OpenStates
  source evidence, roll calls, and officially bounded election data.

Do not make causal claims merely by joining geography to policy data. The
geographic/mart caveats in `docs/blueprint.md` and the source coverage recorded
in `inventory/progress.yaml` are part of every analysis's provenance.
