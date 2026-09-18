WITH upserted AS (
  INSERT INTO core.membership (
    person_id, organization_id, post_id, ocd_id, role, start_date, end_date,
    source_artifact_id, metadata
  )
  SELECT
    pi.person_id,
    oi.organization_id,
    po.post_id,
    m.id,
    m.role,
    CASE
      WHEN m.start_date ~ '^\d{4}-\d{2}-\d{2}$' THEN m.start_date::date
      ELSE NULL
    END,
    CASE
      WHEN m.end_date ~ '^\d{4}-\d{2}-\d{2}$' THEN m.end_date::date
      ELSE NULL
    END,
    %(source_artifact_id)s::uuid,
    jsonb_build_object(
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
  ON CONFLICT (ocd_id) WHERE ocd_id IS NOT NULL DO UPDATE SET
    person_id = EXCLUDED.person_id,
    organization_id = EXCLUDED.organization_id,
    post_id = EXCLUDED.post_id,
    role = EXCLUDED.role,
    start_date = COALESCE(EXCLUDED.start_date, core.membership.start_date),
    end_date = COALESCE(EXCLUDED.end_date, core.membership.end_date),
    source_artifact_id = EXCLUDED.source_artifact_id,
    metadata = core.membership.metadata || EXCLUDED.metadata
  RETURNING membership_id
)
SELECT count(*)::int AS n FROM upserted;
