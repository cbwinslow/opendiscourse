INSERT INTO core.bill_identifier (
  bill_id, namespace, external_id, source_artifact_id, source_payload_id, source_url, metadata
) VALUES (
  %(bill_id)s, %(namespace)s, %(external_id)s, %(source_artifact_id)s, %(source_payload_id)s, %(source_url)s, %(metadata)s
)
ON CONFLICT (namespace, external_id) DO UPDATE SET
  bill_id = EXCLUDED.bill_id,
  source_artifact_id = COALESCE(EXCLUDED.source_artifact_id, core.bill_identifier.source_artifact_id),
  source_payload_id = COALESCE(EXCLUDED.source_payload_id, core.bill_identifier.source_payload_id),
  source_url = COALESCE(EXCLUDED.source_url, core.bill_identifier.source_url),
  metadata = core.bill_identifier.metadata || EXCLUDED.metadata;
