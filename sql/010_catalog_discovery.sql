CREATE TABLE IF NOT EXISTS catalog.discovery (
  discovery_id text PRIMARY KEY,
  dataset_id text NOT NULL REFERENCES catalog.dataset(dataset_id),
  state text NOT NULL DEFAULT 'idle'
    CHECK (state IN ('idle', 'running', 'paused', 'complete', 'failed')),
  cursor jsonb NOT NULL DEFAULT '{}'::jsonb,
  statistics jsonb NOT NULL DEFAULT '{}'::jsonb,
  error_message text,
  started_at timestamptz,
  finished_at timestamptz,
  updated_at timestamptz NOT NULL DEFAULT now()
);
