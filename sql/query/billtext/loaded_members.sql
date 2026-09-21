-- Members of one artifact version that are fully loaded *and* attached to a bill.
-- A row with bill_id NULL is stored evidence for an unknown bill; it stays in the
-- resume todo so a later sync can set bill_id and write the document link.
SELECT source_member
FROM core.bill_text_source_record
WHERE source_artifact_id = %(artifact_id)s
  AND bill_id IS NOT NULL;
