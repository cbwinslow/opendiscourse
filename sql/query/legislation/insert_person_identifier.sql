INSERT INTO core.person_identifier (person_id, namespace, external_id)
VALUES (%(person_id)s, %(namespace)s, %(external_id)s)
ON CONFLICT (namespace, external_id) DO UPDATE
SET external_id = core.person_identifier.external_id
RETURNING person_id;
