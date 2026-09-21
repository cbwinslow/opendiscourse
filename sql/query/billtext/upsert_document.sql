-- Typed version identity plus a pointer to the retained zip (or fallback XML) bytes.
INSERT INTO core.document (
  document_type, source_key, title, published_at, canonical_url, checksum_sha256,
  artifact_id, version_code, congress, session, bill_type, bill_number, source_member, metadata
) VALUES (
  %(document_type)s, %(source_key)s, %(title)s, %(published_at)s, %(canonical_url)s, %(checksum_sha256)s,
  %(artifact_id)s, %(version_code)s, %(congress)s, %(session)s, %(bill_type)s, %(bill_number)s,
  %(source_member)s, %(metadata)s
)
ON CONFLICT (document_type, source_key) DO UPDATE SET
  title = COALESCE(EXCLUDED.title, core.document.title),
  published_at = COALESCE(EXCLUDED.published_at, core.document.published_at),
  canonical_url = COALESCE(EXCLUDED.canonical_url, core.document.canonical_url),
  checksum_sha256 = COALESCE(EXCLUDED.checksum_sha256, core.document.checksum_sha256),
  artifact_id = EXCLUDED.artifact_id,
  version_code = EXCLUDED.version_code,
  congress = EXCLUDED.congress,
  session = EXCLUDED.session,
  bill_type = EXCLUDED.bill_type,
  bill_number = EXCLUDED.bill_number,
  source_member = EXCLUDED.source_member,
  metadata = core.document.metadata || EXCLUDED.metadata
RETURNING document_id;
