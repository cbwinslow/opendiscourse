CREATE TABLE IF NOT EXISTS stage.pep_row (
  artifact_id uuid NOT NULL REFERENCES ingest.artifact(artifact_id),
  source_member text NOT NULL,
  source_ordinal bigint NOT NULL,
  geography_level text NOT NULL,
  raw jsonb NOT NULL,
  staged_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (artifact_id, source_member, source_ordinal)
);

CREATE TABLE IF NOT EXISTS fact.population_estimate (
  population_estimate_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  release_vintage integer NOT NULL,
  estimate_year integer NOT NULL,
  geography_id uuid NOT NULL REFERENCES core.geography(geography_id),
  population bigint NOT NULL,
  source_artifact_id uuid NOT NULL REFERENCES ingest.artifact(artifact_id),
  source_member text NOT NULL,
  source_ordinal bigint NOT NULL,
  loaded_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (source_artifact_id, source_member, source_ordinal, estimate_year)
);
CREATE INDEX IF NOT EXISTS population_estimate_lookup_idx
  ON fact.population_estimate (release_vintage, estimate_year, geography_id);
