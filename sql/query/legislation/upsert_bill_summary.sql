INSERT INTO core.bill_summary (
  bill_id, source_artifact_id, source_member, source_ordinal,
  version_code, action_date, action_description, update_date, text
) VALUES (
  %(bill_id)s, %(source_artifact_id)s, %(source_member)s, %(source_ordinal)s,
  %(version_code)s, %(action_date)s::date, %(action_description)s, %(update_date)s::timestamptz, %(text)s
)
ON CONFLICT (bill_id, source_artifact_id, source_member, source_ordinal) DO UPDATE SET
  version_code = EXCLUDED.version_code,
  action_date = EXCLUDED.action_date,
  action_description = EXCLUDED.action_description,
  update_date = EXCLUDED.update_date,
  text = EXCLUDED.text;
