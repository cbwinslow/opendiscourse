INSERT INTO core.roll_call (
  jurisdiction, legislative_session, chamber, external_id, occurred_at,
  question, result, metadata, ocd_id, organization_id
) VALUES (
  'us', %(congress)s, %(chamber)s, %(external_id)s, %(occurred_at)s,
  %(question)s, %(result)s, %(metadata)s, %(ocd_id)s, %(organization_id)s
)
-- Once the official file is loaded, the provider may only add what is missing (its own identifiers).
ON CONFLICT (jurisdiction, legislative_session, external_id) DO UPDATE SET
  (occurred_at, question, result, metadata, organization_id) = (
    SELECT
      CASE WHEN official THEN core.roll_call.occurred_at
        ELSE COALESCE(EXCLUDED.occurred_at, core.roll_call.occurred_at) END,
      CASE WHEN official THEN core.roll_call.question
        ELSE COALESCE(EXCLUDED.question, core.roll_call.question) END,
      CASE WHEN official THEN core.roll_call.result
        ELSE COALESCE(EXCLUDED.result, core.roll_call.result) END,
      CASE WHEN official THEN EXCLUDED.metadata || core.roll_call.metadata
        ELSE core.roll_call.metadata || EXCLUDED.metadata END,
      CASE WHEN official THEN COALESCE(core.roll_call.organization_id, EXCLUDED.organization_id)
        ELSE COALESCE(EXCLUDED.organization_id, core.roll_call.organization_id) END
    FROM (
      SELECT EXISTS (
        SELECT 1 FROM core.roll_call_source_record s WHERE s.roll_call_id = core.roll_call.roll_call_id
      ) AS official
    ) o
  ),
  ocd_id = COALESCE(EXCLUDED.ocd_id, core.roll_call.ocd_id)
RETURNING roll_call_id;
