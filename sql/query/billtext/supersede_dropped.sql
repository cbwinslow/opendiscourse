-- After a complete zip refresh, drop older-version records whose members the
-- new archive no longer contains. Rewritten members already moved via the
-- identity upsert. Bound keep list is the current zip's XML names.
DELETE FROM core.bill_text_source_record
WHERE source_artifact_id = ANY(%(old_artifact_ids)s::uuid[])
  AND NOT (source_member = ANY(%(keep_members)s::text[]));
