WITH latest AS (
  SELECT a.* FROM ingest.artifact a
  WHERE a.dataset_id=%(dataset_id)s::text AND a.artifact_key=%(artifact_key)s::text
  ORDER BY a.artifact_version DESC LIMIT 1 FOR UPDATE
), promote AS (
  UPDATE ingest.artifact a SET remote_url=%(remote_url)s::text, local_path=%(local_path)s::text,
    period_start=%(period_start)s::date, period_end=%(period_end)s::date,
    content_type=COALESCE(%(content_type)s::text,a.content_type), bytes_downloaded=%(bytes_downloaded)s::bigint,
    checksum_sha256=%(checksum_sha256)s::text, status=%(status)s::text,
    error_message=%(error_message)s::text,
    downloaded_at=CASE WHEN %(status)s::text='downloaded' THEN now() ELSE a.downloaded_at END,
    metadata=a.metadata || COALESCE(%(metadata)s::jsonb,'{}'::jsonb)
  FROM latest l WHERE a.artifact_id=l.artifact_id AND %(action)s::text='promote' RETURNING a.*
), retry AS (
  UPDATE ingest.artifact a SET remote_url=%(remote_url)s::text, status=%(status)s::text,
    error_message=%(error_message)s::text,
    downloaded_at=CASE WHEN %(status)s::text='downloaded' THEN now() ELSE a.downloaded_at END,
    metadata=a.metadata || COALESCE(%(metadata)s::jsonb,'{}'::jsonb)
  FROM latest l WHERE a.artifact_id=l.artifact_id AND %(action)s::text='retry' RETURNING a.*
), append_version AS (
  INSERT INTO ingest.artifact(dataset_id,remote_url,local_path,artifact_key,artifact_version,period_start,period_end,content_type,bytes_downloaded,checksum_sha256,status,error_message,downloaded_at,metadata)
  SELECT %(dataset_id)s::text,%(remote_url)s::text,%(local_path)s::text,%(artifact_key)s::text,
    COALESCE((SELECT artifact_version+1 FROM latest),1),%(period_start)s::date,%(period_end)s::date,%(content_type)s::text,%(bytes_downloaded)s::bigint,%(checksum_sha256)s::text,%(status)s::text,%(error_message)s::text,CASE WHEN %(status)s::text='downloaded' THEN now() END,COALESCE(%(metadata)s::jsonb,'{}'::jsonb)
  WHERE %(action)s::text='append'
  RETURNING *
)
SELECT artifact_id,dataset_id,remote_url,local_path,artifact_key,artifact_version,status,checksum_sha256,metadata FROM promote
UNION ALL SELECT artifact_id,dataset_id,remote_url,local_path,artifact_key,artifact_version,status,checksum_sha256,metadata FROM retry
UNION ALL SELECT artifact_id,dataset_id,remote_url,local_path,artifact_key,artifact_version,status,checksum_sha256,metadata FROM append_version;
