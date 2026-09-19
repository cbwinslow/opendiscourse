# Source matrix (measured 2026-09-19)

What "every loaded source" is and how each is acquired today. `Gap` is what the kit
must close. Sizes are `ingest.artifact` bytes; the "derived" column is what a rebuild
re-creates. Retained files are never re-created by deleting them.

| Dataset id | Origin | Raw (artifacts, bytes) | Derived | Download today | Ingest today | Gap |
|---|---|---|---|---|---|---|
| `census.api_catalog`, `census.acs_5` | Census Data API | 4 small (skipped) | catalog rows | `plan-run censusmeta` | same | none; needs `CENSUS_API_KEY` |
| `census.acs_5_bulk` | Census ACS 5-year detailed tables | 2,264 files, 110 GB | `stage.acs_bulk_row` 5 GB, `fact.acs_bulk_estimate` 99 GB | `ingest acs-bulk-plan`, `-preview`, `-approve`, `-download` | `-stage`, `-load` | selection lives in gitignored `meta/bulk-plans` (about 30 plans); 4 `Table_Shells.txt` unregistered |
| `census.business_patterns` | Census CBP | 122 files, 773 MB | `stage.cbp_row` 22 GB, `fact.business_pattern` | `ingest cbp-bulk-*` | same | selection not tracked |
| `census.decennial` | Census 2020 DHC | 2 files, 2.2 GB | `stage.dhc_geo_row`, DHC values | `ingest dhc-bulk-*` | same | selection not tracked |
| `census.population_estimates` | Census PEP | 4 files, 6 MB | `stage.pep_row` | `ingest pep-bulk-*` | same | selection not tracked |
| `census.tiger` | Census TIGER/Line | 39 files, 6.2 GB | `stage.tiger_feature` 10 GB, `core.geography_boundary` | `ingest tiger-bulk-*` | same | selection not tracked |
| `congress.govinfo_billstatus` | GovInfo BILLSTATUS bulk, Congresses 108-119 | 114 zips, 692 MB (16 rows under `/mnt/storage`) | bills, actions, sponsors, records, laws, amendments | `sync-billstatus --congress N` | same (one step) | 16 legacy-path rows; 96 stale `.lock` files |
| `congress.legislators` | `unitedstates/congress-legislators` (git) | 2 files, 10 MB (rows point into the checkout) | people, identifiers, terms, posts, divisions | `scripts/bootstrap_upstream.sh` | `load-legislators` | registry rows point outside `DATA_ROOT`; git checkout is not an artifact download |
| `openstates.dump` | OpenStates monthly dump | 2 files, 10 GB | separate `openstates` DB, FDW, people, organizations, votes | `bootstrap openstates-dump --year Y --month M [--data]` | `validate-openstates-snapshot`, restore, `load-openstates-*` | restore and FDW setup need a superuser once; promotion follows AD-8 |
| `fec.campaign_finance` | FEC bulk files | 50 archives, 20 GB, all under `/mnt/storage` | `stage.fec_row` 74 GB | **none** | `ingest fec-bulk-register`, `-stage` (legacy root only) | no downloader: build one (last phase); layout question open |
| BLS, FRED, Treasury | provider APIs | tiny | `fact` series | `plan-run fredcore`, `bootstrap bls-core`, `treasury-curve` | same | optional; FRED/Treasury have known failures |

Order: `init-db`, catalog and metadata, then people (legislators, then OpenStates
seeds), geography (TIGER, PEP, DHC), Census facts, BILLSTATUS (joins people by
BioGuide), FEC last. Verify with `research-db loaded`, `coverage`, `census-health`,
`congress-health`.
