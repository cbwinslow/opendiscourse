-- A refreshed BILLS zip is a new artifact version. Drop the older version's records
-- for exactly the members the new version just rewrote, in the same transaction.
DELETE FROM core.bill_text_source_record
WHERE source_artifact_id = ANY(%(old_artifact_ids)s::uuid[])
  AND source_member = ANY(%(source_members)s::text[]);
