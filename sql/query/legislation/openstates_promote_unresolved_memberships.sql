WITH unresolved AS (
  SELECT
    COALESCE(m.person_id, m.id) AS external_id,
    CASE
      WHEN m.person_id IS NULL THEN 'missing_ocd_person_id'
      ELSE 'no_canonical_person_identifier'
    END AS reason,
    count(*)::int AS reference_count
  FROM openstates_source.opencivicdata_membership AS m
  JOIN openstates_source.opencivicdata_organization AS o
    ON o.id = m.organization_id
  WHERE o.jurisdiction_id = %(jurisdiction_id)s
    AND (
      m.person_id IS NULL
      OR NOT EXISTS (
        SELECT 1
        FROM core.person_identifier AS pi
        WHERE pi.namespace = 'ocd' AND pi.external_id = m.person_id
      )
    )
  GROUP BY
    COALESCE(m.person_id, m.id),
    CASE
      WHEN m.person_id IS NULL THEN 'missing_ocd_person_id'
      ELSE 'no_canonical_person_identifier'
    END
), upserted AS (
  INSERT INTO ingest.identity_exception (
    dataset_id, run_id, source_artifact_id, congress, kind, namespace,
    external_id, reason, reference_count
  )
  SELECT
    'openstates.legislation',
    %(run_id)s::uuid,
    %(source_artifact_id)s::uuid,
    0,
    'membership',
    'ocd',
    unresolved.external_id,
    unresolved.reason,
    unresolved.reference_count
  FROM unresolved
  ON CONFLICT (run_id, kind, namespace, external_id, reason) DO UPDATE SET
    reference_count = ingest.identity_exception.reference_count + EXCLUDED.reference_count,
    last_seen_at = now()
  RETURNING identity_exception_id
)
SELECT count(*)::int AS n FROM upserted;
