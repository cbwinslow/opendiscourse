-- Birthday and gender follow the member file. A blank value clears the column.
UPDATE core.person AS p
SET birthday = s.birthday,
    gender = s.gender
FROM profile_person AS s
JOIN core.person_identifier AS pi
  ON pi.namespace = 'bioguide' AND pi.external_id = s.bioguide
WHERE p.person_id = pi.person_id
  AND (p.birthday, p.gender) IS DISTINCT FROM (s.birthday, s.gender)
RETURNING 1
