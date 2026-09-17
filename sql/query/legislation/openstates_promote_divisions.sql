WITH upserted AS (
  INSERT INTO core.division (
    ocd_division_id, label, classification, source_artifact_id, metadata
  )
  SELECT DISTINCT
    d.id,
    d.name,
    COALESCE(NULLIF(btrim(d.subtype1), ''), 'division'),
    %(source_artifact_id)s::uuid,
    jsonb_build_object('canonical_baseline', 'openstates')
  FROM openstates_source.opencivicdata_division AS d
  JOIN openstates_source.opencivicdata_post AS p
    ON p.division_id = d.id
  JOIN openstates_source.opencivicdata_organization AS o
    ON o.id = p.organization_id
  JOIN core.organization_identifier AS oi
    ON oi.namespace = 'ocd' AND oi.external_id = o.id
  WHERE o.jurisdiction_id = %(jurisdiction_id)s
  ON CONFLICT (ocd_division_id) WHERE ocd_division_id IS NOT NULL DO UPDATE SET
    label = EXCLUDED.label,
    classification = EXCLUDED.classification,
    source_artifact_id = EXCLUDED.source_artifact_id,
    metadata = core.division.metadata || EXCLUDED.metadata
  RETURNING division_id
)
SELECT count(*)::int AS n FROM upserted;
