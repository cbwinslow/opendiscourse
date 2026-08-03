INSERT INTO core.document (document_type, source_key, title, published_at, canonical_url, artifact_id, source_payload_id, metadata)
VALUES (%(document_type)s, %(source_key)s, %(title)s, %(published_at)s, %(canonical_url)s, %(artifact_id)s, %(source_payload_id)s, %(metadata)s)
ON CONFLICT (document_type, source_key) DO UPDATE SET
  title = COALESCE(EXCLUDED.title, core.document.title),
  published_at = COALESCE(EXCLUDED.published_at, core.document.published_at),
  metadata = core.document.metadata || EXCLUDED.metadata
RETURNING document_id;
