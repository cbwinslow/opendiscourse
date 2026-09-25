INSERT INTO core.bill_cbo_cost_estimate (
  bill_id, source_artifact_id, source_member, source_ordinal,
  published_at, title, source_url, description
) VALUES (
  %(bill_id)s, %(source_artifact_id)s, %(source_member)s, %(source_ordinal)s,
  %(published_at)s::timestamptz, %(title)s, %(source_url)s, %(description)s
)
ON CONFLICT (bill_id, source_artifact_id, source_member, source_ordinal) DO UPDATE SET
  published_at = EXCLUDED.published_at,
  title = EXCLUDED.title,
  source_url = EXCLUDED.source_url,
  description = EXCLUDED.description;
