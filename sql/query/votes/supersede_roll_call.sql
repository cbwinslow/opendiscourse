-- A refreshed file is a new artifact version. Drop what the older versions loaded for this roll call
-- (their votes and their record), in the caller's transaction, so nothing of the old file survives
-- beside the new one. Votes from other sources (OpenStates) are not touched.
WITH votes AS (
  DELETE FROM fact.member_vote
  WHERE roll_call_id = %(roll_call_id)s AND source_artifact_id = ANY(%(old_artifact_ids)s::uuid[])
  RETURNING 1
), records AS (
  DELETE FROM core.roll_call_source_record
  WHERE roll_call_id = %(roll_call_id)s AND source_artifact_id = ANY(%(old_artifact_ids)s::uuid[])
  RETURNING 1
)
SELECT (SELECT count(*) FROM votes) AS votes, (SELECT count(*) FROM records) AS records;
