INSERT INTO core.roll_call (
  jurisdiction, legislative_session, chamber, external_id, occurred_at,
  question, result, metadata, ocd_id, organization_id
) VALUES (
  'us', %(congress)s, %(chamber)s, %(external_id)s, %(occurred_at)s,
  %(question)s, %(result)s, %(metadata)s, %(ocd_id)s, %(organization_id)s
)
ON CONFLICT (jurisdiction, legislative_session, external_id) DO UPDATE SET
  occurred_at = COALESCE(EXCLUDED.occurred_at, core.roll_call.occurred_at),
  question = COALESCE(EXCLUDED.question, core.roll_call.question),
  result = COALESCE(EXCLUDED.result, core.roll_call.result),
  metadata = core.roll_call.metadata || EXCLUDED.metadata,
  ocd_id = COALESCE(EXCLUDED.ocd_id, core.roll_call.ocd_id),
  organization_id = COALESCE(EXCLUDED.organization_id, core.roll_call.organization_id)
RETURNING roll_call_id;
