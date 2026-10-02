SELECT artifact_id::text, artifact_key, checksum_sha256, bytes_downloaded, status
FROM ingest.current_artifact WHERE dataset_id = 'openstates.dump'
ORDER BY artifact_key;
