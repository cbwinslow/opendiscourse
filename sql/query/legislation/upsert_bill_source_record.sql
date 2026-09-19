-- One row per BILLSTATUS file: the whole record, keyed by artifact and member. A row here
-- marks the member as fully loaded (it is written last, in the same transaction as the rest).
INSERT INTO core.bill_source_record (bill_id, source_artifact_id, source_member, record, record_sha256)
VALUES (%(bill_id)s, %(source_artifact_id)s, %(source_member)s, %(record)s, %(record_sha256)s)
ON CONFLICT (source_artifact_id, source_member) DO UPDATE SET
  bill_id = EXCLUDED.bill_id,
  record = EXCLUDED.record,
  record_sha256 = EXCLUDED.record_sha256,
  loaded_at = now();
