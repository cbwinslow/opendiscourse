DELETE FROM core.person_leadership AS l
WHERE NOT EXISTS (
  SELECT 1
  FROM profile_leadership AS s
  WHERE s.bioguide = l.bioguide
    AND s.chamber = l.chamber
    AND s.title = l.title
    AND s.start_date = l.start_date
)
RETURNING 1
