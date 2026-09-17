WITH upserted AS (
  INSERT INTO core.post (
    organization_id, division_id, ocd_id, label, role, source_artifact_id, metadata
  )
  SELECT
    oi.organization_id,
    div.division_id,
    p.id,
    p.label,
    NULLIF(btrim(p.role), ''),
    %(source_artifact_id)s::uuid,
    jsonb_build_object(
      'canonical_baseline', 'openstates',
      'openstates_ocd_id', p.id
    )
  FROM openstates_source.opencivicdata_post AS p
  JOIN openstates_source.opencivicdata_organization AS o
    ON o.id = p.organization_id
  JOIN core.organization_identifier AS oi
    ON oi.namespace = 'ocd' AND oi.external_id = p.organization_id
  LEFT JOIN core.division AS div
    ON div.ocd_division_id = p.division_id
  WHERE o.jurisdiction_id = %(jurisdiction_id)s
  ON CONFLICT (ocd_id) WHERE ocd_id IS NOT NULL DO UPDATE SET
    organization_id = EXCLUDED.organization_id,
    division_id = EXCLUDED.division_id,
    label = EXCLUDED.label,
    role = COALESCE(EXCLUDED.role, core.post.role),
    source_artifact_id = COALESCE(core.post.source_artifact_id, EXCLUDED.source_artifact_id),
    metadata = core.post.metadata || EXCLUDED.metadata
  RETURNING post_id
)
SELECT count(*)::int AS n FROM upserted;
