-- Drop bodies the files no longer contain. Assignments go with them.
DELETE FROM core.committee
WHERE NOT (thomas_key = ANY(%(keys)s::text[]))
RETURNING 1
