INSERT INTO core.bill_law (
  bill_id, source_artifact_id, source_member, source_ordinal, law_type, law_number
) VALUES (
  %(bill_id)s, %(source_artifact_id)s, %(source_member)s, %(source_ordinal)s, %(law_type)s, %(law_number)s
)
ON CONFLICT (bill_id, source_artifact_id, source_member, source_ordinal) DO UPDATE SET
  law_type = EXCLUDED.law_type,
  law_number = EXCLUDED.law_number;
