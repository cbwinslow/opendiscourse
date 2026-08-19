CREATE TABLE IF NOT EXISTS stage.acs_bulk_row (
  artifact_id uuid NOT NULL REFERENCES ingest.artifact(artifact_id),
  source_ordinal bigint NOT NULL,
  release_year integer NOT NULL,
  table_id text NOT NULL,
  geography_type text NOT NULL,
  geoid text NOT NULL,
  raw jsonb NOT NULL,
  PRIMARY KEY (artifact_id, source_ordinal)
);

CREATE TABLE IF NOT EXISTS fact.acs_bulk_estimate (
  acs_bulk_estimate_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  release_year integer NOT NULL,
  geography_id uuid NOT NULL REFERENCES core.geography(geography_id),
  table_id text NOT NULL,
  field_id text NOT NULL,
  measure text NOT NULL CHECK (measure IN ('estimate', 'margin_of_error')),
  value numeric,
  source_artifact_id uuid NOT NULL REFERENCES ingest.artifact(artifact_id),
  source_ordinal bigint NOT NULL,
  UNIQUE (source_artifact_id, source_ordinal, field_id)
);

CREATE INDEX IF NOT EXISTS acs_bulk_estimate_lookup_idx
  ON fact.acs_bulk_estimate (release_year, geography_id, table_id, field_id);
