-- File rows that are gone from this snapshot are not kept as current records.
DELETE FROM core.committee_source_record AS s
WHERE NOT EXISTS (
  SELECT 1
  FROM jsonb_to_recordset(%(rows)s::jsonb) AS r(source_file text, thomas_key text, bioguide text)
  WHERE r.source_file = s.source_file
    AND r.thomas_key = s.thomas_key
    AND r.bioguide = s.bioguide
)
RETURNING 1
