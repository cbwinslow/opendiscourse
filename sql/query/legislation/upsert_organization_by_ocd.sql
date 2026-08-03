WITH existing AS (
  SELECT organization_id FROM core.organization_identifier
  WHERE namespace = 'ocd' AND external_id = %(ocd_id)s
), inserted AS (
  INSERT INTO core.organization (organization_type, name, jurisdiction_geoid, metadata)
  SELECT %(organization_type)s, %(name)s, 'us', %(metadata)s
  WHERE NOT EXISTS (SELECT 1 FROM existing)
  RETURNING organization_id
), target AS (
  SELECT organization_id FROM existing UNION ALL SELECT organization_id FROM inserted
), identifier AS (
  INSERT INTO core.organization_identifier (organization_id, namespace, external_id)
  SELECT organization_id, 'ocd', %(ocd_id)s FROM target
  ON CONFLICT (namespace, external_id) DO NOTHING
)
SELECT organization_id FROM target;
