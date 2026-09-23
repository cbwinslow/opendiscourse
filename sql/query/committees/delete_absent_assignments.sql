-- Someone who left the current file is removed. The committee stays.
DELETE FROM core.committee_assignment AS a
WHERE NOT EXISTS (
  SELECT 1
  FROM jsonb_to_recordset(%(rows)s::jsonb) AS r(thomas_key text, bioguide text)
  JOIN core.committee c ON c.thomas_key = r.thomas_key
  WHERE c.committee_id = a.committee_id AND a.bioguide = r.bioguide
)
RETURNING 1
