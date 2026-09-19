INSERT INTO ingest.identity_conflict (dataset_id, run_id, kind, subject, person_ids, identifiers)
VALUES (%(dataset_id)s, %(run_id)s, %(kind)s, %(subject)s, %(person_ids)s, %(identifiers)s)
ON CONFLICT (dataset_id, kind, subject, person_ids) DO UPDATE
  SET seen_count = ingest.identity_conflict.seen_count + 1,
      last_seen_at = now(),
      resolved_at = NULL,
      resolution = NULL,
      run_id = coalesce(EXCLUDED.run_id, ingest.identity_conflict.run_id),
      identifiers = EXCLUDED.identifiers
