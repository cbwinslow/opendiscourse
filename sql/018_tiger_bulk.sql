CREATE TABLE IF NOT EXISTS stage.tiger_feature (
  artifact_id uuid NOT NULL REFERENCES ingest.artifact(artifact_id),
  layer text NOT NULL,
  source_ordinal bigint NOT NULL,
  geoid text NOT NULL,
  name text,
  state_fips text,
  county_fips text,
  raw jsonb NOT NULL,
  geom geometry(Geometry, 4326) NOT NULL,
  staged_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (artifact_id, source_ordinal)
);

ALTER TABLE core.geography_boundary
  ADD COLUMN IF NOT EXISTS source_artifact_id uuid REFERENCES ingest.artifact(artifact_id);
CREATE INDEX IF NOT EXISTS tiger_feature_geom_idx ON stage.tiger_feature USING gist(geom);
