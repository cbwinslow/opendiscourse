-- People this snapshot actually linked, for roster assertions. No name matching.
SELECT a.person_id::text AS person_id, a.bioguide, a.stated_name
FROM core.committee_assignment a
WHERE a.person_id IS NOT NULL
ORDER BY a.person_id::text, a.bioguide
