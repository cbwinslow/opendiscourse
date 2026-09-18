WITH reconciled AS (
  UPDATE core.membership AS cm
  SET ocd_id = m.id,
      source_artifact_id = %(source_artifact_id)s::uuid,
      metadata = cm.metadata || jsonb_build_object(
        'canonical_baseline', 'openstates',
        'openstates_ocd_id', m.id
      )
  FROM openstates_source.opencivicdata_membership AS m
  JOIN openstates_source.opencivicdata_organization AS o
    ON o.id = m.organization_id
  JOIN core.organization_identifier AS oi
    ON oi.namespace = 'ocd' AND oi.external_id = m.organization_id
  JOIN core.person_identifier AS pi
    ON pi.namespace = 'ocd' AND pi.external_id = m.person_id
  LEFT JOIN core.post AS po
    ON po.ocd_id = m.post_id
  WHERE o.jurisdiction_id = %(jurisdiction_id)s
    AND m.person_id IS NOT NULL
    AND (
      m.post_id IS NULL
      OR (po.post_id IS NOT NULL AND po.organization_id = oi.organization_id)
    )
    AND cm.ocd_id IS NULL
    AND cm.person_id = pi.person_id
    AND cm.organization_id = oi.organization_id
    AND (cm.post_id IS NOT DISTINCT FROM po.post_id OR cm.post_id IS NULL)
    AND cm.start_date IS NOT DISTINCT FROM (
      CASE
        WHEN m.start_date ~ '^\d{4}-\d{2}-\d{2}$' THEN m.start_date::date
        ELSE NULL
      END
    )
  RETURNING cm.membership_id
)
SELECT count(*)::int AS n FROM reconciled;
