INSERT INTO core.legislative_session (
  jurisdiction_id, identifier, name, classification, active, source_artifact_id, source_payload_id, metadata
) VALUES (
  %(jurisdiction_id)s, %(identifier)s, %(name)s, %(classification)s, %(active)s, %(source_artifact_id)s, %(source_payload_id)s, %(metadata)s
)
ON CONFLICT (jurisdiction_id, identifier) DO UPDATE SET
  name = COALESCE(EXCLUDED.name, core.legislative_session.name),
  classification = COALESCE(EXCLUDED.classification, core.legislative_session.classification),
  active = COALESCE(EXCLUDED.active, core.legislative_session.active),
  source_artifact_id = COALESCE(EXCLUDED.source_artifact_id, core.legislative_session.source_artifact_id),
  source_payload_id = COALESCE(EXCLUDED.source_payload_id, core.legislative_session.source_payload_id),
  metadata = core.legislative_session.metadata || EXCLUDED.metadata
RETURNING legislative_session_id;
