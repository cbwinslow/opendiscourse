SELECT artifact_id, dataset_id, remote_url, local_path, artifact_key, status, checksum_sha256, metadata
FROM ingest.artifact
WHERE dataset_id = %(dataset_id)s AND artifact_key = %(artifact_key)s;
