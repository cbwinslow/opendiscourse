-- An official roll-call file that identifies every member is the whole roll, so a stored vote that
-- did not come from it is another provider's leftover. A roll whose file lists nobody, or has a
-- member we could not identify, is left alone: the other row may be the only record of that vote.
-- roll_call_ids NULL means every stored roll call.
DELETE FROM fact.member_vote v
USING (
  SELECT roll_call_id, array_agg(source_artifact_id) AS artifacts
  FROM core.roll_call_source_record
  WHERE %(roll_call_ids)s::uuid[] IS NULL OR roll_call_id = ANY(%(roll_call_ids)s::uuid[])
  GROUP BY roll_call_id
  HAVING bool_and(entry_count > 0 AND entries_without_id = 0 AND cardinality(unresolved_bioguide_ids) = 0)
) official
WHERE v.roll_call_id = official.roll_call_id
  AND (v.source_artifact_id IS NULL OR NOT v.source_artifact_id = ANY(official.artifacts));
