CREATE SCHEMA IF NOT EXISTS stage;

CREATE TABLE IF NOT EXISTS stage.cbp_row (
  artifact_id uuid NOT NULL REFERENCES ingest.artifact(artifact_id),
  source_member text NOT NULL,
  source_ordinal bigint NOT NULL,
  geography_level text NOT NULL,
  raw jsonb NOT NULL,
  staged_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (artifact_id, source_member, source_ordinal)
);

CREATE TABLE IF NOT EXISTS fact.business_pattern (
  business_pattern_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  release_year integer NOT NULL,
  geography_id uuid NOT NULL REFERENCES core.geography(geography_id),
  naics text NOT NULL,
  legal_form text NOT NULL DEFAULT '',
  establishments bigint,
  employment bigint,
  first_quarter_payroll numeric,
  annual_payroll numeric,
  flags jsonb NOT NULL DEFAULT '{}'::jsonb,
  source_artifact_id uuid NOT NULL REFERENCES ingest.artifact(artifact_id),
  source_member text NOT NULL,
  source_ordinal bigint NOT NULL,
  loaded_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (source_artifact_id, source_member, source_ordinal)
);
CREATE INDEX IF NOT EXISTS business_pattern_lookup_idx
  ON fact.business_pattern (release_year, geography_id, naics);
