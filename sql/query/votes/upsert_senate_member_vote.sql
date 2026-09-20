-- One senator's vote as the Senate recorded it. Replaces an OpenStates row for the same
-- (roll call, person): the official evidence and the as-recorded party, state, name and LIS id win, and
-- the House-only fields (sort name, unaccented name, role) a replaced row might carry are cleared.
INSERT INTO fact.member_vote (
  roll_call_id, person_id, position, source_artifact_id, position_raw, party_at_vote, state_at_vote,
  name_at_vote, last_name_at_vote, first_name_at_vote, lis_member_id_at_vote
) VALUES (
  %(roll_call_id)s, %(person_id)s, %(position)s, %(source_artifact_id)s, %(position_raw)s, %(party)s,
  %(state)s, %(name)s, %(last_name)s, %(first_name)s, %(lis_member_id)s
)
ON CONFLICT (roll_call_id, person_id) DO UPDATE SET
  position = EXCLUDED.position,
  source_artifact_id = EXCLUDED.source_artifact_id,
  source_payload_id = NULL,
  sort_name_at_vote = NULL,
  unaccented_name_at_vote = NULL,
  role_at_vote = NULL,
  position_raw = EXCLUDED.position_raw,
  party_at_vote = EXCLUDED.party_at_vote,
  state_at_vote = EXCLUDED.state_at_vote,
  name_at_vote = EXCLUDED.name_at_vote,
  last_name_at_vote = EXCLUDED.last_name_at_vote,
  first_name_at_vote = EXCLUDED.first_name_at_vote,
  lis_member_id_at_vote = EXCLUDED.lis_member_id_at_vote;
