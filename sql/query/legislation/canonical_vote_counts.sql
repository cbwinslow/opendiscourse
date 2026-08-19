SELECT
  rc.legislative_session AS congress,
  count(DISTINCT rc.roll_call_id) AS canonical_roll_calls,
  count(mv.person_id) AS canonical_member_votes
FROM core.roll_call rc
LEFT JOIN fact.member_vote mv ON mv.roll_call_id = rc.roll_call_id
WHERE rc.legislative_session = ANY(%(congresses)s)
GROUP BY rc.legislative_session
ORDER BY rc.legislative_session;
