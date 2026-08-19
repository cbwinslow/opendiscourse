INSERT INTO ingest.resume_cursor
  (dataset_id, cursor_key, cursor, source_artifact_id, last_run_id, state)
VALUES
  (%(dataset_id)s, %(cursor_key)s, %(cursor)s, %(source_artifact_id)s,
   %(last_run_id)s, %(state)s)
ON CONFLICT (dataset_id, cursor_key) DO UPDATE SET
  cursor = EXCLUDED.cursor,
  source_artifact_id = EXCLUDED.source_artifact_id,
  last_run_id = EXCLUDED.last_run_id,
  state = EXCLUDED.state,
  updated_at = now()
RETURNING cursor, state;
