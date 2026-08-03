INSERT INTO core.bill_committee (
  bill_id, namespace, external_id, name, chamber, source_artifact_id, source_payload_id, source_member, metadata
) VALUES (
  %(bill_id)s, %(namespace)s, %(external_id)s, %(name)s, %(chamber)s, %(source_artifact_id)s, %(source_payload_id)s, %(source_member)s, %(metadata)s
)
ON CONFLICT (bill_id, namespace, external_id, source_artifact_id, source_member) DO UPDATE SET
  name = COALESCE(EXCLUDED.name, core.bill_committee.name),
  chamber = COALESCE(EXCLUDED.chamber, core.bill_committee.chamber),
  source_payload_id = COALESCE(EXCLUDED.source_payload_id, core.bill_committee.source_payload_id),
  metadata = core.bill_committee.metadata || EXCLUDED.metadata;
