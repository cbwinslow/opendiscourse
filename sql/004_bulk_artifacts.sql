CREATE TABLE IF NOT EXISTS ingest.artifact (
  artifact_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  dataset_id text NOT NULL REFERENCES catalog.dataset(dataset_id),
  remote_url text NOT NULL,
  local_path text NOT NULL,
  artifact_key text NOT NULL,
  period_start date,
  period_end date,
  content_type text,
  bytes_downloaded bigint,
  checksum_sha256 text,
  status text NOT NULL CHECK (status IN ('planned', 'downloading', 'downloaded', 'loaded', 'failed', 'skipped')),
  discovered_at timestamptz NOT NULL DEFAULT now(),
  downloaded_at timestamptz,
  loaded_at timestamptz,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  error_message text,
  UNIQUE (dataset_id, artifact_key)
);
CREATE INDEX IF NOT EXISTS artifact_dataset_status_idx ON ingest.artifact(dataset_id, status);
