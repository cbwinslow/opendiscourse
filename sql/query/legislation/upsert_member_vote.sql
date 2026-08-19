INSERT INTO fact.member_vote (
  roll_call_id, person_id, position, source_artifact_id
) VALUES (
  %(roll_call_id)s, %(person_id)s, %(position)s, %(source_artifact_id)s
)
ON CONFLICT (roll_call_id, person_id) DO UPDATE SET
  position = EXCLUDED.position,
  source_artifact_id = COALESCE(EXCLUDED.source_artifact_id, fact.member_vote.source_artifact_id);
