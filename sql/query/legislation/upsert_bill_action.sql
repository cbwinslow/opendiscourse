INSERT INTO core.bill_action (
  bill_id, action_date, description, classification, source_artifact_id, source_payload_id, source_member, source_ordinal, metadata
) VALUES (
  %(bill_id)s, %(action_date)s, %(description)s, %(classification)s, %(source_artifact_id)s, %(source_payload_id)s, %(source_member)s, %(source_ordinal)s, %(metadata)s
)
ON CONFLICT (bill_id, source_artifact_id, source_member, source_ordinal) WHERE source_artifact_id IS NOT NULL DO UPDATE SET
  action_date = COALESCE(EXCLUDED.action_date, core.bill_action.action_date),
  description = EXCLUDED.description,
  classification = COALESCE(EXCLUDED.classification, core.bill_action.classification),
  source_payload_id = COALESCE(EXCLUDED.source_payload_id, core.bill_action.source_payload_id),
  metadata = core.bill_action.metadata || EXCLUDED.metadata;
