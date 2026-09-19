INSERT INTO core.bill_related_bill (
  bill_id, source_artifact_id, source_member, source_ordinal,
  related_congress, related_bill_type, related_bill_number, title,
  latest_action_date, latest_action_text, relationships
) VALUES (
  %(bill_id)s, %(source_artifact_id)s, %(source_member)s, %(source_ordinal)s,
  %(related_congress)s, %(related_bill_type)s, %(related_bill_number)s, %(title)s,
  %(latest_action_date)s::date, %(latest_action_text)s, %(relationships)s
)
ON CONFLICT (bill_id, source_artifact_id, source_member, source_ordinal) DO UPDATE SET
  related_congress = EXCLUDED.related_congress,
  related_bill_type = EXCLUDED.related_bill_type,
  related_bill_number = EXCLUDED.related_bill_number,
  title = EXCLUDED.title,
  latest_action_date = EXCLUDED.latest_action_date,
  latest_action_text = EXCLUDED.latest_action_text,
  relationships = EXCLUDED.relationships;
