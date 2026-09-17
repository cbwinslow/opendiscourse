SELECT artifact_id, dataset_id, remote_url, local_path, artifact_key, artifact_version, status, checksum_sha256, metadata
FROM ingest.artifact
WHERE dataset_id = %(dataset_id)s
  AND artifact_key = %(artifact_key)s
  AND (%(version)s::integer IS NULL OR artifact_version = %(version)s::integer)
ORDER BY artifact_version DESC
LIMIT 1;
