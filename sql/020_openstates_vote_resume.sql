CREATE TABLE IF NOT EXISTS ingest.resume_cursor (
  dataset_id text NOT NULL REFERENCES catalog.dataset(dataset_id),
  cursor_key text NOT NULL,
  cursor jsonb NOT NULL DEFAULT '{}'::jsonb,
  source_artifact_id uuid REFERENCES ingest.artifact(artifact_id),
  last_run_id uuid REFERENCES ingest.run(run_id),
  state text NOT NULL CHECK (state IN ('running', 'paused', 'complete')),
  updated_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (dataset_id, cursor_key)
);
