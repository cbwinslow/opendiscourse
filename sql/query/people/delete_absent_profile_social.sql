DELETE FROM core.person_social_account AS a
WHERE NOT EXISTS (
  SELECT 1
  FROM profile_social AS s
  WHERE s.bioguide = a.bioguide AND s.network = a.network
)
RETURNING 1
