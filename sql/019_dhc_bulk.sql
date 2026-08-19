CREATE TABLE IF NOT EXISTS stage.dhc_geo_row (
  artifact_id uuid NOT NULL REFERENCES ingest.artifact(artifact_id),
  source_member text NOT NULL,
  source_ordinal bigint NOT NULL,
  logrecno text NOT NULL,
  sumlev text NOT NULL,
  geoid text,
  raw jsonb NOT NULL,
  PRIMARY KEY (artifact_id, source_member, source_ordinal)
);
CREATE INDEX IF NOT EXISTS dhc_geo_lookup_idx ON stage.dhc_geo_row (artifact_id, logrecno, sumlev);

CREATE TABLE IF NOT EXISTS fact.decennial_dhc_value (
  dhc_value_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  release_year integer NOT NULL,
  geography_id uuid NOT NULL REFERENCES core.geography(geography_id),
  table_id text NOT NULL,
  variable_id text NOT NULL,
  value bigint,
  source_artifact_id uuid NOT NULL REFERENCES ingest.artifact(artifact_id),
  source_member text NOT NULL,
  source_ordinal bigint NOT NULL,
  UNIQUE (source_artifact_id, source_member, source_ordinal, variable_id)
);
CREATE INDEX IF NOT EXISTS dhc_value_lookup_idx
  ON fact.decennial_dhc_value (release_year, geography_id, table_id, variable_id);
