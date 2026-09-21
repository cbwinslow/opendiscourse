-- One row per BILLS version identity. A later zip replaces a fallback-XML row for
-- the same congress/session/type/number/version; attaching a previously unknown
-- bill updates bill_id in place. bill_id is NULL when we do not hold the bill
-- (BILLSTATUS is the parent; we never invent one).
INSERT INTO core.bill_text_source_record (
  bill_id, source_artifact_id, source_member,
  congress, session, bill_type, bill_number, version_code,
  record, record_sha256
) VALUES (
  %(bill_id)s, %(source_artifact_id)s, %(source_member)s,
  %(congress)s, %(session)s, %(bill_type)s, %(bill_number)s, %(version_code)s,
  %(record)s, %(record_sha256)s
)
ON CONFLICT (congress, session, bill_type, bill_number, version_code) DO UPDATE SET
  bill_id = EXCLUDED.bill_id,
  source_artifact_id = EXCLUDED.source_artifact_id,
  source_member = EXCLUDED.source_member,
  record = EXCLUDED.record,
  record_sha256 = EXCLUDED.record_sha256,
  loaded_at = now();
