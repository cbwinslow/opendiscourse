-- Members of one artifact version that are fully loaded: they have their record row, which is
-- written last in the batch transaction. Bills loaded before Story 9.5b have none yet.
SELECT source_member
FROM core.bill_source_record
WHERE source_artifact_id = %(artifact_id)s;
