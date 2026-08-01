CREATE SCHEMA IF NOT EXISTS catalog;
CREATE SCHEMA IF NOT EXISTS ingest;
CREATE SCHEMA IF NOT EXISTS core;
CREATE SCHEMA IF NOT EXISTS fact;

CREATE TABLE IF NOT EXISTS catalog.provider (
  provider_id text PRIMARY KEY,
  name text NOT NULL,
  base_url text,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS catalog.dataset (
  dataset_id text PRIMARY KEY,
  provider_id text NOT NULL REFERENCES catalog.provider(provider_id),
  title text NOT NULL,
  access_method text,
  grain_description text,
  refresh_cadence text,
  priority smallint,
  active boolean NOT NULL DEFAULT true,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS catalog.dataset_field (
  dataset_id text NOT NULL REFERENCES catalog.dataset(dataset_id),
  field_id text NOT NULL,
  label text,
  data_type text,
  description text,
  valid_from date,
  valid_to date,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  PRIMARY KEY (dataset_id, field_id, valid_from)
);

CREATE TABLE IF NOT EXISTS ingest.run (
  run_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  dataset_id text NOT NULL REFERENCES catalog.dataset(dataset_id),
  mode text NOT NULL CHECK (mode IN ('backfill', 'incremental', 'manual')),
  status text NOT NULL CHECK (status IN ('running', 'succeeded', 'failed', 'partial')),
  started_at timestamptz NOT NULL DEFAULT now(),
  finished_at timestamptz,
  parameters jsonb NOT NULL DEFAULT '{}'::jsonb,
  record_count bigint NOT NULL DEFAULT 0,
  error_message text,
  code_version text
);

CREATE TABLE IF NOT EXISTS ingest.raw_payload (
  payload_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  run_id uuid NOT NULL REFERENCES ingest.run(run_id),
  source_url text NOT NULL,
  fetched_at timestamptz NOT NULL DEFAULT now(),
  http_status integer,
  content_type text,
  checksum_sha256 text NOT NULL,
  payload jsonb NOT NULL,
  UNIQUE (run_id, checksum_sha256)
);
CREATE INDEX IF NOT EXISTS raw_payload_run_idx ON ingest.raw_payload(run_id);

CREATE TABLE IF NOT EXISTS core.geography (
  geography_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  geography_type text NOT NULL,
  geoid text NOT NULL,
  name text,
  parent_geoid text,
  state_fips text,
  county_fips text,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  UNIQUE (geography_type, geoid)
);

CREATE TABLE IF NOT EXISTS core.geography_boundary (
  boundary_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  geography_id uuid NOT NULL REFERENCES core.geography(geography_id),
  boundary_vintage integer NOT NULL,
  valid_from date,
  valid_to date,
  geom geometry(Geometry, 4326) NOT NULL,
  source_payload_id uuid REFERENCES ingest.raw_payload(payload_id),
  UNIQUE (geography_id, boundary_vintage)
);
CREATE INDEX IF NOT EXISTS geography_boundary_geom_idx ON core.geography_boundary USING gist(geom);

CREATE TABLE IF NOT EXISTS core.organization (
  organization_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_type text NOT NULL,
  name text NOT NULL,
  jurisdiction_geoid text,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS core.person (
  person_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  full_name text NOT NULL,
  given_name text,
  family_name text,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb
);
CREATE TABLE IF NOT EXISTS core.person_identifier (
  person_id uuid NOT NULL REFERENCES core.person(person_id),
  namespace text NOT NULL,
  external_id text NOT NULL,
  valid_from date,
  valid_to date,
  PRIMARY KEY (namespace, external_id)
);

CREATE TABLE IF NOT EXISTS core.instrument (
  instrument_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  instrument_type text NOT NULL,
  name text,
  currency text,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb
);
CREATE TABLE IF NOT EXISTS core.instrument_symbol (
  instrument_id uuid NOT NULL REFERENCES core.instrument(instrument_id),
  symbol text NOT NULL,
  exchange text NOT NULL DEFAULT '',
  valid_from date,
  valid_to date,
  PRIMARY KEY (symbol, exchange, valid_from)
);
