SELECT cursor, source_artifact_id, last_run_id, state, updated_at
FROM ingest.resume_cursor
WHERE dataset_id = %(dataset_id)s AND cursor_key = %(cursor_key)s;
