WITH existing AS (
  SELECT person_id FROM core.person_identifier
  WHERE namespace = 'bioguide' AND external_id = %(bioguide_id)s
), inserted AS (
  INSERT INTO core.person (full_name, given_name, family_name, metadata)
  SELECT %(full_name)s, %(given_name)s, %(family_name)s, %(metadata)s
  WHERE NOT EXISTS (SELECT 1 FROM existing)
  RETURNING person_id
), target AS (
  SELECT person_id FROM existing UNION ALL SELECT person_id FROM inserted
), identifier AS (
  INSERT INTO core.person_identifier (person_id, namespace, external_id)
  SELECT person_id, 'bioguide', %(bioguide_id)s FROM target
  ON CONFLICT (namespace, external_id) DO NOTHING
)
SELECT person_id FROM target;
