-- Other versions of one logical artifact: the versions a newer load supersedes.
SELECT artifact_id
FROM ingest.artifact
WHERE dataset_id = %(dataset_id)s
  AND artifact_key = %(artifact_key)s
  AND artifact_id <> %(keep_artifact_id)s;
