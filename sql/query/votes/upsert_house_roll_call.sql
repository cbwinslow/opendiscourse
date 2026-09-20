-- One official House roll call. A row OpenStates already created under the same key
-- (us-<year>-lower-<number>) is enriched in place: same roll_call_id, official fields added,
-- and the official time and question replace the provider's, and so does the result (NULL when the
-- official word is not a plain pass or fail: a stale provider pass/fail must not sit beside it). A new key inserts.
-- `inserted` tells the two apart; `openstates` says whether the enriched row came from OpenStates.
INSERT INTO core.roll_call (
  jurisdiction, legislative_session, chamber, external_id, occurred_at, question, result, metadata,
  organization_id, legislative_session_id, roll_number, roll_year, congress_session, legislative_number,
  vote_type, vote_result, majority_party, vote_description, amendment_number, amendment_author,
  action_date, action_time_etz, yea_total, nay_total, present_total, not_voting_total, source_artifact_id
) VALUES (
  'us', %(congress)s, 'house', %(external_id)s, %(occurred_at)s, %(question)s, %(result)s, %(metadata)s,
  %(organization_id)s, %(legislative_session_id)s, %(roll_number)s, %(roll_year)s, %(congress_session)s,
  %(legislative_number)s, %(vote_type)s, %(vote_result)s, %(majority_party)s, %(vote_description)s,
  %(amendment_number)s, %(amendment_author)s, %(action_date)s, %(action_time_etz)s, %(yea_total)s,
  %(nay_total)s, %(present_total)s, %(not_voting_total)s, %(source_artifact_id)s
)
ON CONFLICT (jurisdiction, legislative_session, external_id) DO UPDATE SET
  occurred_at = COALESCE(EXCLUDED.occurred_at, core.roll_call.occurred_at),
  question = COALESCE(EXCLUDED.question, core.roll_call.question),
  result = EXCLUDED.result,
  organization_id = COALESCE(core.roll_call.organization_id, EXCLUDED.organization_id),
  legislative_session_id = COALESCE(core.roll_call.legislative_session_id, EXCLUDED.legislative_session_id),
  roll_number = EXCLUDED.roll_number,
  roll_year = EXCLUDED.roll_year,
  congress_session = EXCLUDED.congress_session,
  legislative_number = EXCLUDED.legislative_number,
  vote_type = EXCLUDED.vote_type,
  vote_result = EXCLUDED.vote_result,
  majority_party = EXCLUDED.majority_party,
  vote_description = EXCLUDED.vote_description,
  amendment_number = EXCLUDED.amendment_number,
  amendment_author = EXCLUDED.amendment_author,
  action_date = EXCLUDED.action_date,
  action_time_etz = EXCLUDED.action_time_etz,
  yea_total = EXCLUDED.yea_total,
  nay_total = EXCLUDED.nay_total,
  present_total = EXCLUDED.present_total,
  not_voting_total = EXCLUDED.not_voting_total,
  source_artifact_id = EXCLUDED.source_artifact_id
RETURNING roll_call_id, (xmax = 0) AS inserted, (metadata->>'source' = 'openstates') AS openstates;
