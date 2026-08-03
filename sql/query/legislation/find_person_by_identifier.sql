SELECT person_id
FROM core.person_identifier
WHERE namespace = %(namespace)s AND external_id = %(external_id)s
LIMIT 1;
