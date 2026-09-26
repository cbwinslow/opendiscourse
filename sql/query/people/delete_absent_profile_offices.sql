DELETE FROM core.district_office AS o
WHERE NOT EXISTS (
  SELECT 1 FROM profile_office AS s WHERE s.office_key = o.office_key
)
RETURNING 1
