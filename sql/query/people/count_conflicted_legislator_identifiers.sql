-- Staged identifiers of groups that wrote nothing because they conflict.
SELECT count(*) AS skipped
FROM legislator_stage s
JOIN legislator_group g USING (bioguide)
WHERE g.outcome IN ('multiple_owners', 'bioguide_mismatch')
