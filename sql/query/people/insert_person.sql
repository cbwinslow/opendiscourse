INSERT INTO core.person (full_name, given_name, family_name, metadata)
VALUES (%(full_name)s, %(given_name)s, %(family_name)s, %(metadata)s)
RETURNING person_id
