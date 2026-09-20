-- Rolls whose official totals differ from the typed member votes now stored. OpenStates rows can
-- lack members the official file has; both are reported, never hidden. Only rolls with official
-- yea and nay totals are compared (elections tally candidates instead). Yes, no and not voting are
-- compared; present is not, because 'other' also holds any word that is not a plain yes or no.
SELECT rc.roll_call_id, rc.external_id, rc.yea_total, rc.nay_total, rc.not_voting_total,
       count(*) FILTER (WHERE mv.position = 'yes') AS yes_votes,
       count(*) FILTER (WHERE mv.position = 'no') AS no_votes,
       count(*) FILTER (WHERE mv.position = 'not voting') AS not_voting_votes
FROM core.roll_call rc
LEFT JOIN fact.member_vote mv ON mv.roll_call_id = rc.roll_call_id
WHERE rc.roll_call_id = ANY(%(roll_call_ids)s::uuid[])
  AND rc.yea_total IS NOT NULL AND rc.nay_total IS NOT NULL
GROUP BY rc.roll_call_id, rc.external_id, rc.yea_total, rc.nay_total, rc.not_voting_total
HAVING count(*) FILTER (WHERE mv.position = 'yes') <> rc.yea_total
    OR count(*) FILTER (WHERE mv.position = 'no') <> rc.nay_total
    OR (rc.not_voting_total IS NOT NULL
        AND count(*) FILTER (WHERE mv.position = 'not voting') <> rc.not_voting_total)
ORDER BY rc.external_id;
