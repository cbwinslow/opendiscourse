INSERT INTO core.bill_amendment (
  bill_id, source_artifact_id, source_member, source_ordinal,
  amendment_congress, amendment_type, amendment_number, chamber, purpose, description,
  submitted_at, proposed_at, update_date, latest_action_date, latest_action_text,
  sponsor_bioguide_id, metadata
) VALUES (
  %(bill_id)s, %(source_artifact_id)s, %(source_member)s, %(source_ordinal)s,
  %(amendment_congress)s, %(amendment_type)s, %(amendment_number)s, %(chamber)s, %(purpose)s, %(description)s,
  %(submitted_at)s::timestamptz, %(proposed_at)s::timestamptz, %(update_date)s::timestamptz,
  %(latest_action_date)s::date, %(latest_action_text)s, %(sponsor_bioguide_id)s, %(metadata)s
)
ON CONFLICT (bill_id, source_artifact_id, source_member, source_ordinal) DO UPDATE SET
  amendment_congress = EXCLUDED.amendment_congress,
  amendment_type = EXCLUDED.amendment_type,
  amendment_number = EXCLUDED.amendment_number,
  chamber = EXCLUDED.chamber,
  purpose = EXCLUDED.purpose,
  description = EXCLUDED.description,
  submitted_at = EXCLUDED.submitted_at,
  proposed_at = EXCLUDED.proposed_at,
  update_date = EXCLUDED.update_date,
  latest_action_date = EXCLUDED.latest_action_date,
  latest_action_text = EXCLUDED.latest_action_text,
  sponsor_bioguide_id = EXCLUDED.sponsor_bioguide_id,
  metadata = EXCLUDED.metadata;
