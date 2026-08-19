CREATE TABLE IF NOT EXISTS ingest.identity_exception (
  identity_exception_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  dataset_id text NOT NULL REFERENCES catalog.dataset(dataset_id),
  run_id uuid NOT NULL REFERENCES ingest.run(run_id),
  source_artifact_id uuid NOT NULL REFERENCES ingest.artifact(artifact_id),
  congress integer NOT NULL,
  kind text NOT NULL CHECK (kind IN ('voter')),
  namespace text NOT NULL,
  external_id text NOT NULL,
  reason text NOT NULL,
  reference_count integer NOT NULL DEFAULT 1 CHECK (reference_count > 0),
  first_seen_at timestamptz NOT NULL DEFAULT now(),
  last_seen_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (run_id, kind, namespace, external_id, reason)
);

CREATE INDEX IF NOT EXISTS identity_exception_lookup_idx
  ON ingest.identity_exception (congress, namespace, external_id);
