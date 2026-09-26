SELECT bioguide, 'social' AS source
FROM profile_social AS s
WHERE NOT EXISTS (
  SELECT 1 FROM core.person_identifier AS pi
  WHERE pi.namespace = 'bioguide' AND pi.external_id = s.bioguide
)
UNION
SELECT bioguide, 'office' AS source
FROM profile_office AS o
WHERE NOT EXISTS (
  SELECT 1 FROM core.person_identifier AS pi
  WHERE pi.namespace = 'bioguide' AND pi.external_id = o.bioguide
)
ORDER BY 1, 2
