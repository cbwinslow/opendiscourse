-- One row per roll-call file: the whole record. Written last in the roll call's transaction,
-- so its presence means the roll call is fully loaded. unresolved_bioguide_ids lists members the
-- file names that the warehouse does not know yet; a rerun tries them again.
INSERT INTO core.roll_call_source_record (
  roll_call_id, source_artifact_id, record, record_sha256, entry_count, typed_count, entries_without_id,
  unresolved_bioguide_ids
) VALUES (
  %(roll_call_id)s, %(source_artifact_id)s, %(record)s, %(record_sha256)s, %(entry_count)s, %(typed_count)s,
  %(entries_without_id)s, %(unresolved_bioguide_ids)s
)
ON CONFLICT (source_artifact_id) DO UPDATE SET
  roll_call_id = EXCLUDED.roll_call_id,
  record = EXCLUDED.record,
  record_sha256 = EXCLUDED.record_sha256,
  entry_count = EXCLUDED.entry_count,
  typed_count = EXCLUDED.typed_count,
  entries_without_id = EXCLUDED.entries_without_id,
  unresolved_bioguide_ids = EXCLUDED.unresolved_bioguide_ids,
  loaded_at = now();
