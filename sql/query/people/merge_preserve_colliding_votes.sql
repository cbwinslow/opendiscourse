-- Votes the duplicate cast on a roll call the survivor also voted on. Kept whole in the
-- audit table, then removed so the survivor's own vote stands.
WITH kept AS (
  INSERT INTO ingest.person_merge_vote (person_merge_id, roll_call_id, vote)
  SELECT %(merge_id)s, d.roll_call_id, to_jsonb(d)
  FROM fact.member_vote d
  JOIN fact.member_vote s ON s.roll_call_id = d.roll_call_id AND s.person_id = %(survivor)s
  WHERE d.person_id = %(duplicate)s
  RETURNING roll_call_id
)
DELETE FROM fact.member_vote v
USING kept
WHERE v.person_id = %(duplicate)s AND v.roll_call_id = kept.roll_call_id
