-- A provider's copy of a vote (OpenStates). The official roll-call file wins: nothing is added to a
-- roll call whose file identifies every member, and a vote that came from the file is never changed.
INSERT INTO fact.member_vote (
  roll_call_id, person_id, position, source_artifact_id
)
SELECT %(roll_call_id)s::uuid, %(person_id)s::uuid, %(position)s::text, %(source_artifact_id)s::uuid
WHERE NOT EXISTS (
  SELECT 1 FROM core.roll_call_source_record s
  WHERE s.roll_call_id = %(roll_call_id)s::uuid
    AND s.entry_count > 0 AND s.entries_without_id = 0 AND cardinality(s.unresolved_bioguide_ids) = 0
)
ON CONFLICT (roll_call_id, person_id) DO UPDATE SET
  position = EXCLUDED.position,
  source_artifact_id = COALESCE(EXCLUDED.source_artifact_id, fact.member_vote.source_artifact_id)
WHERE NOT EXISTS (
  SELECT 1 FROM core.roll_call_source_record s
  WHERE s.roll_call_id = fact.member_vote.roll_call_id
    AND s.source_artifact_id = fact.member_vote.source_artifact_id
);
