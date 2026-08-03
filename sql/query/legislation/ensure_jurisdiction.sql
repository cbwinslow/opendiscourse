INSERT INTO core.jurisdiction (jurisdiction_id, name, classification, metadata)
VALUES (%(jurisdiction_id)s, %(name)s, %(classification)s, %(metadata)s)
ON CONFLICT (jurisdiction_id) DO UPDATE SET
  name = EXCLUDED.name,
  classification = EXCLUDED.classification,
  metadata = core.jurisdiction.metadata || EXCLUDED.metadata;
