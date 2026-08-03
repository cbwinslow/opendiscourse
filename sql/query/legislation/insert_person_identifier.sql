INSERT INTO core.person_identifier (person_id, namespace, external_id)
VALUES (%(person_id)s, %(namespace)s, %(external_id)s)
ON CONFLICT (namespace, external_id) DO NOTHING
RETURNING person_id;
