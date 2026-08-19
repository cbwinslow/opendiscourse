CREATE TABLE IF NOT EXISTS stage.fec_row (
  artifact_id uuid NOT NULL REFERENCES ingest.artifact(artifact_id),
  family text NOT NULL,
  cycle smallint NOT NULL,
  source_ordinal bigint NOT NULL,
  raw jsonb NOT NULL,
  staged_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (artifact_id, source_ordinal)
);
CREATE INDEX IF NOT EXISTS fec_row_family_cycle_idx ON stage.fec_row (family, cycle);
