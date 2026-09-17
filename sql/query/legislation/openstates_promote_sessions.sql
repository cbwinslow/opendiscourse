WITH upserted AS (
  INSERT INTO core.legislative_session (
    jurisdiction_id, identifier, name, classification, starts_on, ends_on,
    active, source_artifact_id, metadata
  )
  SELECT
    s.jurisdiction_id,
    s.identifier,
    NULLIF(btrim(s.name), ''),
    NULLIF(btrim(s.classification), ''),
    CASE
      WHEN s.start_date ~ '^\d{4}-\d{2}-\d{2}$' THEN s.start_date::date
      ELSE NULL
    END,
    CASE
      WHEN s.end_date ~ '^\d{4}-\d{2}-\d{2}$' THEN s.end_date::date
      ELSE NULL
    END,
    s.active,
    %(source_artifact_id)s::uuid,
    jsonb_strip_nulls(
      jsonb_build_object(
        'canonical_baseline', 'openstates',
        'openstates_session_id', s.id,
        'congress', CASE WHEN s.identifier ~ '^\d+$' THEN s.identifier::int ELSE NULL END
      )
    )
  FROM openstates_source.opencivicdata_legislativesession AS s
  WHERE s.jurisdiction_id = %(jurisdiction_id)s
  ON CONFLICT (jurisdiction_id, identifier) DO UPDATE SET
    name = COALESCE(EXCLUDED.name, core.legislative_session.name),
    classification = COALESCE(EXCLUDED.classification, core.legislative_session.classification),
    starts_on = COALESCE(EXCLUDED.starts_on, core.legislative_session.starts_on),
    ends_on = COALESCE(EXCLUDED.ends_on, core.legislative_session.ends_on),
    active = COALESCE(EXCLUDED.active, core.legislative_session.active),
    source_artifact_id = EXCLUDED.source_artifact_id,
    metadata = core.legislative_session.metadata || EXCLUDED.metadata
  RETURNING legislative_session_id
)
SELECT count(*)::int AS n FROM upserted;
