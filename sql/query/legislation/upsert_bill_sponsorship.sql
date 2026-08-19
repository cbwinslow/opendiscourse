INSERT INTO core.bill_sponsorship (
  bill_id, person_id, member_namespace, member_external_id, role, source_artifact_id, source_payload_id, source_member, metadata
) VALUES (
  %(bill_id)s, %(person_id)s, %(member_namespace)s, %(member_external_id)s, %(role)s, %(source_artifact_id)s, %(source_payload_id)s, %(source_member)s, %(metadata)s
)
ON CONFLICT (bill_id, member_namespace, member_external_id, role, source_artifact_id, source_member) DO UPDATE SET
  person_id = COALESCE(EXCLUDED.person_id, core.bill_sponsorship.person_id),
  source_payload_id = COALESCE(EXCLUDED.source_payload_id, core.bill_sponsorship.source_payload_id),
  metadata = core.bill_sponsorship.metadata || EXCLUDED.metadata;
