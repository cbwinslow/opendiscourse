-- One official Senate roll call. A row OpenStates already created under the same key
-- (us-<year>-upper-<number>) is enriched in place: same roll_call_id, official fields added,
-- and the official time and question replace the provider's, and so does the result (NULL when the
-- official word is not a plain pass or fail: a stale provider pass/fail must not sit beside it). A new key inserts.
-- `inserted` tells the two apart; `openstates` says whether the enriched row came from OpenStates.
-- The bill link is set only when the document names a bill core.bill holds (by Congress, type and
-- number, never by title); a link already made is never removed by a file that cannot make it.
INSERT INTO core.roll_call (
  jurisdiction, legislative_session, chamber, external_id, occurred_at, question, result, metadata,
  organization_id, legislative_session_id, roll_number, roll_year, congress_session, vote_result,
  action_date, action_time_etz, yea_total, nay_total, present_total, not_voting_total, source_artifact_id,
  vote_question_text, vote_document_text, vote_result_text, vote_title, majority_requirement, modified_at,
  document_congress, document_type, document_number, document_name, document_title, document_short_title,
  amendment_number, amendment_to_amendment_number, amendment_to_amendment_to_amendment_number,
  amendment_to_document_number, amendment_to_document_short_title, amendment_purpose,
  tie_breaker_by, tie_breaker_vote, bill_id
) VALUES (
  'us', %(congress)s, 'senate', %(external_id)s, %(occurred_at)s, %(question)s, %(result)s, %(metadata)s,
  %(organization_id)s, %(legislative_session_id)s, %(roll_number)s, %(roll_year)s, %(congress_session)s,
  %(vote_result)s, %(action_date)s, %(action_time_etz)s, %(yea_total)s, %(nay_total)s, %(present_total)s,
  %(not_voting_total)s, %(source_artifact_id)s,
  %(vote_question_text)s, %(vote_document_text)s, %(vote_result_text)s, %(vote_title)s,
  %(majority_requirement)s, %(modified_at)s,
  %(document_congress)s, %(document_type)s, %(document_number)s, %(document_name)s, %(document_title)s,
  %(document_short_title)s, %(amendment_number)s, %(amendment_to_amendment_number)s,
  %(amendment_to_amendment_to_amendment_number)s, %(amendment_to_document_number)s,
  %(amendment_to_document_short_title)s, %(amendment_purpose)s, %(tie_breaker_by)s, %(tie_breaker_vote)s,
  (SELECT b.bill_id FROM core.bill b
   WHERE b.jurisdiction = 'us' AND b.legislative_session = %(link_congress)s::text
     AND b.bill_type = %(link_bill_type)s AND b.bill_number = %(link_bill_number)s)
)
ON CONFLICT (jurisdiction, legislative_session, external_id) DO UPDATE SET
  occurred_at = COALESCE(EXCLUDED.occurred_at, core.roll_call.occurred_at),
  question = COALESCE(EXCLUDED.question, core.roll_call.question),
  result = EXCLUDED.result,
  organization_id = COALESCE(core.roll_call.organization_id, EXCLUDED.organization_id),
  legislative_session_id = COALESCE(core.roll_call.legislative_session_id, EXCLUDED.legislative_session_id),
  bill_id = COALESCE(EXCLUDED.bill_id, core.roll_call.bill_id),
  roll_number = EXCLUDED.roll_number,
  roll_year = EXCLUDED.roll_year,
  congress_session = EXCLUDED.congress_session,
  vote_result = EXCLUDED.vote_result,
  action_date = EXCLUDED.action_date,
  action_time_etz = EXCLUDED.action_time_etz,
  yea_total = EXCLUDED.yea_total,
  nay_total = EXCLUDED.nay_total,
  present_total = EXCLUDED.present_total,
  not_voting_total = EXCLUDED.not_voting_total,
  source_artifact_id = EXCLUDED.source_artifact_id,
  vote_question_text = EXCLUDED.vote_question_text,
  vote_document_text = EXCLUDED.vote_document_text,
  vote_result_text = EXCLUDED.vote_result_text,
  vote_title = EXCLUDED.vote_title,
  majority_requirement = EXCLUDED.majority_requirement,
  modified_at = EXCLUDED.modified_at,
  document_congress = EXCLUDED.document_congress,
  document_type = EXCLUDED.document_type,
  document_number = EXCLUDED.document_number,
  document_name = EXCLUDED.document_name,
  document_title = EXCLUDED.document_title,
  document_short_title = EXCLUDED.document_short_title,
  amendment_number = EXCLUDED.amendment_number,
  amendment_to_amendment_number = EXCLUDED.amendment_to_amendment_number,
  amendment_to_amendment_to_amendment_number = EXCLUDED.amendment_to_amendment_to_amendment_number,
  amendment_to_document_number = EXCLUDED.amendment_to_document_number,
  amendment_to_document_short_title = EXCLUDED.amendment_to_document_short_title,
  amendment_purpose = EXCLUDED.amendment_purpose,
  tie_breaker_by = EXCLUDED.tie_breaker_by,
  tie_breaker_vote = EXCLUDED.tie_breaker_vote
RETURNING roll_call_id, (xmax = 0) AS inserted, (metadata->>'source' = 'openstates') AS openstates;
