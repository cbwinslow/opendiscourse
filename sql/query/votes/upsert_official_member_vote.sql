-- One member's vote as the Clerk recorded it. Replaces an OpenStates row for the same
-- (roll call, person): the official evidence and the as-recorded party, state and name win.
INSERT INTO fact.member_vote (
  roll_call_id, person_id, position, source_artifact_id, position_raw, party_at_vote, state_at_vote,
  name_at_vote, sort_name_at_vote, unaccented_name_at_vote, role_at_vote
) VALUES (
  %(roll_call_id)s, %(person_id)s, %(position)s, %(source_artifact_id)s, %(position_raw)s, %(party)s,
  %(state)s, %(name)s, %(sort_name)s, %(unaccented_name)s, %(role)s
)
ON CONFLICT (roll_call_id, person_id) DO UPDATE SET
  position = EXCLUDED.position,
  source_artifact_id = EXCLUDED.source_artifact_id,
  source_payload_id = NULL,
  position_raw = EXCLUDED.position_raw,
  party_at_vote = EXCLUDED.party_at_vote,
  state_at_vote = EXCLUDED.state_at_vote,
  name_at_vote = EXCLUDED.name_at_vote,
  sort_name_at_vote = EXCLUDED.sort_name_at_vote,
  unaccented_name_at_vote = EXCLUDED.unaccented_name_at_vote,
  role_at_vote = EXCLUDED.role_at_vote;
