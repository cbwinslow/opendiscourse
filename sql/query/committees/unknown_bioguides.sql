SELECT DISTINCT bioguide
FROM core.committee_assignment
WHERE person_id IS NULL
ORDER BY bioguide
