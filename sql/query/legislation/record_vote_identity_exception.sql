INSERT INTO ingest.identity_exception
  (dataset_id, run_id, source_artifact_id, congress, kind, namespace,
   external_id, reason, reference_count)
VALUES
  (%(dataset_id)s, %(run_id)s, %(source_artifact_id)s, %(congress)s, 'voter',
   'ocd', %(external_id)s, %(reason)s, %(reference_count)s)
ON CONFLICT (run_id, kind, namespace, external_id, reason) DO UPDATE SET
  reference_count = ingest.identity_exception.reference_count + EXCLUDED.reference_count,
  last_seen_at = now();
