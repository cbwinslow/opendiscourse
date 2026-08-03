INSERT INTO core.bill_subject (
  bill_id, namespace, external_id, label, source_artifact_id, source_payload_id, source_member, metadata
) VALUES (
  %(bill_id)s, %(namespace)s, %(external_id)s, %(label)s, %(source_artifact_id)s, %(source_payload_id)s, %(source_member)s, %(metadata)s
)
ON CONFLICT (bill_id, namespace, external_id, source_artifact_id, source_member) DO UPDATE SET
  label = EXCLUDED.label,
  source_payload_id = COALESCE(EXCLUDED.source_payload_id, core.bill_subject.source_payload_id),
  metadata = core.bill_subject.metadata || EXCLUDED.metadata;
