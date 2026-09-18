WITH latest AS (
  SELECT artifact_id, dataset_id, remote_url, local_path, artifact_key,
         artifact_version, status, checksum_sha256, metadata
  FROM ingest.artifact
  WHERE dataset_id = %(dataset_id)s::text AND artifact_key = %(artifact_key)s::text
  ORDER BY artifact_version DESC
  LIMIT 1
  FOR UPDATE
),
upd AS (
  UPDATE ingest.artifact a
  SET remote_url = %(remote_url)s::text,
      local_path = %(local_path)s::text,
      period_start = COALESCE(%(period_start)s::date, a.period_start),
      period_end = COALESCE(%(period_end)s::date, a.period_end),
      content_type = COALESCE(%(content_type)s::text, a.content_type),
      bytes_downloaded = COALESCE(%(bytes_downloaded)s::bigint, a.bytes_downloaded),
      checksum_sha256 = COALESCE(%(checksum_sha256)s::text, a.checksum_sha256),
      status = %(status)s::text,
      metadata = a.metadata || COALESCE(%(metadata)s::jsonb, '{}'::jsonb)
  FROM latest l
  WHERE a.artifact_id = l.artifact_id
    AND NOT (%(checksum_sha256)s::text IS NOT NULL AND l.checksum_sha256 IS NOT NULL AND %(checksum_sha256)s::text <> l.checksum_sha256)
    AND NOT (l.checksum_sha256 IS NOT NULL AND l.status IN ('downloaded', 'loaded') AND %(checksum_sha256)s::text IS NULL AND %(status)s::text IN ('planned', 'downloading', 'failed'))
  RETURNING a.artifact_id, a.dataset_id, a.remote_url, a.local_path, a.artifact_key, a.artifact_version, a.status, a.checksum_sha256, a.metadata
),
ins AS (
  INSERT INTO ingest.artifact (
    dataset_id, remote_url, local_path, artifact_key, artifact_version,
    period_start, period_end, content_type, bytes_downloaded, checksum_sha256,
    status, metadata
  )
  SELECT
    %(dataset_id)s::text, %(remote_url)s::text, %(local_path)s::text, %(artifact_key)s::text,
    COALESCE((SELECT artifact_version + 1 FROM latest), 1),
    %(period_start)s::date, %(period_end)s::date, %(content_type)s::text, %(bytes_downloaded)s::bigint, %(checksum_sha256)s::text,
    %(status)s::text, COALESCE(%(metadata)s::jsonb, '{}'::jsonb)
  WHERE NOT EXISTS (SELECT 1 FROM latest)
     OR EXISTS (
       SELECT 1 FROM latest l
       WHERE %(checksum_sha256)s::text IS NOT NULL AND l.checksum_sha256 IS NOT NULL AND %(checksum_sha256)s::text <> l.checksum_sha256
     )
  RETURNING artifact_id, dataset_id, remote_url, local_path, artifact_key, artifact_version, status, checksum_sha256, metadata
)
SELECT artifact_id, dataset_id, remote_url, local_path, artifact_key, artifact_version, status, checksum_sha256, metadata
FROM upd
UNION ALL
SELECT artifact_id, dataset_id, remote_url, local_path, artifact_key, artifact_version, status, checksum_sha256, metadata
FROM ins
UNION ALL
SELECT artifact_id, dataset_id, remote_url, local_path, artifact_key, artifact_version, status, checksum_sha256, metadata
FROM latest
WHERE checksum_sha256 IS NOT NULL
  AND status IN ('downloaded', 'loaded')
  AND %(checksum_sha256)s::text IS NULL
  AND %(status)s::text IN ('planned', 'downloading', 'failed');
