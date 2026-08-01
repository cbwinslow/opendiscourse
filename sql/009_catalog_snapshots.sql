CREATE TABLE IF NOT EXISTS catalog.snapshot (
  snapshot_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  dataset_id text NOT NULL REFERENCES catalog.dataset(dataset_id),
  source_url text NOT NULL,
  checksum_sha256 text NOT NULL,
  artifact_id uuid REFERENCES ingest.artifact(artifact_id),
  captured_at timestamptz NOT NULL DEFAULT now(),
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  UNIQUE (dataset_id, checksum_sha256)
);

CREATE TABLE IF NOT EXISTS catalog.snapshot_resource (
  snapshot_id uuid NOT NULL REFERENCES catalog.snapshot(snapshot_id) ON DELETE CASCADE,
  resource_id uuid NOT NULL REFERENCES catalog.resource(resource_id) ON DELETE RESTRICT,
  PRIMARY KEY (snapshot_id, resource_id)
);
