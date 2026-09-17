# Live OpenDiscourse schema catalog

Schema-only snapshot of the operator warehouse. **Not a second
migration path.** Alembic owns catalog/core/fact/ingest/stage
contracts; `sql/query/` is runtime SQL; `sql/NNN_*.sql` is bootstrap
legacy reference.

| Field | Value |
|---|---|
| Captured | 2026-09-17T04:29:52+00:00 |
| Database | `opendiscourse` |
| PostgreSQL | 17.11 (Ubuntu 17.11-1.pgdg24.04+2) |
| Database size | 234 GB (data; dump is schema-only) |
| Alembic head | `c4f7a2d9e651` |

## Extensions

| Extension | Version |
|---|---|
| `pg_trgm` | 1.6 |
| `pgcrypto` | 1.3 |
| `plpgsql` | 1.0 |
| `postgis` | 3.6.4 |
| `postgres_fdw` | 1.1 |
| `unaccent` | 1.1 |
| `vector` | 0.8.5 |

## Object inventory

| Schema | Name | Kind | Est. rows | Total size | Comment |
|---|---|---|---:|---|---|
| `catalog` | `basket` | table | 10 | 80 kB |  |
| `catalog` | `basket_item` | table | 48 | 32 kB |  |
| `catalog` | `dataset` | table | 28 | 256 kB |  |
| `catalog` | `dataset_field` | table | 225472 | 124 MB |  |
| `catalog` | `discovery` | table | 1 | 32 kB |  |
| `catalog` | `plan` | table | 5 | 80 kB |  |
| `catalog` | `provider` | table | 10 | 80 kB |  |
| `catalog` | `resource` | table | 703329 | 1231 MB |  |
| `catalog` | `resource_field` | table | -1 | 16 kB |  |
| `catalog` | `snapshot` | table | -1 | 48 kB |  |
| `catalog` | `snapshot_resource` | table | 12020 | 1544 kB |  |
| `core` | `bill` | table | 36540 | 13 MB |  |
| `core` | `bill_action` | table | 157971 | 70 MB |  |
| `core` | `bill_committee` | table | 45458 | 18 MB |  |
| `core` | `bill_document` | table | 42781 | 7112 kB |  |
| `core` | `bill_identifier` | table | 73632 | 21 MB |  |
| `core` | `bill_sponsorship` | table | 402817 | 194 MB |  |
| `core` | `bill_subject` | table | 125912 | 54 MB |  |
| `core` | `document` | table | 42488 | 25 MB |  |
| `core` | `document_chunk` | table | -1 | 32 kB |  |
| `core` | `embedding` | table | -1 | 24 kB |  |
| `core` | `geography` | table | 49742 | 16 MB |  |
| `core` | `geography_boundary` | table | 377428 | 10 GB |  |
| `core` | `instrument` | table | -1 | 16 kB |  |
| `core` | `instrument_symbol` | table | -1 | 16 kB |  |
| `core` | `jurisdiction` | table | -1 | 32 kB |  |
| `core` | `legislative_session` | table | -1 | 48 kB |  |
| `core` | `membership` | table | -1 | 32 kB |  |
| `core` | `organization` | table | 242 | 136 kB |  |
| `core` | `organization_identifier` | table | 242 | 104 kB |  |
| `core` | `person` | table | 723 | 256 kB |  |
| `core` | `person_identifier` | table | 9838 | 2040 kB |  |
| `core` | `roll_call` | table | 1788 | 1096 kB |  |
| `fact` | `acs_bulk_estimate` | table | 280819136 | 99 GB |  |
| `fact` | `business_pattern` | table | 30618374 | 12 GB |  |
| `fact` | `decennial_dhc_value` | table | 22758 | 7696 kB |  |
| `fact` | `market_bar` | table | -1 | 16 kB |  |
| `fact` | `measurement` | table | 321460 | 196 MB |  |
| `fact` | `member_vote` | table | 464784 | 69 MB |  |
| `fact` | `population_estimate` | table | 55205 | 23 MB |  |
| `ingest` | `artifact` | table | 2505 | 2504 kB |  |
| `ingest` | `cursor` | table | -1 | 32 kB |  |
| `ingest` | `identity_exception` | table | -1 | 64 kB |  |
| `ingest` | `raw_payload` | table | 170 | 11 MB |  |
| `ingest` | `resume_cursor` | table | -1 | 32 kB |  |
| `ingest` | `run` | table | 264 | 152 kB |  |
| `leg` | `bill` | view | -1 | 0 bytes |  |
| `leg` | `person` | view | -1 | 0 bytes |  |
| `mart` | `mart_geography_year_measurement` | view | -1 | 0 bytes |  |
| `mart` | `mart_roll_call_results` | view | -1 | 0 bytes |  |
| `mart` | `stg_bills` | view | -1 | 0 bytes |  |
| `mart` | `stg_geography` | view | -1 | 0 bytes |  |
| `mart` | `stg_measurements` | view | -1 | 0 bytes |  |
| `mart` | `stg_member_votes` | view | -1 | 0 bytes |  |
| `mart` | `stg_roll_calls` | view | -1 | 0 bytes |  |
| `openstates_source` | `opencivicdata_bill` | foreign table | -1 | 0 bytes |  |
| `openstates_source` | `opencivicdata_billaction` | foreign table | -1 | 0 bytes |  |
| `openstates_source` | `opencivicdata_billdocument` | foreign table | -1 | 0 bytes |  |
| `openstates_source` | `opencivicdata_billsponsorship` | foreign table | -1 | 0 bytes |  |
| `openstates_source` | `opencivicdata_jurisdiction` | foreign table | -1 | 0 bytes |  |
| `openstates_source` | `opencivicdata_legislativesession` | foreign table | -1 | 0 bytes |  |
| `openstates_source` | `opencivicdata_organization` | foreign table | -1 | 0 bytes |  |
| `openstates_source` | `opencivicdata_person` | foreign table | -1 | 0 bytes |  |
| `openstates_source` | `opencivicdata_personidentifier` | foreign table | -1 | 0 bytes |  |
| `openstates_source` | `opencivicdata_personvote` | foreign table | -1 | 0 bytes |  |
| `openstates_source` | `opencivicdata_voteevent` | foreign table | -1 | 0 bytes |  |
| `public` | `alembic_version` | table | -1 | 24 kB |  |
| `stage` | `acs_bulk_row` | table | 5602131 | 5191 MB |  |
| `stage` | `cbp_row` | table | 29237760 | 22 GB |  |
| `stage` | `dhc_geo_row` | table | 11379 | 9288 kB |  |
| `stage` | `fec_row` | table | 101668128 | 74 GB |  |
| `stage` | `pep_row` | table | 6495 | 13 MB |  |
| `stage` | `tiger_feature` | table | 373854 | 10 GB |  |

## Foreign tables

OpenStates is a provider snapshot. These foreign tables are the
approved `openstates_source` FDW surface, not the researcher
contract. Do not copy Django dump tables into `core`.

| Schema | Table | Server | FDW |
|---|---|---|---|
| `openstates_source` | `opencivicdata_bill` | `openstates_local` | `postgres_fdw` |
| `openstates_source` | `opencivicdata_billaction` | `openstates_local` | `postgres_fdw` |
| `openstates_source` | `opencivicdata_billdocument` | `openstates_local` | `postgres_fdw` |
| `openstates_source` | `opencivicdata_billsponsorship` | `openstates_local` | `postgres_fdw` |
| `openstates_source` | `opencivicdata_jurisdiction` | `openstates_local` | `postgres_fdw` |
| `openstates_source` | `opencivicdata_legislativesession` | `openstates_local` | `postgres_fdw` |
| `openstates_source` | `opencivicdata_organization` | `openstates_local` | `postgres_fdw` |
| `openstates_source` | `opencivicdata_person` | `openstates_local` | `postgres_fdw` |
| `openstates_source` | `opencivicdata_personidentifier` | `openstates_local` | `postgres_fdw` |
| `openstates_source` | `opencivicdata_personvote` | `openstates_local` | `postgres_fdw` |
| `openstates_source` | `opencivicdata_voteevent` | `openstates_local` | `postgres_fdw` |

## Relations

### Schema `catalog`

#### `catalog.basket`

- Kind: table
- Estimated rows: 10
- Total size: 80 kB

| Column | Type | Null | Default | Comment |
|---|---|---|---|---|
| `basket_id` | `uuid` | NO | `gen_random_uuid()` |  |
| `name` | `text` | NO |  |  |
| `state` | `text` | NO | `'draft'::text` |  |
| `metadata` | `jsonb` | NO | `'{}'::jsonb` |  |
| `created_at` | `timestamp with time zone` | NO | `now()` |  |
| `updated_at` | `timestamp with time zone` | NO | `now()` |  |

Constraints:

- `basket_state_check` (c): `CHECK (state = ANY (ARRAY['draft'::text, 'review'::text, 'approved'::text, 'archived'::text]))`
- `basket_pkey` (p): `PRIMARY KEY (basket_id)`
- `basket_name_key` (u): `UNIQUE (name)`

Indexes:

- `basket_name_key`: `CREATE UNIQUE INDEX basket_name_key ON catalog.basket USING btree (name)`
- `basket_pkey`: `CREATE UNIQUE INDEX basket_pkey ON catalog.basket USING btree (basket_id)`

#### `catalog.basket_item`

- Kind: table
- Estimated rows: 48
- Total size: 32 kB

| Column | Type | Null | Default | Comment |
|---|---|---|---|---|
| `basket_id` | `uuid` | NO |  |  |
| `resource_id` | `uuid` | NO |  |  |
| `selected_fields` | `jsonb` | NO | `'[]'::jsonb` |  |
| `metadata` | `jsonb` | NO | `'{}'::jsonb` |  |
| `added_at` | `timestamp with time zone` | NO | `now()` |  |

Constraints:

- `basket_item_basket_id_fkey` (f): `FOREIGN KEY (basket_id) REFERENCES catalog.basket(basket_id) ON DELETE CASCADE`
- `basket_item_resource_id_fkey` (f): `FOREIGN KEY (resource_id) REFERENCES catalog.resource(resource_id) ON DELETE RESTRICT`
- `basket_item_pkey` (p): `PRIMARY KEY (basket_id, resource_id)`

Indexes:

- `basket_item_pkey`: `CREATE UNIQUE INDEX basket_item_pkey ON catalog.basket_item USING btree (basket_id, resource_id)`

#### `catalog.dataset`

- Kind: table
- Estimated rows: 28
- Total size: 256 kB

| Column | Type | Null | Default | Comment |
|---|---|---|---|---|
| `dataset_id` | `text` | NO |  |  |
| `provider_id` | `text` | NO |  |  |
| `title` | `text` | NO |  |  |
| `access_method` | `text` | YES |  |  |
| `grain_description` | `text` | YES |  |  |
| `refresh_cadence` | `text` | YES |  |  |
| `priority` | `smallint` | YES |  |  |
| `active` | `boolean` | NO | `true` |  |
| `metadata` | `jsonb` | NO | `'{}'::jsonb` |  |
| `created_at` | `timestamp with time zone` | NO | `now()` |  |
| `updated_at` | `timestamp with time zone` | NO | `now()` |  |

Constraints:

- `dataset_provider_id_fkey` (f): `FOREIGN KEY (provider_id) REFERENCES catalog.provider(provider_id)`
- `dataset_pkey` (p): `PRIMARY KEY (dataset_id)`

Indexes:

- `dataset_pkey`: `CREATE UNIQUE INDEX dataset_pkey ON catalog.dataset USING btree (dataset_id)`

#### `catalog.dataset_field`

- Kind: table
- Estimated rows: 225472
- Total size: 124 MB

| Column | Type | Null | Default | Comment |
|---|---|---|---|---|
| `dataset_id` | `text` | NO |  |  |
| `field_id` | `text` | NO |  |  |
| `label` | `text` | YES |  |  |
| `data_type` | `text` | YES |  |  |
| `description` | `text` | YES |  |  |
| `valid_from` | `date` | NO |  |  |
| `valid_to` | `date` | YES |  |  |
| `metadata` | `jsonb` | NO | `'{}'::jsonb` |  |

Constraints:

- `dataset_field_dataset_id_fkey` (f): `FOREIGN KEY (dataset_id) REFERENCES catalog.dataset(dataset_id)`
- `dataset_field_pkey` (p): `PRIMARY KEY (dataset_id, field_id, valid_from)`

Indexes:

- `dataset_field_pkey`: `CREATE UNIQUE INDEX dataset_field_pkey ON catalog.dataset_field USING btree (dataset_id, field_id, valid_from)`

#### `catalog.discovery`

- Kind: table
- Estimated rows: 1
- Total size: 32 kB

| Column | Type | Null | Default | Comment |
|---|---|---|---|---|
| `discovery_id` | `text` | NO |  |  |
| `dataset_id` | `text` | NO |  |  |
| `state` | `text` | NO | `'idle'::text` |  |
| `cursor` | `jsonb` | NO | `'{}'::jsonb` |  |
| `statistics` | `jsonb` | NO | `'{}'::jsonb` |  |
| `error_message` | `text` | YES |  |  |
| `started_at` | `timestamp with time zone` | YES |  |  |
| `finished_at` | `timestamp with time zone` | YES |  |  |
| `updated_at` | `timestamp with time zone` | NO | `now()` |  |

Constraints:

- `discovery_state_check` (c): `CHECK (state = ANY (ARRAY['idle'::text, 'running'::text, 'paused'::text, 'complete'::text, 'failed'::text]))`
- `discovery_dataset_id_fkey` (f): `FOREIGN KEY (dataset_id) REFERENCES catalog.dataset(dataset_id)`
- `discovery_pkey` (p): `PRIMARY KEY (discovery_id)`

Indexes:

- `discovery_pkey`: `CREATE UNIQUE INDEX discovery_pkey ON catalog.discovery USING btree (discovery_id)`

#### `catalog.plan`

- Kind: table
- Estimated rows: 5
- Total size: 80 kB

| Column | Type | Null | Default | Comment |
|---|---|---|---|---|
| `plan_id` | `text` | NO |  |  |
| `dataset_id` | `text` | NO |  |  |
| `handler` | `text` | NO |  |  |
| `cadence` | `text` | NO |  |  |
| `enabled` | `boolean` | NO | `true` |  |
| `parameters` | `jsonb` | NO | `'{}'::jsonb` |  |
| `metadata` | `jsonb` | NO | `'{}'::jsonb` |  |
| `updated_at` | `timestamp with time zone` | NO | `now()` |  |

Constraints:

- `plan_dataset_id_fkey` (f): `FOREIGN KEY (dataset_id) REFERENCES catalog.dataset(dataset_id)`
- `plan_pkey` (p): `PRIMARY KEY (plan_id)`

Indexes:

- `plan_pkey`: `CREATE UNIQUE INDEX plan_pkey ON catalog.plan USING btree (plan_id)`

#### `catalog.provider`

- Kind: table
- Estimated rows: 10
- Total size: 80 kB

| Column | Type | Null | Default | Comment |
|---|---|---|---|---|
| `provider_id` | `text` | NO |  |  |
| `name` | `text` | NO |  |  |
| `base_url` | `text` | YES |  |  |
| `created_at` | `timestamp with time zone` | NO | `now()` |  |

Constraints:

- `provider_pkey` (p): `PRIMARY KEY (provider_id)`

Indexes:

- `provider_pkey`: `CREATE UNIQUE INDEX provider_pkey ON catalog.provider USING btree (provider_id)`

#### `catalog.resource`

- Kind: table
- Estimated rows: 703329
- Total size: 1231 MB

| Column | Type | Null | Default | Comment |
|---|---|---|---|---|
| `resource_id` | `uuid` | NO | `gen_random_uuid()` |  |
| `dataset_id` | `text` | NO |  |  |
| `resource_key` | `text` | NO |  |  |
| `resource_type` | `text` | NO |  |  |
| `title` | `text` | NO |  |  |
| `summary` | `text` | YES |  |  |
| `universe` | `text` | YES |  |  |
| `release_year` | `integer` | YES |  |  |
| `metadata` | `jsonb` | NO | `'{}'::jsonb` |  |
| `source_artifact_id` | `uuid` | YES |  |  |
| `discovered_at` | `timestamp with time zone` | NO | `now()` |  |
| `updated_at` | `timestamp with time zone` | NO | `now()` |  |

Constraints:

- `resource_dataset_id_fkey` (f): `FOREIGN KEY (dataset_id) REFERENCES catalog.dataset(dataset_id)`
- `resource_source_artifact_id_fkey` (f): `FOREIGN KEY (source_artifact_id) REFERENCES ingest.artifact(artifact_id)`
- `resource_pkey` (p): `PRIMARY KEY (resource_id)`
- `resource_dataset_id_resource_key_key` (u): `UNIQUE (dataset_id, resource_key)`

Indexes:

- `resource_dataset_id_resource_key_key`: `CREATE UNIQUE INDEX resource_dataset_id_resource_key_key ON catalog.resource USING btree (dataset_id, resource_key)`
- `resource_fts_idx`: `CREATE INDEX resource_fts_idx ON catalog.resource USING gin (to_tsvector('english'::regconfig, ((((((((((COALESCE(resource_key, ''::text) || ' '::text) || COALESCE(title, ''::text)) || ' '::text) || COALESCE(summary, ''::text)) || ' '::text) || COALESCE(universe, ''::text)) || ' '::text) || COALESCE(resource_type, ''::text)) || ' '::text) || COALESCE((metadata)::text, ''::text))))`
- `resource_pkey`: `CREATE UNIQUE INDEX resource_pkey ON catalog.resource USING btree (resource_id)`
- `resource_search_idx`: `CREATE INDEX resource_search_idx ON catalog.resource USING btree (dataset_id, release_year, resource_type)`
- `resource_title_trgm_idx`: `CREATE INDEX resource_title_trgm_idx ON catalog.resource USING gin (title gin_trgm_ops)`

#### `catalog.resource_field`

- Kind: table
- Estimated rows: -1
- Total size: 16 kB

| Column | Type | Null | Default | Comment |
|---|---|---|---|---|
| `resource_id` | `uuid` | NO |  |  |
| `field_key` | `text` | NO |  |  |
| `label` | `text` | YES |  |  |
| `description` | `text` | YES |  |  |
| `data_type` | `text` | YES |  |  |
| `metadata` | `jsonb` | NO | `'{}'::jsonb` |  |
| `discovered_at` | `timestamp with time zone` | NO | `now()` |  |

Constraints:

- `resource_field_resource_id_fkey` (f): `FOREIGN KEY (resource_id) REFERENCES catalog.resource(resource_id) ON DELETE CASCADE`
- `resource_field_pkey` (p): `PRIMARY KEY (resource_id, field_key)`

Indexes:

- `resource_field_pkey`: `CREATE UNIQUE INDEX resource_field_pkey ON catalog.resource_field USING btree (resource_id, field_key)`

#### `catalog.snapshot`

- Kind: table
- Estimated rows: -1
- Total size: 48 kB

| Column | Type | Null | Default | Comment |
|---|---|---|---|---|
| `snapshot_id` | `uuid` | NO | `gen_random_uuid()` |  |
| `dataset_id` | `text` | NO |  |  |
| `source_url` | `text` | NO |  |  |
| `checksum_sha256` | `text` | NO |  |  |
| `artifact_id` | `uuid` | YES |  |  |
| `captured_at` | `timestamp with time zone` | NO | `now()` |  |
| `metadata` | `jsonb` | NO | `'{}'::jsonb` |  |

Constraints:

- `snapshot_artifact_id_fkey` (f): `FOREIGN KEY (artifact_id) REFERENCES ingest.artifact(artifact_id)`
- `snapshot_dataset_id_fkey` (f): `FOREIGN KEY (dataset_id) REFERENCES catalog.dataset(dataset_id)`
- `snapshot_pkey` (p): `PRIMARY KEY (snapshot_id)`
- `snapshot_dataset_id_checksum_sha256_key` (u): `UNIQUE (dataset_id, checksum_sha256)`

Indexes:

- `snapshot_dataset_id_checksum_sha256_key`: `CREATE UNIQUE INDEX snapshot_dataset_id_checksum_sha256_key ON catalog.snapshot USING btree (dataset_id, checksum_sha256)`
- `snapshot_pkey`: `CREATE UNIQUE INDEX snapshot_pkey ON catalog.snapshot USING btree (snapshot_id)`

#### `catalog.snapshot_resource`

- Kind: table
- Estimated rows: 12020
- Total size: 1544 kB

| Column | Type | Null | Default | Comment |
|---|---|---|---|---|
| `snapshot_id` | `uuid` | NO |  |  |
| `resource_id` | `uuid` | NO |  |  |

Constraints:

- `snapshot_resource_resource_id_fkey` (f): `FOREIGN KEY (resource_id) REFERENCES catalog.resource(resource_id) ON DELETE RESTRICT`
- `snapshot_resource_snapshot_id_fkey` (f): `FOREIGN KEY (snapshot_id) REFERENCES catalog.snapshot(snapshot_id) ON DELETE CASCADE`
- `snapshot_resource_pkey` (p): `PRIMARY KEY (snapshot_id, resource_id)`

Indexes:

- `snapshot_resource_pkey`: `CREATE UNIQUE INDEX snapshot_resource_pkey ON catalog.snapshot_resource USING btree (snapshot_id, resource_id)`

### Schema `core`

#### `core.bill`

- Kind: table
- Estimated rows: 36540
- Total size: 13 MB

| Column | Type | Null | Default | Comment |
|---|---|---|---|---|
| `bill_id` | `uuid` | NO | `gen_random_uuid()` |  |
| `jurisdiction` | `text` | NO |  |  |
| `legislative_session` | `text` | NO |  |  |
| `bill_type` | `text` | NO |  |  |
| `bill_number` | `text` | NO |  |  |
| `title` | `text` | YES |  |  |
| `introduced_date` | `date` | YES |  |  |
| `latest_action_date` | `date` | YES |  |  |
| `latest_action` | `text` | YES |  |  |
| `metadata` | `jsonb` | NO | `'{}'::jsonb` |  |
| `legislative_session_id` | `uuid` | YES |  |  |
| `ocd_id` | `text` | YES |  |  |

Constraints:

- `bill_legislative_session_id_fkey` (f): `FOREIGN KEY (legislative_session_id) REFERENCES core.legislative_session(legislative_session_id)`
- `bill_pkey` (p): `PRIMARY KEY (bill_id)`
- `bill_jurisdiction_legislative_session_bill_type_bill_number_key` (u): `UNIQUE (jurisdiction, legislative_session, bill_type, bill_number)`

Indexes:

- `bill_jurisdiction_legislative_session_bill_type_bill_number_key`: `CREATE UNIQUE INDEX bill_jurisdiction_legislative_session_bill_type_bill_number_key ON core.bill USING btree (jurisdiction, legislative_session, bill_type, bill_number)`
- `bill_ocd_id_idx`: `CREATE UNIQUE INDEX bill_ocd_id_idx ON core.bill USING btree (ocd_id) WHERE (ocd_id IS NOT NULL)`
- `bill_pkey`: `CREATE UNIQUE INDEX bill_pkey ON core.bill USING btree (bill_id)`

#### `core.bill_action`

- Kind: table
- Estimated rows: 157971
- Total size: 70 MB

| Column | Type | Null | Default | Comment |
|---|---|---|---|---|
| `bill_action_id` | `uuid` | NO | `gen_random_uuid()` |  |
| `bill_id` | `uuid` | NO |  |  |
| `action_date` | `timestamp with time zone` | YES |  |  |
| `description` | `text` | NO |  |  |
| `classification` | `text[]` | YES |  |  |
| `source_payload_id` | `uuid` | YES |  |  |
| `source_artifact_id` | `uuid` | YES |  |  |
| `source_member` | `text` | YES |  |  |
| `source_ordinal` | `integer` | YES |  |  |
| `metadata` | `jsonb` | NO | `'{}'::jsonb` |  |

Constraints:

- `bill_action_source_evidence` (c): `CHECK (source_artifact_id IS NOT NULL OR source_payload_id IS NOT NULL)`
- `bill_action_bill_id_fkey` (f): `FOREIGN KEY (bill_id) REFERENCES core.bill(bill_id)`
- `bill_action_source_artifact_id_fkey` (f): `FOREIGN KEY (source_artifact_id) REFERENCES ingest.artifact(artifact_id)`
- `bill_action_source_payload_id_fkey` (f): `FOREIGN KEY (source_payload_id) REFERENCES ingest.raw_payload(payload_id)`
- `bill_action_pkey` (p): `PRIMARY KEY (bill_action_id)`

Indexes:

- `bill_action_pkey`: `CREATE UNIQUE INDEX bill_action_pkey ON core.bill_action USING btree (bill_action_id)`
- `bill_action_source_member_idx`: `CREATE UNIQUE INDEX bill_action_source_member_idx ON core.bill_action USING btree (bill_id, source_artifact_id, source_member, source_ordinal) WHERE (source_artifact_id IS NOT NULL)`

#### `core.bill_committee`

- Kind: table
- Estimated rows: 45458
- Total size: 18 MB

| Column | Type | Null | Default | Comment |
|---|---|---|---|---|
| `bill_committee_id` | `uuid` | NO | `gen_random_uuid()` |  |
| `bill_id` | `uuid` | NO |  |  |
| `namespace` | `text` | NO | `'congress.gov.committee'::text` |  |
| `external_id` | `text` | NO |  |  |
| `name` | `text` | YES |  |  |
| `chamber` | `text` | YES |  |  |
| `source_artifact_id` | `uuid` | YES |  |  |
| `source_payload_id` | `uuid` | YES |  |  |
| `source_member` | `text` | YES |  |  |
| `metadata` | `jsonb` | NO | `'{}'::jsonb` |  |

Constraints:

- `bill_committee_check` (c): `CHECK (source_artifact_id IS NOT NULL OR source_payload_id IS NOT NULL)`
- `bill_committee_bill_id_fkey` (f): `FOREIGN KEY (bill_id) REFERENCES core.bill(bill_id)`
- `bill_committee_source_artifact_id_fkey` (f): `FOREIGN KEY (source_artifact_id) REFERENCES ingest.artifact(artifact_id)`
- `bill_committee_source_payload_id_fkey` (f): `FOREIGN KEY (source_payload_id) REFERENCES ingest.raw_payload(payload_id)`
- `bill_committee_pkey` (p): `PRIMARY KEY (bill_committee_id)`
- `bill_committee_bill_id_namespace_external_id_source_artifac_key` (u): `UNIQUE NULLS NOT DISTINCT (bill_id, namespace, external_id, source_artifact_id, source_member)`

Indexes:

- `bill_committee_bill_id_namespace_external_id_source_artifac_key`: `CREATE UNIQUE INDEX bill_committee_bill_id_namespace_external_id_source_artifac_key ON core.bill_committee USING btree (bill_id, namespace, external_id, source_artifact_id, source_member) NULLS NOT DISTINCT`
- `bill_committee_pkey`: `CREATE UNIQUE INDEX bill_committee_pkey ON core.bill_committee USING btree (bill_committee_id)`

#### `core.bill_document`

- Kind: table
- Estimated rows: 42781
- Total size: 7112 kB

| Column | Type | Null | Default | Comment |
|---|---|---|---|---|
| `bill_id` | `uuid` | NO |  |  |
| `document_id` | `uuid` | NO |  |  |
| `relation` | `text` | NO | `'text'::text` |  |

Constraints:

- `bill_document_bill_id_fkey` (f): `FOREIGN KEY (bill_id) REFERENCES core.bill(bill_id)`
- `bill_document_document_id_fkey` (f): `FOREIGN KEY (document_id) REFERENCES core.document(document_id)`
- `bill_document_pkey` (p): `PRIMARY KEY (bill_id, document_id, relation)`

Indexes:

- `bill_document_pkey`: `CREATE UNIQUE INDEX bill_document_pkey ON core.bill_document USING btree (bill_id, document_id, relation)`

#### `core.bill_identifier`

- Kind: table
- Estimated rows: 73632
- Total size: 21 MB

| Column | Type | Null | Default | Comment |
|---|---|---|---|---|
| `bill_id` | `uuid` | NO |  |  |
| `namespace` | `text` | NO |  |  |
| `external_id` | `text` | NO |  |  |
| `source_artifact_id` | `uuid` | YES |  |  |
| `source_payload_id` | `uuid` | YES |  |  |
| `source_url` | `text` | YES |  |  |
| `metadata` | `jsonb` | NO | `'{}'::jsonb` |  |

Constraints:

- `bill_identifier_check` (c): `CHECK (source_artifact_id IS NOT NULL OR source_payload_id IS NOT NULL)`
- `bill_identifier_bill_id_fkey` (f): `FOREIGN KEY (bill_id) REFERENCES core.bill(bill_id)`
- `bill_identifier_source_artifact_id_fkey` (f): `FOREIGN KEY (source_artifact_id) REFERENCES ingest.artifact(artifact_id)`
- `bill_identifier_source_payload_id_fkey` (f): `FOREIGN KEY (source_payload_id) REFERENCES ingest.raw_payload(payload_id)`
- `bill_identifier_pkey` (p): `PRIMARY KEY (namespace, external_id)`

Indexes:

- `bill_identifier_bill_idx`: `CREATE INDEX bill_identifier_bill_idx ON core.bill_identifier USING btree (bill_id)`
- `bill_identifier_pkey`: `CREATE UNIQUE INDEX bill_identifier_pkey ON core.bill_identifier USING btree (namespace, external_id)`

#### `core.bill_sponsorship`

- Kind: table
- Estimated rows: 402817
- Total size: 194 MB

| Column | Type | Null | Default | Comment |
|---|---|---|---|---|
| `bill_sponsorship_id` | `uuid` | NO | `gen_random_uuid()` |  |
| `bill_id` | `uuid` | NO |  |  |
| `person_id` | `uuid` | YES |  |  |
| `member_namespace` | `text` | NO | `'bioguide'::text` |  |
| `member_external_id` | `text` | NO |  |  |
| `role` | `text` | NO |  |  |
| `source_artifact_id` | `uuid` | YES |  |  |
| `source_payload_id` | `uuid` | YES |  |  |
| `source_member` | `text` | YES |  |  |
| `metadata` | `jsonb` | NO | `'{}'::jsonb` |  |

Constraints:

- `bill_sponsorship_check` (c): `CHECK (source_artifact_id IS NOT NULL OR source_payload_id IS NOT NULL)`
- `bill_sponsorship_role_check` (c): `CHECK (role = ANY (ARRAY['sponsor'::text, 'cosponsor'::text]))`
- `bill_sponsorship_bill_id_fkey` (f): `FOREIGN KEY (bill_id) REFERENCES core.bill(bill_id)`
- `bill_sponsorship_person_id_fkey` (f): `FOREIGN KEY (person_id) REFERENCES core.person(person_id)`
- `bill_sponsorship_source_artifact_id_fkey` (f): `FOREIGN KEY (source_artifact_id) REFERENCES ingest.artifact(artifact_id)`
- `bill_sponsorship_source_payload_id_fkey` (f): `FOREIGN KEY (source_payload_id) REFERENCES ingest.raw_payload(payload_id)`
- `bill_sponsorship_pkey` (p): `PRIMARY KEY (bill_sponsorship_id)`
- `bill_sponsorship_bill_id_member_namespace_member_external_i_key` (u): `UNIQUE NULLS NOT DISTINCT (bill_id, member_namespace, member_external_id, role, source_artifact_id, source_member)`

Indexes:

- `bill_sponsorship_bill_id_member_namespace_member_external_i_key`: `CREATE UNIQUE INDEX bill_sponsorship_bill_id_member_namespace_member_external_i_key ON core.bill_sponsorship USING btree (bill_id, member_namespace, member_external_id, role, source_artifact_id, source_member) NULLS NOT DISTINCT`
- `bill_sponsorship_person_idx`: `CREATE INDEX bill_sponsorship_person_idx ON core.bill_sponsorship USING btree (person_id)`
- `bill_sponsorship_pkey`: `CREATE UNIQUE INDEX bill_sponsorship_pkey ON core.bill_sponsorship USING btree (bill_sponsorship_id)`

#### `core.bill_subject`

- Kind: table
- Estimated rows: 125912
- Total size: 54 MB

| Column | Type | Null | Default | Comment |
|---|---|---|---|---|
| `bill_subject_id` | `uuid` | NO | `gen_random_uuid()` |  |
| `bill_id` | `uuid` | NO |  |  |
| `namespace` | `text` | NO | `'congress.gov.subject'::text` |  |
| `external_id` | `text` | NO |  |  |
| `label` | `text` | NO |  |  |
| `source_artifact_id` | `uuid` | YES |  |  |
| `source_payload_id` | `uuid` | YES |  |  |
| `source_member` | `text` | YES |  |  |
| `metadata` | `jsonb` | NO | `'{}'::jsonb` |  |

Constraints:

- `bill_subject_check` (c): `CHECK (source_artifact_id IS NOT NULL OR source_payload_id IS NOT NULL)`
- `bill_subject_bill_id_fkey` (f): `FOREIGN KEY (bill_id) REFERENCES core.bill(bill_id)`
- `bill_subject_source_artifact_id_fkey` (f): `FOREIGN KEY (source_artifact_id) REFERENCES ingest.artifact(artifact_id)`
- `bill_subject_source_payload_id_fkey` (f): `FOREIGN KEY (source_payload_id) REFERENCES ingest.raw_payload(payload_id)`
- `bill_subject_pkey` (p): `PRIMARY KEY (bill_subject_id)`
- `bill_subject_bill_id_namespace_external_id_source_artifact__key` (u): `UNIQUE NULLS NOT DISTINCT (bill_id, namespace, external_id, source_artifact_id, source_member)`

Indexes:

- `bill_subject_bill_id_namespace_external_id_source_artifact__key`: `CREATE UNIQUE INDEX bill_subject_bill_id_namespace_external_id_source_artifact__key ON core.bill_subject USING btree (bill_id, namespace, external_id, source_artifact_id, source_member) NULLS NOT DISTINCT`
- `bill_subject_pkey`: `CREATE UNIQUE INDEX bill_subject_pkey ON core.bill_subject USING btree (bill_subject_id)`

#### `core.document`

- Kind: table
- Estimated rows: 42488
- Total size: 25 MB

| Column | Type | Null | Default | Comment |
|---|---|---|---|---|
| `document_id` | `uuid` | NO | `gen_random_uuid()` |  |
| `document_type` | `text` | NO |  |  |
| `source_key` | `text` | NO |  |  |
| `title` | `text` | YES |  |  |
| `published_at` | `timestamp with time zone` | YES |  |  |
| `language` | `text` | NO | `'en'::text` |  |
| `canonical_url` | `text` | YES |  |  |
| `checksum_sha256` | `text` | YES |  |  |
| `metadata` | `jsonb` | NO | `'{}'::jsonb` |  |
| `source_payload_id` | `uuid` | YES |  |  |
| `artifact_id` | `uuid` | YES |  |  |
| `created_at` | `timestamp with time zone` | NO | `now()` |  |

Constraints:

- `document_artifact_id_fkey` (f): `FOREIGN KEY (artifact_id) REFERENCES ingest.artifact(artifact_id)`
- `document_source_payload_id_fkey` (f): `FOREIGN KEY (source_payload_id) REFERENCES ingest.raw_payload(payload_id)`
- `document_pkey` (p): `PRIMARY KEY (document_id)`
- `document_document_type_source_key_key` (u): `UNIQUE (document_type, source_key)`

Indexes:

- `document_document_type_source_key_key`: `CREATE UNIQUE INDEX document_document_type_source_key_key ON core.document USING btree (document_type, source_key)`
- `document_pkey`: `CREATE UNIQUE INDEX document_pkey ON core.document USING btree (document_id)`

#### `core.document_chunk`

- Kind: table
- Estimated rows: -1
- Total size: 32 kB

| Column | Type | Null | Default | Comment |
|---|---|---|---|---|
| `chunk_id` | `uuid` | NO | `gen_random_uuid()` |  |
| `document_id` | `uuid` | NO |  |  |
| `ordinal` | `integer` | NO |  |  |
| `text` | `text` | NO |  |  |
| `token_count` | `integer` | YES |  |  |
| `checksum_sha256` | `text` | NO |  |  |
| `metadata` | `jsonb` | NO | `'{}'::jsonb` |  |

Constraints:

- `document_chunk_ordinal_check` (c): `CHECK (ordinal >= 0)`
- `document_chunk_document_id_fkey` (f): `FOREIGN KEY (document_id) REFERENCES core.document(document_id)`
- `document_chunk_pkey` (p): `PRIMARY KEY (chunk_id)`
- `document_chunk_document_id_checksum_sha256_key` (u): `UNIQUE (document_id, checksum_sha256)`
- `document_chunk_document_id_ordinal_key` (u): `UNIQUE (document_id, ordinal)`

Indexes:

- `document_chunk_document_id_checksum_sha256_key`: `CREATE UNIQUE INDEX document_chunk_document_id_checksum_sha256_key ON core.document_chunk USING btree (document_id, checksum_sha256)`
- `document_chunk_document_id_ordinal_key`: `CREATE UNIQUE INDEX document_chunk_document_id_ordinal_key ON core.document_chunk USING btree (document_id, ordinal)`
- `document_chunk_pkey`: `CREATE UNIQUE INDEX document_chunk_pkey ON core.document_chunk USING btree (chunk_id)`

#### `core.embedding`

- Kind: table
- Estimated rows: -1
- Total size: 24 kB

| Column | Type | Null | Default | Comment |
|---|---|---|---|---|
| `embedding_id` | `uuid` | NO | `gen_random_uuid()` |  |
| `chunk_id` | `uuid` | NO |  |  |
| `model` | `text` | NO |  |  |
| `dimensions` | `integer` | NO |  |  |
| `vector_values` | `real[]` | NO |  |  |
| `created_at` | `timestamp with time zone` | NO | `now()` |  |

Constraints:

- `embedding_check` (c): `CHECK (cardinality(vector_values) = dimensions)`
- `embedding_dimensions_check` (c): `CHECK (dimensions > 0)`
- `embedding_chunk_id_fkey` (f): `FOREIGN KEY (chunk_id) REFERENCES core.document_chunk(chunk_id)`
- `embedding_pkey` (p): `PRIMARY KEY (embedding_id)`
- `embedding_chunk_id_model_key` (u): `UNIQUE (chunk_id, model)`

Indexes:

- `embedding_chunk_id_model_key`: `CREATE UNIQUE INDEX embedding_chunk_id_model_key ON core.embedding USING btree (chunk_id, model)`
- `embedding_pkey`: `CREATE UNIQUE INDEX embedding_pkey ON core.embedding USING btree (embedding_id)`

#### `core.geography`

- Kind: table
- Estimated rows: 49742
- Total size: 16 MB

| Column | Type | Null | Default | Comment |
|---|---|---|---|---|
| `geography_id` | `uuid` | NO | `gen_random_uuid()` |  |
| `geography_type` | `text` | NO |  |  |
| `geoid` | `text` | NO |  |  |
| `name` | `text` | YES |  |  |
| `parent_geoid` | `text` | YES |  |  |
| `state_fips` | `text` | YES |  |  |
| `county_fips` | `text` | YES |  |  |
| `metadata` | `jsonb` | NO | `'{}'::jsonb` |  |

Constraints:

- `geography_pkey` (p): `PRIMARY KEY (geography_id)`
- `geography_geography_type_geoid_key` (u): `UNIQUE (geography_type, geoid)`

Indexes:

- `geography_geography_type_geoid_key`: `CREATE UNIQUE INDEX geography_geography_type_geoid_key ON core.geography USING btree (geography_type, geoid)`
- `geography_pkey`: `CREATE UNIQUE INDEX geography_pkey ON core.geography USING btree (geography_id)`

#### `core.geography_boundary`

- Kind: table
- Estimated rows: 377428
- Total size: 10 GB

| Column | Type | Null | Default | Comment |
|---|---|---|---|---|
| `boundary_id` | `uuid` | NO | `gen_random_uuid()` |  |
| `geography_id` | `uuid` | NO |  |  |
| `boundary_vintage` | `integer` | NO |  |  |
| `valid_from` | `date` | YES |  |  |
| `valid_to` | `date` | YES |  |  |
| `geom` | `geometry(Geometry,4326)` | NO |  |  |
| `source_payload_id` | `uuid` | YES |  |  |
| `source_artifact_id` | `uuid` | YES |  |  |

Constraints:

- `geography_boundary_geography_id_fkey` (f): `FOREIGN KEY (geography_id) REFERENCES core.geography(geography_id)`
- `geography_boundary_source_artifact_id_fkey` (f): `FOREIGN KEY (source_artifact_id) REFERENCES ingest.artifact(artifact_id)`
- `geography_boundary_source_payload_id_fkey` (f): `FOREIGN KEY (source_payload_id) REFERENCES ingest.raw_payload(payload_id)`
- `geography_boundary_pkey` (p): `PRIMARY KEY (boundary_id)`
- `geography_boundary_geography_id_boundary_vintage_key` (u): `UNIQUE (geography_id, boundary_vintage)`

Indexes:

- `geography_boundary_geography_id_boundary_vintage_key`: `CREATE UNIQUE INDEX geography_boundary_geography_id_boundary_vintage_key ON core.geography_boundary USING btree (geography_id, boundary_vintage)`
- `geography_boundary_geom_idx`: `CREATE INDEX geography_boundary_geom_idx ON core.geography_boundary USING gist (geom)`
- `geography_boundary_pkey`: `CREATE UNIQUE INDEX geography_boundary_pkey ON core.geography_boundary USING btree (boundary_id)`

#### `core.instrument`

- Kind: table
- Estimated rows: -1
- Total size: 16 kB

| Column | Type | Null | Default | Comment |
|---|---|---|---|---|
| `instrument_id` | `uuid` | NO | `gen_random_uuid()` |  |
| `instrument_type` | `text` | NO |  |  |
| `name` | `text` | YES |  |  |
| `currency` | `text` | YES |  |  |
| `metadata` | `jsonb` | NO | `'{}'::jsonb` |  |

Constraints:

- `instrument_pkey` (p): `PRIMARY KEY (instrument_id)`

Indexes:

- `instrument_pkey`: `CREATE UNIQUE INDEX instrument_pkey ON core.instrument USING btree (instrument_id)`

#### `core.instrument_symbol`

- Kind: table
- Estimated rows: -1
- Total size: 16 kB

| Column | Type | Null | Default | Comment |
|---|---|---|---|---|
| `instrument_id` | `uuid` | NO |  |  |
| `symbol` | `text` | NO |  |  |
| `exchange` | `text` | NO | `''::text` |  |
| `valid_from` | `date` | NO |  |  |
| `valid_to` | `date` | YES |  |  |

Constraints:

- `instrument_symbol_instrument_id_fkey` (f): `FOREIGN KEY (instrument_id) REFERENCES core.instrument(instrument_id)`
- `instrument_symbol_pkey` (p): `PRIMARY KEY (symbol, exchange, valid_from)`

Indexes:

- `instrument_symbol_pkey`: `CREATE UNIQUE INDEX instrument_symbol_pkey ON core.instrument_symbol USING btree (symbol, exchange, valid_from)`

#### `core.jurisdiction`

- Kind: table
- Estimated rows: -1
- Total size: 32 kB

| Column | Type | Null | Default | Comment |
|---|---|---|---|---|
| `jurisdiction_id` | `text` | NO |  |  |
| `name` | `text` | NO |  |  |
| `classification` | `text` | NO |  |  |
| `metadata` | `jsonb` | NO | `'{}'::jsonb` |  |

Constraints:

- `jurisdiction_pkey` (p): `PRIMARY KEY (jurisdiction_id)`

Indexes:

- `jurisdiction_pkey`: `CREATE UNIQUE INDEX jurisdiction_pkey ON core.jurisdiction USING btree (jurisdiction_id)`

#### `core.legislative_session`

- Kind: table
- Estimated rows: -1
- Total size: 48 kB

| Column | Type | Null | Default | Comment |
|---|---|---|---|---|
| `legislative_session_id` | `uuid` | NO | `gen_random_uuid()` |  |
| `jurisdiction_id` | `text` | NO |  |  |
| `identifier` | `text` | NO |  |  |
| `name` | `text` | YES |  |  |
| `classification` | `text` | YES |  |  |
| `starts_on` | `date` | YES |  |  |
| `ends_on` | `date` | YES |  |  |
| `active` | `boolean` | YES |  |  |
| `source_artifact_id` | `uuid` | YES |  |  |
| `source_payload_id` | `uuid` | YES |  |  |
| `metadata` | `jsonb` | NO | `'{}'::jsonb` |  |

Constraints:

- `legislative_session_check` (c): `CHECK (source_artifact_id IS NOT NULL OR source_payload_id IS NOT NULL)`
- `legislative_session_jurisdiction_id_fkey` (f): `FOREIGN KEY (jurisdiction_id) REFERENCES core.jurisdiction(jurisdiction_id)`
- `legislative_session_source_artifact_id_fkey` (f): `FOREIGN KEY (source_artifact_id) REFERENCES ingest.artifact(artifact_id)`
- `legislative_session_source_payload_id_fkey` (f): `FOREIGN KEY (source_payload_id) REFERENCES ingest.raw_payload(payload_id)`
- `legislative_session_pkey` (p): `PRIMARY KEY (legislative_session_id)`
- `legislative_session_jurisdiction_id_identifier_key` (u): `UNIQUE (jurisdiction_id, identifier)`

Indexes:

- `legislative_session_jurisdiction_id_identifier_key`: `CREATE UNIQUE INDEX legislative_session_jurisdiction_id_identifier_key ON core.legislative_session USING btree (jurisdiction_id, identifier)`
- `legislative_session_pkey`: `CREATE UNIQUE INDEX legislative_session_pkey ON core.legislative_session USING btree (legislative_session_id)`

#### `core.membership`

- Kind: table
- Estimated rows: -1
- Total size: 32 kB

| Column | Type | Null | Default | Comment |
|---|---|---|---|---|
| `membership_id` | `uuid` | NO | `gen_random_uuid()` |  |
| `person_id` | `uuid` | NO |  |  |
| `organization_id` | `uuid` | NO |  |  |
| `legislative_session_id` | `uuid` | YES |  |  |
| `role` | `text` | NO |  |  |
| `start_date` | `date` | YES |  |  |
| `end_date` | `date` | YES |  |  |
| `source_artifact_id` | `uuid` | YES |  |  |
| `source_payload_id` | `uuid` | YES |  |  |
| `metadata` | `jsonb` | NO | `'{}'::jsonb` |  |

Constraints:

- `membership_check` (c): `CHECK (source_artifact_id IS NOT NULL OR source_payload_id IS NOT NULL)`
- `membership_legislative_session_id_fkey` (f): `FOREIGN KEY (legislative_session_id) REFERENCES core.legislative_session(legislative_session_id)`
- `membership_organization_id_fkey` (f): `FOREIGN KEY (organization_id) REFERENCES core.organization(organization_id)`
- `membership_person_id_fkey` (f): `FOREIGN KEY (person_id) REFERENCES core.person(person_id)`
- `membership_source_artifact_id_fkey` (f): `FOREIGN KEY (source_artifact_id) REFERENCES ingest.artifact(artifact_id)`
- `membership_source_payload_id_fkey` (f): `FOREIGN KEY (source_payload_id) REFERENCES ingest.raw_payload(payload_id)`
- `membership_pkey` (p): `PRIMARY KEY (membership_id)`

Indexes:

- `membership_organization_idx`: `CREATE INDEX membership_organization_idx ON core.membership USING btree (organization_id)`
- `membership_person_idx`: `CREATE INDEX membership_person_idx ON core.membership USING btree (person_id)`
- `membership_pkey`: `CREATE UNIQUE INDEX membership_pkey ON core.membership USING btree (membership_id)`

#### `core.organization`

- Kind: table
- Estimated rows: 242
- Total size: 136 kB

| Column | Type | Null | Default | Comment |
|---|---|---|---|---|
| `organization_id` | `uuid` | NO | `gen_random_uuid()` |  |
| `organization_type` | `text` | NO |  |  |
| `name` | `text` | NO |  |  |
| `jurisdiction_geoid` | `text` | YES |  |  |
| `metadata` | `jsonb` | NO | `'{}'::jsonb` |  |

Constraints:

- `organization_pkey` (p): `PRIMARY KEY (organization_id)`

Indexes:

- `organization_pkey`: `CREATE UNIQUE INDEX organization_pkey ON core.organization USING btree (organization_id)`

#### `core.organization_identifier`

- Kind: table
- Estimated rows: 242
- Total size: 104 kB

| Column | Type | Null | Default | Comment |
|---|---|---|---|---|
| `organization_id` | `uuid` | NO |  |  |
| `namespace` | `text` | NO |  |  |
| `external_id` | `text` | NO |  |  |
| `metadata` | `jsonb` | NO | `'{}'::jsonb` |  |

Constraints:

- `organization_identifier_organization_id_fkey` (f): `FOREIGN KEY (organization_id) REFERENCES core.organization(organization_id)`
- `organization_identifier_pkey` (p): `PRIMARY KEY (namespace, external_id)`

Indexes:

- `organization_identifier_pkey`: `CREATE UNIQUE INDEX organization_identifier_pkey ON core.organization_identifier USING btree (namespace, external_id)`

#### `core.person`

- Kind: table
- Estimated rows: 723
- Total size: 256 kB

| Column | Type | Null | Default | Comment |
|---|---|---|---|---|
| `person_id` | `uuid` | NO | `gen_random_uuid()` |  |
| `full_name` | `text` | NO |  |  |
| `given_name` | `text` | YES |  |  |
| `family_name` | `text` | YES |  |  |
| `metadata` | `jsonb` | NO | `'{}'::jsonb` |  |

Constraints:

- `person_pkey` (p): `PRIMARY KEY (person_id)`

Indexes:

- `person_pkey`: `CREATE UNIQUE INDEX person_pkey ON core.person USING btree (person_id)`

#### `core.person_identifier`

- Kind: table
- Estimated rows: 9838
- Total size: 2040 kB

| Column | Type | Null | Default | Comment |
|---|---|---|---|---|
| `person_id` | `uuid` | NO |  |  |
| `namespace` | `text` | NO |  |  |
| `external_id` | `text` | NO |  |  |
| `valid_from` | `date` | YES |  |  |
| `valid_to` | `date` | YES |  |  |

Constraints:

- `person_identifier_person_id_fkey` (f): `FOREIGN KEY (person_id) REFERENCES core.person(person_id)`
- `person_identifier_pkey` (p): `PRIMARY KEY (namespace, external_id)`

Indexes:

- `person_identifier_pkey`: `CREATE UNIQUE INDEX person_identifier_pkey ON core.person_identifier USING btree (namespace, external_id)`

#### `core.roll_call`

- Kind: table
- Estimated rows: 1788
- Total size: 1096 kB

| Column | Type | Null | Default | Comment |
|---|---|---|---|---|
| `roll_call_id` | `uuid` | NO | `gen_random_uuid()` |  |
| `jurisdiction` | `text` | NO |  |  |
| `legislative_session` | `text` | NO |  |  |
| `chamber` | `text` | YES |  |  |
| `external_id` | `text` | NO |  |  |
| `occurred_at` | `timestamp with time zone` | YES |  |  |
| `question` | `text` | YES |  |  |
| `result` | `text` | YES |  |  |
| `metadata` | `jsonb` | NO | `'{}'::jsonb` |  |
| `bill_id` | `uuid` | YES |  |  |
| `legislative_session_id` | `uuid` | YES |  |  |
| `organization_id` | `uuid` | YES |  |  |
| `ocd_id` | `text` | YES |  |  |

Constraints:

- `roll_call_bill_id_fkey` (f): `FOREIGN KEY (bill_id) REFERENCES core.bill(bill_id)`
- `roll_call_legislative_session_id_fkey` (f): `FOREIGN KEY (legislative_session_id) REFERENCES core.legislative_session(legislative_session_id)`
- `roll_call_organization_id_fkey` (f): `FOREIGN KEY (organization_id) REFERENCES core.organization(organization_id)`
- `roll_call_pkey` (p): `PRIMARY KEY (roll_call_id)`
- `roll_call_jurisdiction_legislative_session_external_id_key` (u): `UNIQUE (jurisdiction, legislative_session, external_id)`

Indexes:

- `roll_call_jurisdiction_legislative_session_external_id_key`: `CREATE UNIQUE INDEX roll_call_jurisdiction_legislative_session_external_id_key ON core.roll_call USING btree (jurisdiction, legislative_session, external_id)`
- `roll_call_ocd_id_idx`: `CREATE UNIQUE INDEX roll_call_ocd_id_idx ON core.roll_call USING btree (ocd_id) WHERE (ocd_id IS NOT NULL)`
- `roll_call_pkey`: `CREATE UNIQUE INDEX roll_call_pkey ON core.roll_call USING btree (roll_call_id)`

### Schema `fact`

#### `fact.acs_bulk_estimate`

- Kind: table
- Estimated rows: 280819136
- Total size: 99 GB

| Column | Type | Null | Default | Comment |
|---|---|---|---|---|
| `acs_bulk_estimate_id` | `uuid` | NO | `gen_random_uuid()` |  |
| `release_year` | `integer` | NO |  |  |
| `geography_id` | `uuid` | NO |  |  |
| `table_id` | `text` | NO |  |  |
| `field_id` | `text` | NO |  |  |
| `measure` | `text` | NO |  |  |
| `value` | `numeric` | YES |  |  |
| `source_artifact_id` | `uuid` | NO |  |  |
| `source_ordinal` | `bigint` | NO |  |  |

Constraints:

- `acs_bulk_estimate_measure_check` (c): `CHECK (measure = ANY (ARRAY['estimate'::text, 'margin_of_error'::text]))`
- `acs_bulk_estimate_geography_id_fkey` (f): `FOREIGN KEY (geography_id) REFERENCES core.geography(geography_id)`
- `acs_bulk_estimate_source_artifact_id_fkey` (f): `FOREIGN KEY (source_artifact_id) REFERENCES ingest.artifact(artifact_id)`
- `acs_bulk_estimate_pkey` (p): `PRIMARY KEY (acs_bulk_estimate_id)`
- `acs_bulk_estimate_source_artifact_id_source_ordinal_field_i_key` (u): `UNIQUE (source_artifact_id, source_ordinal, field_id)`

Indexes:

- `acs_bulk_estimate_lookup_idx`: `CREATE INDEX acs_bulk_estimate_lookup_idx ON fact.acs_bulk_estimate USING btree (release_year, geography_id, table_id, field_id)`
- `acs_bulk_estimate_pkey`: `CREATE UNIQUE INDEX acs_bulk_estimate_pkey ON fact.acs_bulk_estimate USING btree (acs_bulk_estimate_id)`
- `acs_bulk_estimate_source_artifact_id_source_ordinal_field_i_key`: `CREATE UNIQUE INDEX acs_bulk_estimate_source_artifact_id_source_ordinal_field_i_key ON fact.acs_bulk_estimate USING btree (source_artifact_id, source_ordinal, field_id)`

#### `fact.business_pattern`

- Kind: table
- Estimated rows: 30618374
- Total size: 12 GB

| Column | Type | Null | Default | Comment |
|---|---|---|---|---|
| `business_pattern_id` | `uuid` | NO | `gen_random_uuid()` |  |
| `release_year` | `integer` | NO |  |  |
| `geography_id` | `uuid` | NO |  |  |
| `naics` | `text` | NO |  |  |
| `legal_form` | `text` | NO | `''::text` |  |
| `establishments` | `bigint` | YES |  |  |
| `employment` | `bigint` | YES |  |  |
| `first_quarter_payroll` | `numeric` | YES |  |  |
| `annual_payroll` | `numeric` | YES |  |  |
| `flags` | `jsonb` | NO | `'{}'::jsonb` |  |
| `source_artifact_id` | `uuid` | NO |  |  |
| `source_member` | `text` | NO |  |  |
| `source_ordinal` | `bigint` | NO |  |  |
| `loaded_at` | `timestamp with time zone` | NO | `now()` |  |

Constraints:

- `business_pattern_geography_id_fkey` (f): `FOREIGN KEY (geography_id) REFERENCES core.geography(geography_id)`
- `business_pattern_source_artifact_id_fkey` (f): `FOREIGN KEY (source_artifact_id) REFERENCES ingest.artifact(artifact_id)`
- `business_pattern_pkey` (p): `PRIMARY KEY (business_pattern_id)`
- `business_pattern_source_artifact_id_source_member_source_or_key` (u): `UNIQUE (source_artifact_id, source_member, source_ordinal)`

Indexes:

- `business_pattern_lookup_idx`: `CREATE INDEX business_pattern_lookup_idx ON fact.business_pattern USING btree (release_year, geography_id, naics)`
- `business_pattern_pkey`: `CREATE UNIQUE INDEX business_pattern_pkey ON fact.business_pattern USING btree (business_pattern_id)`
- `business_pattern_source_artifact_id_source_member_source_or_key`: `CREATE UNIQUE INDEX business_pattern_source_artifact_id_source_member_source_or_key ON fact.business_pattern USING btree (source_artifact_id, source_member, source_ordinal)`

#### `fact.decennial_dhc_value`

- Kind: table
- Estimated rows: 22758
- Total size: 7696 kB

| Column | Type | Null | Default | Comment |
|---|---|---|---|---|
| `dhc_value_id` | `uuid` | NO | `gen_random_uuid()` |  |
| `release_year` | `integer` | NO |  |  |
| `geography_id` | `uuid` | NO |  |  |
| `table_id` | `text` | NO |  |  |
| `variable_id` | `text` | NO |  |  |
| `value` | `bigint` | YES |  |  |
| `source_artifact_id` | `uuid` | NO |  |  |
| `source_member` | `text` | NO |  |  |
| `source_ordinal` | `bigint` | NO |  |  |

Constraints:

- `decennial_dhc_value_geography_id_fkey` (f): `FOREIGN KEY (geography_id) REFERENCES core.geography(geography_id)`
- `decennial_dhc_value_source_artifact_id_fkey` (f): `FOREIGN KEY (source_artifact_id) REFERENCES ingest.artifact(artifact_id)`
- `decennial_dhc_value_pkey` (p): `PRIMARY KEY (dhc_value_id)`
- `decennial_dhc_value_source_artifact_id_source_member_source_key` (u): `UNIQUE (source_artifact_id, source_member, source_ordinal, variable_id)`

Indexes:

- `decennial_dhc_value_pkey`: `CREATE UNIQUE INDEX decennial_dhc_value_pkey ON fact.decennial_dhc_value USING btree (dhc_value_id)`
- `decennial_dhc_value_source_artifact_id_source_member_source_key`: `CREATE UNIQUE INDEX decennial_dhc_value_source_artifact_id_source_member_source_key ON fact.decennial_dhc_value USING btree (source_artifact_id, source_member, source_ordinal, variable_id)`
- `dhc_value_lookup_idx`: `CREATE INDEX dhc_value_lookup_idx ON fact.decennial_dhc_value USING btree (release_year, geography_id, table_id, variable_id)`

#### `fact.market_bar`

- Kind: table
- Estimated rows: -1
- Total size: 16 kB

| Column | Type | Null | Default | Comment |
|---|---|---|---|---|
| `instrument_id` | `uuid` | NO |  |  |
| `trade_date` | `date` | NO |  |  |
| `interval` | `text` | NO | `'1d'::text` |  |
| `open` | `numeric` | YES |  |  |
| `high` | `numeric` | YES |  |  |
| `low` | `numeric` | YES |  |  |
| `close` | `numeric` | YES |  |  |
| `adjusted_close` | `numeric` | YES |  |  |
| `volume` | `numeric` | YES |  |  |
| `source_payload_id` | `uuid` | NO |  |  |

Constraints:

- `market_bar_instrument_id_fkey` (f): `FOREIGN KEY (instrument_id) REFERENCES core.instrument(instrument_id)`
- `market_bar_source_payload_id_fkey` (f): `FOREIGN KEY (source_payload_id) REFERENCES ingest.raw_payload(payload_id)`
- `market_bar_pkey` (p): `PRIMARY KEY (instrument_id, trade_date, "interval")`

Indexes:

- `market_bar_pkey`: `CREATE UNIQUE INDEX market_bar_pkey ON fact.market_bar USING btree (instrument_id, trade_date, "interval")`

#### `fact.measurement`

- Kind: table
- Estimated rows: 321460
- Total size: 196 MB

| Column | Type | Null | Default | Comment |
|---|---|---|---|---|
| `measurement_id` | `uuid` | NO | `gen_random_uuid()` |  |
| `dataset_id` | `text` | NO |  |  |
| `field_id` | `text` | NO |  |  |
| `geography_id` | `uuid` | YES |  |  |
| `period_start` | `date` | NO |  |  |
| `period_end` | `date` | YES |  |  |
| `vintage_date` | `date` | YES |  |  |
| `value_numeric` | `numeric` | YES |  |  |
| `value_text` | `text` | YES |  |  |
| `unit` | `text` | YES |  |  |
| `margin_of_error` | `numeric` | YES |  |  |
| `flags` | `jsonb` | NO | `'{}'::jsonb` |  |
| `source_payload_id` | `uuid` | NO |  |  |

Constraints:

- `measurement_dataset_id_fkey` (f): `FOREIGN KEY (dataset_id) REFERENCES catalog.dataset(dataset_id)`
- `measurement_geography_id_fkey` (f): `FOREIGN KEY (geography_id) REFERENCES core.geography(geography_id)`
- `measurement_source_payload_id_fkey` (f): `FOREIGN KEY (source_payload_id) REFERENCES ingest.raw_payload(payload_id)`
- `measurement_pkey` (p): `PRIMARY KEY (measurement_id)`
- `measurement_dataset_id_field_id_geography_id_period_start_p_key` (u): `UNIQUE NULLS NOT DISTINCT (dataset_id, field_id, geography_id, period_start, period_end, vintage_date)`

Indexes:

- `measurement_dataset_id_field_id_geography_id_period_start_p_key`: `CREATE UNIQUE INDEX measurement_dataset_id_field_id_geography_id_period_start_p_key ON fact.measurement USING btree (dataset_id, field_id, geography_id, period_start, period_end, vintage_date) NULLS NOT DISTINCT`
- `measurement_lookup_idx`: `CREATE INDEX measurement_lookup_idx ON fact.measurement USING btree (dataset_id, field_id, period_start)`
- `measurement_pkey`: `CREATE UNIQUE INDEX measurement_pkey ON fact.measurement USING btree (measurement_id)`

#### `fact.member_vote`

- Kind: table
- Estimated rows: 464784
- Total size: 69 MB

| Column | Type | Null | Default | Comment |
|---|---|---|---|---|
| `roll_call_id` | `uuid` | NO |  |  |
| `person_id` | `uuid` | NO |  |  |
| `position` | `text` | NO |  |  |
| `source_payload_id` | `uuid` | YES |  |  |
| `source_artifact_id` | `uuid` | YES |  |  |

Constraints:

- `member_vote_source_evidence` (c): `CHECK (source_artifact_id IS NOT NULL OR source_payload_id IS NOT NULL)`
- `member_vote_person_id_fkey` (f): `FOREIGN KEY (person_id) REFERENCES core.person(person_id)`
- `member_vote_roll_call_id_fkey` (f): `FOREIGN KEY (roll_call_id) REFERENCES core.roll_call(roll_call_id)`
- `member_vote_source_artifact_id_fkey` (f): `FOREIGN KEY (source_artifact_id) REFERENCES ingest.artifact(artifact_id)`
- `member_vote_source_payload_id_fkey` (f): `FOREIGN KEY (source_payload_id) REFERENCES ingest.raw_payload(payload_id)`
- `member_vote_pkey` (p): `PRIMARY KEY (roll_call_id, person_id)`

Indexes:

- `member_vote_pkey`: `CREATE UNIQUE INDEX member_vote_pkey ON fact.member_vote USING btree (roll_call_id, person_id)`

#### `fact.population_estimate`

- Kind: table
- Estimated rows: 55205
- Total size: 23 MB

| Column | Type | Null | Default | Comment |
|---|---|---|---|---|
| `population_estimate_id` | `uuid` | NO | `gen_random_uuid()` |  |
| `release_vintage` | `integer` | NO |  |  |
| `estimate_year` | `integer` | NO |  |  |
| `geography_id` | `uuid` | NO |  |  |
| `population` | `bigint` | NO |  |  |
| `source_artifact_id` | `uuid` | NO |  |  |
| `source_member` | `text` | NO |  |  |
| `source_ordinal` | `bigint` | NO |  |  |
| `loaded_at` | `timestamp with time zone` | NO | `now()` |  |

Constraints:

- `population_estimate_geography_id_fkey` (f): `FOREIGN KEY (geography_id) REFERENCES core.geography(geography_id)`
- `population_estimate_source_artifact_id_fkey` (f): `FOREIGN KEY (source_artifact_id) REFERENCES ingest.artifact(artifact_id)`
- `population_estimate_pkey` (p): `PRIMARY KEY (population_estimate_id)`
- `population_estimate_source_artifact_id_source_member_source_key` (u): `UNIQUE (source_artifact_id, source_member, source_ordinal, estimate_year)`

Indexes:

- `population_estimate_lookup_idx`: `CREATE INDEX population_estimate_lookup_idx ON fact.population_estimate USING btree (release_vintage, estimate_year, geography_id)`
- `population_estimate_pkey`: `CREATE UNIQUE INDEX population_estimate_pkey ON fact.population_estimate USING btree (population_estimate_id)`
- `population_estimate_source_artifact_id_source_member_source_key`: `CREATE UNIQUE INDEX population_estimate_source_artifact_id_source_member_source_key ON fact.population_estimate USING btree (source_artifact_id, source_member, source_ordinal, estimate_year)`

### Schema `ingest`

#### `ingest.artifact`

- Kind: table
- Estimated rows: 2505
- Total size: 2504 kB

| Column | Type | Null | Default | Comment |
|---|---|---|---|---|
| `artifact_id` | `uuid` | NO | `gen_random_uuid()` |  |
| `dataset_id` | `text` | NO |  |  |
| `remote_url` | `text` | NO |  |  |
| `local_path` | `text` | NO |  |  |
| `artifact_key` | `text` | NO |  |  |
| `period_start` | `date` | YES |  |  |
| `period_end` | `date` | YES |  |  |
| `content_type` | `text` | YES |  |  |
| `bytes_downloaded` | `bigint` | YES |  |  |
| `checksum_sha256` | `text` | YES |  |  |
| `status` | `text` | NO |  |  |
| `discovered_at` | `timestamp with time zone` | NO | `now()` |  |
| `downloaded_at` | `timestamp with time zone` | YES |  |  |
| `loaded_at` | `timestamp with time zone` | YES |  |  |
| `metadata` | `jsonb` | NO | `'{}'::jsonb` |  |
| `error_message` | `text` | YES |  |  |

Constraints:

- `artifact_status_check` (c): `CHECK (status = ANY (ARRAY['planned'::text, 'downloading'::text, 'downloaded'::text, 'loaded'::text, 'failed'::text, 'skipped'::text]))`
- `artifact_dataset_id_fkey` (f): `FOREIGN KEY (dataset_id) REFERENCES catalog.dataset(dataset_id)`
- `artifact_pkey` (p): `PRIMARY KEY (artifact_id)`
- `artifact_dataset_id_artifact_key_key` (u): `UNIQUE (dataset_id, artifact_key)`

Indexes:

- `artifact_dataset_id_artifact_key_key`: `CREATE UNIQUE INDEX artifact_dataset_id_artifact_key_key ON ingest.artifact USING btree (dataset_id, artifact_key)`
- `artifact_dataset_status_idx`: `CREATE INDEX artifact_dataset_status_idx ON ingest.artifact USING btree (dataset_id, status)`
- `artifact_pkey`: `CREATE UNIQUE INDEX artifact_pkey ON ingest.artifact USING btree (artifact_id)`

#### `ingest.cursor`

- Kind: table
- Estimated rows: -1
- Total size: 32 kB

| Column | Type | Null | Default | Comment |
|---|---|---|---|---|
| `plan_id` | `text` | NO |  |  |
| `cursor` | `jsonb` | NO | `'{}'::jsonb` |  |
| `successful_run_id` | `uuid` | YES |  |  |
| `updated_at` | `timestamp with time zone` | NO | `now()` |  |

Constraints:

- `cursor_plan_id_fkey` (f): `FOREIGN KEY (plan_id) REFERENCES catalog.plan(plan_id)`
- `cursor_successful_run_id_fkey` (f): `FOREIGN KEY (successful_run_id) REFERENCES ingest.run(run_id)`
- `cursor_pkey` (p): `PRIMARY KEY (plan_id)`

Indexes:

- `cursor_pkey`: `CREATE UNIQUE INDEX cursor_pkey ON ingest.cursor USING btree (plan_id)`

#### `ingest.identity_exception`

- Kind: table
- Estimated rows: -1
- Total size: 64 kB

| Column | Type | Null | Default | Comment |
|---|---|---|---|---|
| `identity_exception_id` | `uuid` | NO | `gen_random_uuid()` |  |
| `dataset_id` | `text` | NO |  |  |
| `run_id` | `uuid` | NO |  |  |
| `source_artifact_id` | `uuid` | NO |  |  |
| `congress` | `integer` | NO |  |  |
| `kind` | `text` | NO |  |  |
| `namespace` | `text` | NO |  |  |
| `external_id` | `text` | NO |  |  |
| `reason` | `text` | NO |  |  |
| `reference_count` | `integer` | NO | `1` |  |
| `first_seen_at` | `timestamp with time zone` | NO | `now()` |  |
| `last_seen_at` | `timestamp with time zone` | NO | `now()` |  |

Constraints:

- `identity_exception_kind_check` (c): `CHECK (kind = 'voter'::text)`
- `identity_exception_reference_count_check` (c): `CHECK (reference_count > 0)`
- `identity_exception_dataset_id_fkey` (f): `FOREIGN KEY (dataset_id) REFERENCES catalog.dataset(dataset_id)`
- `identity_exception_run_id_fkey` (f): `FOREIGN KEY (run_id) REFERENCES ingest.run(run_id)`
- `identity_exception_source_artifact_id_fkey` (f): `FOREIGN KEY (source_artifact_id) REFERENCES ingest.artifact(artifact_id)`
- `identity_exception_pkey` (p): `PRIMARY KEY (identity_exception_id)`
- `identity_exception_run_id_kind_namespace_external_id_reason_key` (u): `UNIQUE (run_id, kind, namespace, external_id, reason)`

Indexes:

- `identity_exception_lookup_idx`: `CREATE INDEX identity_exception_lookup_idx ON ingest.identity_exception USING btree (congress, namespace, external_id)`
- `identity_exception_pkey`: `CREATE UNIQUE INDEX identity_exception_pkey ON ingest.identity_exception USING btree (identity_exception_id)`
- `identity_exception_run_id_kind_namespace_external_id_reason_key`: `CREATE UNIQUE INDEX identity_exception_run_id_kind_namespace_external_id_reason_key ON ingest.identity_exception USING btree (run_id, kind, namespace, external_id, reason)`

#### `ingest.raw_payload`

- Kind: table
- Estimated rows: 170
- Total size: 11 MB

| Column | Type | Null | Default | Comment |
|---|---|---|---|---|
| `payload_id` | `uuid` | NO | `gen_random_uuid()` |  |
| `run_id` | `uuid` | NO |  |  |
| `source_url` | `text` | NO |  |  |
| `fetched_at` | `timestamp with time zone` | NO | `now()` |  |
| `http_status` | `integer` | YES |  |  |
| `content_type` | `text` | YES |  |  |
| `checksum_sha256` | `text` | NO |  |  |
| `payload` | `jsonb` | NO |  |  |

Constraints:

- `raw_payload_run_id_fkey` (f): `FOREIGN KEY (run_id) REFERENCES ingest.run(run_id)`
- `raw_payload_pkey` (p): `PRIMARY KEY (payload_id)`
- `raw_payload_run_id_checksum_sha256_key` (u): `UNIQUE (run_id, checksum_sha256)`

Indexes:

- `raw_payload_pkey`: `CREATE UNIQUE INDEX raw_payload_pkey ON ingest.raw_payload USING btree (payload_id)`
- `raw_payload_run_id_checksum_sha256_key`: `CREATE UNIQUE INDEX raw_payload_run_id_checksum_sha256_key ON ingest.raw_payload USING btree (run_id, checksum_sha256)`
- `raw_payload_run_idx`: `CREATE INDEX raw_payload_run_idx ON ingest.raw_payload USING btree (run_id)`

#### `ingest.resume_cursor`

- Kind: table
- Estimated rows: -1
- Total size: 32 kB

| Column | Type | Null | Default | Comment |
|---|---|---|---|---|
| `dataset_id` | `text` | NO |  |  |
| `cursor_key` | `text` | NO |  |  |
| `cursor` | `jsonb` | NO | `'{}'::jsonb` |  |
| `source_artifact_id` | `uuid` | YES |  |  |
| `last_run_id` | `uuid` | YES |  |  |
| `state` | `text` | NO |  |  |
| `updated_at` | `timestamp with time zone` | NO | `now()` |  |

Constraints:

- `resume_cursor_state_check` (c): `CHECK (state = ANY (ARRAY['running'::text, 'paused'::text, 'complete'::text]))`
- `resume_cursor_dataset_id_fkey` (f): `FOREIGN KEY (dataset_id) REFERENCES catalog.dataset(dataset_id)`
- `resume_cursor_last_run_id_fkey` (f): `FOREIGN KEY (last_run_id) REFERENCES ingest.run(run_id)`
- `resume_cursor_source_artifact_id_fkey` (f): `FOREIGN KEY (source_artifact_id) REFERENCES ingest.artifact(artifact_id)`
- `resume_cursor_pkey` (p): `PRIMARY KEY (dataset_id, cursor_key)`

Indexes:

- `resume_cursor_pkey`: `CREATE UNIQUE INDEX resume_cursor_pkey ON ingest.resume_cursor USING btree (dataset_id, cursor_key)`

#### `ingest.run`

- Kind: table
- Estimated rows: 264
- Total size: 152 kB

| Column | Type | Null | Default | Comment |
|---|---|---|---|---|
| `run_id` | `uuid` | NO | `gen_random_uuid()` |  |
| `dataset_id` | `text` | NO |  |  |
| `mode` | `text` | NO |  |  |
| `status` | `text` | NO |  |  |
| `started_at` | `timestamp with time zone` | NO | `now()` |  |
| `finished_at` | `timestamp with time zone` | YES |  |  |
| `parameters` | `jsonb` | NO | `'{}'::jsonb` |  |
| `record_count` | `bigint` | NO | `0` |  |
| `error_message` | `text` | YES |  |  |
| `code_version` | `text` | YES |  |  |

Constraints:

- `run_mode_check` (c): `CHECK (mode = ANY (ARRAY['backfill'::text, 'incremental'::text, 'manual'::text, 'plan'::text]))`
- `run_status_check` (c): `CHECK (status = ANY (ARRAY['running'::text, 'succeeded'::text, 'failed'::text, 'partial'::text]))`
- `run_dataset_id_fkey` (f): `FOREIGN KEY (dataset_id) REFERENCES catalog.dataset(dataset_id)`
- `run_pkey` (p): `PRIMARY KEY (run_id)`

Indexes:

- `run_pkey`: `CREATE UNIQUE INDEX run_pkey ON ingest.run USING btree (run_id)`

### Schema `leg`

#### `leg.bill`

- Kind: view
- Estimated rows: -1
- Total size: 0 bytes

| Column | Type | Null | Default | Comment |
|---|---|---|---|---|
| `entity_id` | `character varying` | YES |  |  |
| `ocd_id` | `character varying` | YES |  |  |
| `source_system` | `text` | YES |  |  |
| `jurisdiction_id` | `character varying` | YES |  |  |
| `legislative_session_identifier` | `character varying` | YES |  |  |
| `identifier` | `character varying` | YES |  |  |
| `title` | `text` | YES |  |  |
| `classification` | `text[]` | YES |  |  |
| `subject` | `text[]` | YES |  |  |
| `first_action_date` | `character varying` | YES |  |  |
| `latest_action_date` | `character varying` | YES |  |  |
| `latest_action_description` | `text` | YES |  |  |
| `metadata` | `jsonb` | YES |  |  |

#### `leg.person`

- Kind: view
- Estimated rows: -1
- Total size: 0 bytes

| Column | Type | Null | Default | Comment |
|---|---|---|---|---|
| `entity_id` | `character varying` | YES |  |  |
| `ocd_id` | `character varying` | YES |  |  |
| `source_system` | `text` | YES |  |  |
| `name` | `character varying` | YES |  |  |
| `given_name` | `character varying` | YES |  |  |
| `family_name` | `character varying` | YES |  |  |
| `current_jurisdiction_id` | `character varying` | YES |  |  |
| `metadata` | `jsonb` | YES |  |  |

### Schema `mart`

#### `mart.mart_geography_year_measurement`

- Kind: view
- Estimated rows: -1
- Total size: 0 bytes

| Column | Type | Null | Default | Comment |
|---|---|---|---|---|
| `geography_id` | `uuid` | YES |  |  |
| `geography_type` | `text` | YES |  |  |
| `geoid` | `text` | YES |  |  |
| `geography_name` | `text` | YES |  |  |
| `state_fips` | `text` | YES |  |  |
| `county_fips` | `text` | YES |  |  |
| `dataset_id` | `text` | YES |  |  |
| `field_id` | `text` | YES |  |  |
| `period_year` | `integer` | YES |  |  |
| `unit` | `text` | YES |  |  |
| `value_numeric_avg` | `numeric` | YES |  |  |
| `value_numeric_min` | `numeric` | YES |  |  |
| `value_numeric_max` | `numeric` | YES |  |  |
| `observation_count` | `bigint` | YES |  |  |

#### `mart.mart_roll_call_results`

- Kind: view
- Estimated rows: -1
- Total size: 0 bytes

| Column | Type | Null | Default | Comment |
|---|---|---|---|---|
| `roll_call_id` | `uuid` | YES |  |  |
| `jurisdiction` | `text` | YES |  |  |
| `legislative_session` | `text` | YES |  |  |
| `chamber` | `text` | YES |  |  |
| `roll_call_external_id` | `text` | YES |  |  |
| `occurred_at` | `timestamp with time zone` | YES |  |  |
| `question` | `text` | YES |  |  |
| `result` | `text` | YES |  |  |
| `bill_id` | `uuid` | YES |  |  |
| `bill_type` | `text` | YES |  |  |
| `bill_number` | `text` | YES |  |  |
| `bill_title` | `text` | YES |  |  |
| `introduced_date` | `date` | YES |  |  |
| `yea_count` | `bigint` | YES |  |  |
| `nay_count` | `bigint` | YES |  |  |
| `other_count` | `bigint` | YES |  |  |
| `total_votes` | `bigint` | YES |  |  |

#### `mart.stg_bills`

- Kind: view
- Estimated rows: -1
- Total size: 0 bytes

| Column | Type | Null | Default | Comment |
|---|---|---|---|---|
| `bill_id` | `uuid` | YES |  |  |
| `jurisdiction` | `text` | YES |  |  |
| `legislative_session` | `text` | YES |  |  |
| `bill_type` | `text` | YES |  |  |
| `bill_number` | `text` | YES |  |  |
| `title` | `text` | YES |  |  |
| `introduced_date` | `date` | YES |  |  |
| `latest_action_date` | `date` | YES |  |  |
| `latest_action` | `text` | YES |  |  |

#### `mart.stg_geography`

- Kind: view
- Estimated rows: -1
- Total size: 0 bytes

| Column | Type | Null | Default | Comment |
|---|---|---|---|---|
| `geography_id` | `uuid` | YES |  |  |
| `geography_type` | `text` | YES |  |  |
| `geoid` | `text` | YES |  |  |
| `name` | `text` | YES |  |  |
| `state_fips` | `text` | YES |  |  |
| `county_fips` | `text` | YES |  |  |

#### `mart.stg_measurements`

- Kind: view
- Estimated rows: -1
- Total size: 0 bytes

| Column | Type | Null | Default | Comment |
|---|---|---|---|---|
| `measurement_id` | `uuid` | YES |  |  |
| `dataset_id` | `text` | YES |  |  |
| `field_id` | `text` | YES |  |  |
| `geography_id` | `uuid` | YES |  |  |
| `period_start` | `date` | YES |  |  |
| `period_end` | `date` | YES |  |  |
| `vintage_date` | `date` | YES |  |  |
| `value_numeric` | `numeric` | YES |  |  |
| `unit` | `text` | YES |  |  |

#### `mart.stg_member_votes`

- Kind: view
- Estimated rows: -1
- Total size: 0 bytes

| Column | Type | Null | Default | Comment |
|---|---|---|---|---|
| `roll_call_id` | `uuid` | YES |  |  |
| `person_id` | `uuid` | YES |  |  |
| `position` | `text` | YES |  |  |

#### `mart.stg_roll_calls`

- Kind: view
- Estimated rows: -1
- Total size: 0 bytes

| Column | Type | Null | Default | Comment |
|---|---|---|---|---|
| `roll_call_id` | `uuid` | YES |  |  |
| `bill_id` | `uuid` | YES |  |  |
| `jurisdiction` | `text` | YES |  |  |
| `legislative_session` | `text` | YES |  |  |
| `chamber` | `text` | YES |  |  |
| `roll_call_external_id` | `text` | YES |  |  |
| `occurred_at` | `timestamp with time zone` | YES |  |  |
| `question` | `text` | YES |  |  |
| `result` | `text` | YES |  |  |

### Schema `openstates_source`

#### `openstates_source.opencivicdata_bill`

- Kind: foreign table
- Estimated rows: -1
- Total size: 0 bytes

| Column | Type | Null | Default | Comment |
|---|---|---|---|---|
| `created_at` | `timestamp with time zone` | NO |  |  |
| `updated_at` | `timestamp with time zone` | NO |  |  |
| `extras` | `jsonb` | NO |  |  |
| `id` | `character varying(45)` | NO |  |  |
| `identifier` | `character varying(100)` | NO |  |  |
| `title` | `text` | NO |  |  |
| `classification` | `text[]` | NO |  |  |
| `subject` | `text[]` | NO |  |  |
| `from_organization_id` | `character varying(53)` | YES |  |  |
| `legislative_session_id` | `uuid` | NO |  |  |
| `first_action_date` | `character varying(25)` | YES |  |  |
| `latest_action_date` | `character varying(25)` | YES |  |  |
| `latest_action_description` | `text` | NO |  |  |
| `latest_passage_date` | `character varying(25)` | YES |  |  |
| `citations` | `jsonb` | NO |  |  |

#### `openstates_source.opencivicdata_billaction`

- Kind: foreign table
- Estimated rows: -1
- Total size: 0 bytes

| Column | Type | Null | Default | Comment |
|---|---|---|---|---|
| `id` | `uuid` | NO |  |  |
| `description` | `text` | NO |  |  |
| `date` | `character varying(25)` | NO |  |  |
| `classification` | `text[]` | NO |  |  |
| `order` | `integer` | NO |  |  |
| `bill_id` | `character varying(45)` | NO |  |  |
| `organization_id` | `character varying(53)` | NO |  |  |

#### `openstates_source.opencivicdata_billdocument`

- Kind: foreign table
- Estimated rows: -1
- Total size: 0 bytes

| Column | Type | Null | Default | Comment |
|---|---|---|---|---|
| `id` | `uuid` | NO |  |  |
| `note` | `character varying(300)` | NO |  |  |
| `date` | `character varying(10)` | NO |  |  |
| `bill_id` | `character varying(45)` | NO |  |  |
| `extras` | `jsonb` | NO |  |  |
| `classification` | `character varying(100)` | NO |  |  |

#### `openstates_source.opencivicdata_billsponsorship`

- Kind: foreign table
- Estimated rows: -1
- Total size: 0 bytes

| Column | Type | Null | Default | Comment |
|---|---|---|---|---|
| `id` | `uuid` | NO |  |  |
| `name` | `character varying(2000)` | NO |  |  |
| `entity_type` | `character varying(20)` | NO |  |  |
| `primary` | `boolean` | NO |  |  |
| `classification` | `character varying(100)` | NO |  |  |
| `bill_id` | `character varying(45)` | NO |  |  |
| `organization_id` | `character varying(53)` | YES |  |  |
| `person_id` | `character varying(47)` | YES |  |  |

#### `openstates_source.opencivicdata_jurisdiction`

- Kind: foreign table
- Estimated rows: -1
- Total size: 0 bytes

| Column | Type | Null | Default | Comment |
|---|---|---|---|---|
| `created_at` | `timestamp with time zone` | NO |  |  |
| `updated_at` | `timestamp with time zone` | NO |  |  |
| `extras` | `jsonb` | NO |  |  |
| `id` | `character varying(300)` | NO |  |  |
| `name` | `character varying(300)` | NO |  |  |
| `url` | `character varying(2000)` | NO |  |  |
| `classification` | `character varying(50)` | NO |  |  |
| `division_id` | `character varying(300)` | YES |  |  |
| `latest_bill_update` | `timestamp with time zone` | NO |  |  |
| `latest_people_update` | `timestamp with time zone` | NO |  |  |

#### `openstates_source.opencivicdata_legislativesession`

- Kind: foreign table
- Estimated rows: -1
- Total size: 0 bytes

| Column | Type | Null | Default | Comment |
|---|---|---|---|---|
| `id` | `uuid` | NO |  |  |
| `identifier` | `character varying(100)` | NO |  |  |
| `name` | `character varying(300)` | NO |  |  |
| `classification` | `character varying(100)` | NO |  |  |
| `start_date` | `character varying(10)` | NO |  |  |
| `end_date` | `character varying(10)` | NO |  |  |
| `jurisdiction_id` | `character varying(300)` | NO |  |  |
| `active` | `boolean` | NO |  |  |

#### `openstates_source.opencivicdata_organization`

- Kind: foreign table
- Estimated rows: -1
- Total size: 0 bytes

| Column | Type | Null | Default | Comment |
|---|---|---|---|---|
| `created_at` | `timestamp with time zone` | NO |  |  |
| `updated_at` | `timestamp with time zone` | NO |  |  |
| `extras` | `jsonb` | NO |  |  |
| `id` | `character varying(53)` | NO |  |  |
| `name` | `character varying(300)` | NO |  |  |
| `classification` | `character varying(100)` | NO |  |  |
| `jurisdiction_id` | `character varying(300)` | YES |  |  |
| `parent_id` | `character varying(53)` | YES |  |  |
| `links` | `jsonb` | NO |  |  |
| `sources` | `jsonb` | NO |  |  |
| `other_names` | `jsonb` | NO |  |  |

#### `openstates_source.opencivicdata_person`

- Kind: foreign table
- Estimated rows: -1
- Total size: 0 bytes

| Column | Type | Null | Default | Comment |
|---|---|---|---|---|
| `created_at` | `timestamp with time zone` | NO |  |  |
| `updated_at` | `timestamp with time zone` | NO |  |  |
| `extras` | `jsonb` | NO |  |  |
| `id` | `character varying(47)` | NO |  |  |
| `name` | `character varying(300)` | NO |  |  |
| `family_name` | `character varying(100)` | NO |  |  |
| `given_name` | `character varying(100)` | NO |  |  |
| `image` | `character varying(2000)` | NO |  |  |
| `gender` | `character varying(100)` | NO |  |  |
| `biography` | `text` | NO |  |  |
| `birth_date` | `character varying(10)` | NO |  |  |
| `death_date` | `character varying(10)` | NO |  |  |
| `primary_party` | `character varying(100)` | NO |  |  |
| `current_jurisdiction_id` | `character varying(300)` | YES |  |  |
| `current_role` | `jsonb` | YES |  |  |
| `email` | `character varying(300)` | NO |  |  |

#### `openstates_source.opencivicdata_personidentifier`

- Kind: foreign table
- Estimated rows: -1
- Total size: 0 bytes

| Column | Type | Null | Default | Comment |
|---|---|---|---|---|
| `id` | `uuid` | NO |  |  |
| `identifier` | `character varying(300)` | NO |  |  |
| `scheme` | `character varying(300)` | NO |  |  |
| `person_id` | `character varying(47)` | NO |  |  |

#### `openstates_source.opencivicdata_personvote`

- Kind: foreign table
- Estimated rows: -1
- Total size: 0 bytes

| Column | Type | Null | Default | Comment |
|---|---|---|---|---|
| `id` | `uuid` | NO |  |  |
| `option` | `character varying(50)` | NO |  |  |
| `voter_name` | `character varying(300)` | NO |  |  |
| `note` | `text` | NO |  |  |
| `vote_event_id` | `character varying(45)` | NO |  |  |
| `voter_id` | `character varying(47)` | YES |  |  |

#### `openstates_source.opencivicdata_voteevent`

- Kind: foreign table
- Estimated rows: -1
- Total size: 0 bytes

| Column | Type | Null | Default | Comment |
|---|---|---|---|---|
| `created_at` | `timestamp with time zone` | NO |  |  |
| `updated_at` | `timestamp with time zone` | NO |  |  |
| `extras` | `jsonb` | NO |  |  |
| `id` | `character varying(45)` | NO |  |  |
| `identifier` | `character varying(300)` | NO |  |  |
| `motion_text` | `text` | NO |  |  |
| `motion_classification` | `text[]` | NO |  |  |
| `start_date` | `character varying(25)` | NO |  |  |
| `result` | `character varying(50)` | NO |  |  |
| `bill_id` | `character varying(45)` | YES |  |  |
| `bill_action_id` | `uuid` | YES |  |  |
| `legislative_session_id` | `uuid` | NO |  |  |
| `organization_id` | `character varying(53)` | NO |  |  |
| `order` | `integer` | NO |  |  |
| `dedupe_key` | `character varying(500)` | YES |  |  |

### Schema `public`

#### `public.alembic_version`

- Kind: table
- Estimated rows: -1
- Total size: 24 kB

| Column | Type | Null | Default | Comment |
|---|---|---|---|---|
| `version_num` | `character varying(32)` | NO |  |  |

Constraints:

- `alembic_version_pkc` (p): `PRIMARY KEY (version_num)`

Indexes:

- `alembic_version_pkc`: `CREATE UNIQUE INDEX alembic_version_pkc ON public.alembic_version USING btree (version_num)`

### Schema `stage`

#### `stage.acs_bulk_row`

- Kind: table
- Estimated rows: 5602131
- Total size: 5191 MB

| Column | Type | Null | Default | Comment |
|---|---|---|---|---|
| `artifact_id` | `uuid` | NO |  |  |
| `source_ordinal` | `bigint` | NO |  |  |
| `release_year` | `integer` | NO |  |  |
| `table_id` | `text` | NO |  |  |
| `geography_type` | `text` | NO |  |  |
| `geoid` | `text` | NO |  |  |
| `raw` | `jsonb` | NO |  |  |

Constraints:

- `acs_bulk_row_artifact_id_fkey` (f): `FOREIGN KEY (artifact_id) REFERENCES ingest.artifact(artifact_id)`
- `acs_bulk_row_pkey` (p): `PRIMARY KEY (artifact_id, source_ordinal)`

Indexes:

- `acs_bulk_row_pkey`: `CREATE UNIQUE INDEX acs_bulk_row_pkey ON stage.acs_bulk_row USING btree (artifact_id, source_ordinal)`

#### `stage.cbp_row`

- Kind: table
- Estimated rows: 29237760
- Total size: 22 GB

| Column | Type | Null | Default | Comment |
|---|---|---|---|---|
| `artifact_id` | `uuid` | NO |  |  |
| `source_member` | `text` | NO |  |  |
| `source_ordinal` | `bigint` | NO |  |  |
| `geography_level` | `text` | NO |  |  |
| `raw` | `jsonb` | NO |  |  |
| `staged_at` | `timestamp with time zone` | NO | `now()` |  |

Constraints:

- `cbp_row_artifact_id_fkey` (f): `FOREIGN KEY (artifact_id) REFERENCES ingest.artifact(artifact_id)`
- `cbp_row_pkey` (p): `PRIMARY KEY (artifact_id, source_member, source_ordinal)`

Indexes:

- `cbp_row_pkey`: `CREATE UNIQUE INDEX cbp_row_pkey ON stage.cbp_row USING btree (artifact_id, source_member, source_ordinal)`

#### `stage.dhc_geo_row`

- Kind: table
- Estimated rows: 11379
- Total size: 9288 kB

| Column | Type | Null | Default | Comment |
|---|---|---|---|---|
| `artifact_id` | `uuid` | NO |  |  |
| `source_member` | `text` | NO |  |  |
| `source_ordinal` | `bigint` | NO |  |  |
| `logrecno` | `text` | NO |  |  |
| `sumlev` | `text` | NO |  |  |
| `geoid` | `text` | YES |  |  |
| `raw` | `jsonb` | NO |  |  |

Constraints:

- `dhc_geo_row_artifact_id_fkey` (f): `FOREIGN KEY (artifact_id) REFERENCES ingest.artifact(artifact_id)`
- `dhc_geo_row_pkey` (p): `PRIMARY KEY (artifact_id, source_member, source_ordinal)`

Indexes:

- `dhc_geo_lookup_idx`: `CREATE INDEX dhc_geo_lookup_idx ON stage.dhc_geo_row USING btree (artifact_id, logrecno, sumlev)`
- `dhc_geo_row_pkey`: `CREATE UNIQUE INDEX dhc_geo_row_pkey ON stage.dhc_geo_row USING btree (artifact_id, source_member, source_ordinal)`

#### `stage.fec_row`

- Kind: table
- Estimated rows: 101668128
- Total size: 74 GB

| Column | Type | Null | Default | Comment |
|---|---|---|---|---|
| `artifact_id` | `uuid` | NO |  |  |
| `family` | `text` | NO |  |  |
| `cycle` | `smallint` | NO |  |  |
| `source_ordinal` | `bigint` | NO |  |  |
| `raw` | `jsonb` | NO |  |  |
| `staged_at` | `timestamp with time zone` | NO | `now()` |  |

Constraints:

- `fec_row_artifact_id_fkey` (f): `FOREIGN KEY (artifact_id) REFERENCES ingest.artifact(artifact_id)`
- `fec_row_pkey` (p): `PRIMARY KEY (artifact_id, source_ordinal)`

Indexes:

- `fec_row_family_cycle_idx`: `CREATE INDEX fec_row_family_cycle_idx ON stage.fec_row USING btree (family, cycle)`
- `fec_row_pkey`: `CREATE UNIQUE INDEX fec_row_pkey ON stage.fec_row USING btree (artifact_id, source_ordinal)`

#### `stage.pep_row`

- Kind: table
- Estimated rows: 6495
- Total size: 13 MB

| Column | Type | Null | Default | Comment |
|---|---|---|---|---|
| `artifact_id` | `uuid` | NO |  |  |
| `source_member` | `text` | NO |  |  |
| `source_ordinal` | `bigint` | NO |  |  |
| `geography_level` | `text` | NO |  |  |
| `raw` | `jsonb` | NO |  |  |
| `staged_at` | `timestamp with time zone` | NO | `now()` |  |

Constraints:

- `pep_row_artifact_id_fkey` (f): `FOREIGN KEY (artifact_id) REFERENCES ingest.artifact(artifact_id)`
- `pep_row_pkey` (p): `PRIMARY KEY (artifact_id, source_member, source_ordinal)`

Indexes:

- `pep_row_pkey`: `CREATE UNIQUE INDEX pep_row_pkey ON stage.pep_row USING btree (artifact_id, source_member, source_ordinal)`

#### `stage.tiger_feature`

- Kind: table
- Estimated rows: 373854
- Total size: 10 GB

| Column | Type | Null | Default | Comment |
|---|---|---|---|---|
| `artifact_id` | `uuid` | NO |  |  |
| `layer` | `text` | NO |  |  |
| `source_ordinal` | `bigint` | NO |  |  |
| `geoid` | `text` | NO |  |  |
| `name` | `text` | YES |  |  |
| `state_fips` | `text` | YES |  |  |
| `county_fips` | `text` | YES |  |  |
| `raw` | `jsonb` | NO |  |  |
| `geom` | `geometry(Geometry,4326)` | NO |  |  |
| `staged_at` | `timestamp with time zone` | NO | `now()` |  |

Constraints:

- `tiger_feature_artifact_id_fkey` (f): `FOREIGN KEY (artifact_id) REFERENCES ingest.artifact(artifact_id)`
- `tiger_feature_pkey` (p): `PRIMARY KEY (artifact_id, source_ordinal)`

Indexes:

- `tiger_feature_geom_idx`: `CREATE INDEX tiger_feature_geom_idx ON stage.tiger_feature USING gist (geom)`
- `tiger_feature_pkey`: `CREATE UNIQUE INDEX tiger_feature_pkey ON stage.tiger_feature USING btree (artifact_id, source_ordinal)`

## View definitions

### `leg.bill`

```sql
 SELECT bill.id AS entity_id,
    bill.id AS ocd_id,
    'openstates'::text AS source_system,
    jurisdiction.id AS jurisdiction_id,
    session.identifier AS legislative_session_identifier,
    bill.identifier,
    bill.title,
    bill.classification,
    bill.subject,
    bill.first_action_date,
    bill.latest_action_date,
    bill.latest_action_description,
    bill.extras AS metadata
   FROM openstates_source.opencivicdata_bill bill
     JOIN openstates_source.opencivicdata_legislativesession session ON session.id = bill.legislative_session_id
     JOIN openstates_source.opencivicdata_jurisdiction jurisdiction ON jurisdiction.id::text = session.jurisdiction_id::text
UNION ALL
 SELECT bill.bill_id::text AS entity_id,
    bill.ocd_id,
    'opendiscourse'::text AS source_system,
    COALESCE(session.jurisdiction_id, bill.jurisdiction) AS jurisdiction_id,
    COALESCE(session.identifier, bill.legislative_session) AS legislative_session_identifier,
    (bill.bill_type || ' '::text) || bill.bill_number AS identifier,
    bill.title,
    ARRAY[bill.bill_type] AS classification,
    ARRAY[]::text[] AS subject,
    bill.introduced_date::text AS first_action_date,
    bill.latest_action_date::text AS latest_action_date,
    bill.latest_action AS latest_action_description,
    bill.metadata
   FROM core.bill bill
     LEFT JOIN core.legislative_session session ON session.legislative_session_id = bill.legislative_session_id;;
```

### `leg.person`

```sql
 SELECT person.id AS entity_id,
    person.id AS ocd_id,
    'openstates'::text AS source_system,
    person.name,
    person.given_name,
    person.family_name,
    person.current_jurisdiction_id,
    person.extras AS metadata
   FROM openstates_source.opencivicdata_person person
UNION ALL
 SELECT person.person_id::text AS entity_id,
    identifier.external_id AS ocd_id,
    'opendiscourse'::text AS source_system,
    person.full_name AS name,
    person.given_name,
    person.family_name,
    NULL::text AS current_jurisdiction_id,
    person.metadata
   FROM core.person person
     LEFT JOIN LATERAL ( SELECT person_identifier.external_id
           FROM core.person_identifier
          WHERE person_identifier.person_id = person.person_id AND person_identifier.namespace = 'ocd'::text
          ORDER BY person_identifier.valid_from
         LIMIT 1) identifier ON true;;
```

### `mart.mart_geography_year_measurement`

```sql
 SELECT g.geography_id,
    g.geography_type,
    g.geoid,
    g.name AS geography_name,
    g.state_fips,
    g.county_fips,
    m.dataset_id,
    m.field_id,
    EXTRACT(year FROM m.period_start)::integer AS period_year,
    m.unit,
    avg(m.value_numeric) AS value_numeric_avg,
    min(m.value_numeric) AS value_numeric_min,
    max(m.value_numeric) AS value_numeric_max,
    count(*) AS observation_count
   FROM mart.stg_measurements m
     LEFT JOIN mart.stg_geography g ON g.geography_id = m.geography_id
  GROUP BY g.geography_id, g.geography_type, g.geoid, g.name, g.state_fips, g.county_fips, m.dataset_id, m.field_id, (EXTRACT(year FROM m.period_start)), m.unit;;
```

### `mart.mart_roll_call_results`

```sql
 WITH votes AS (
         SELECT stg_member_votes.roll_call_id,
            count(*) FILTER (WHERE stg_member_votes."position" = 'yes'::text) AS yea_count,
            count(*) FILTER (WHERE stg_member_votes."position" = 'no'::text) AS nay_count,
            count(*) FILTER (WHERE stg_member_votes."position" <> ALL (ARRAY['yes'::text, 'no'::text])) AS other_count,
            count(*) AS total_votes
           FROM mart.stg_member_votes
          GROUP BY stg_member_votes.roll_call_id
        )
 SELECT rc.roll_call_id,
    rc.jurisdiction,
    rc.legislative_session,
    rc.chamber,
    rc.roll_call_external_id,
    rc.occurred_at,
    rc.question,
    rc.result,
    b.bill_id,
    b.bill_type,
    b.bill_number,
    b.title AS bill_title,
    b.introduced_date,
    COALESCE(v.yea_count, 0::bigint) AS yea_count,
    COALESCE(v.nay_count, 0::bigint) AS nay_count,
    COALESCE(v.other_count, 0::bigint) AS other_count,
    COALESCE(v.total_votes, 0::bigint) AS total_votes
   FROM mart.stg_roll_calls rc
     LEFT JOIN mart.stg_bills b ON b.bill_id = rc.bill_id
     LEFT JOIN votes v ON v.roll_call_id = rc.roll_call_id;;
```

### `mart.stg_bills`

```sql
 SELECT bill_id,
    jurisdiction,
    legislative_session,
    bill_type,
    bill_number,
    title,
    introduced_date,
    latest_action_date,
    latest_action
   FROM core.bill;;
```

### `mart.stg_geography`

```sql
 SELECT geography_id,
    geography_type,
    geoid,
    name,
    state_fips,
    county_fips
   FROM core.geography;;
```

### `mart.stg_measurements`

```sql
 SELECT measurement_id,
    dataset_id,
    field_id,
    geography_id,
    period_start,
    period_end,
    vintage_date,
    value_numeric,
    unit
   FROM fact.measurement;;
```

### `mart.stg_member_votes`

```sql
 SELECT roll_call_id,
    person_id,
    "position"
   FROM fact.member_vote;;
```

### `mart.stg_roll_calls`

```sql
 SELECT roll_call_id,
    bill_id,
    jurisdiction,
    legislative_session,
    chamber,
    external_id AS roll_call_external_id,
    occurred_at,
    question,
    result
   FROM core.roll_call;;
```
