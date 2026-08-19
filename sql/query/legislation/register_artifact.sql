INSERT INTO ingest.artifact (
  dataset_id, remote_url, local_path, artifact_key,
  period_start, period_end, content_type, bytes_downloaded, checksum_sha256,
  status, metadata
) VALUES (
  %(dataset_id)s, %(remote_url)s, %(local_path)s, %(artifact_key)s,
  %(period_start)s, %(period_end)s, %(content_type)s, %(bytes_downloaded)s, %(checksum_sha256)s,
  %(status)s, %(metadata)s
)
ON CONFLICT (dataset_id, artifact_key) DO UPDATE SET
  remote_url = EXCLUDED.remote_url,
  local_path = EXCLUDED.local_path,
  period_start = COALESCE(EXCLUDED.period_start, ingest.artifact.period_start),
  period_end = COALESCE(EXCLUDED.period_end, ingest.artifact.period_end),
  content_type = COALESCE(EXCLUDED.content_type, ingest.artifact.content_type),
  bytes_downloaded = COALESCE(EXCLUDED.bytes_downloaded, ingest.artifact.bytes_downloaded),
  checksum_sha256 = COALESCE(EXCLUDED.checksum_sha256, ingest.artifact.checksum_sha256),
  status = EXCLUDED.status,
  metadata = ingest.artifact.metadata || EXCLUDED.metadata
RETURNING artifact_id, dataset_id, remote_url, local_path, artifact_key, status, checksum_sha256;
