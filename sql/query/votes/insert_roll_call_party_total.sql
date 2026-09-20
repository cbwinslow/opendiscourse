INSERT INTO core.roll_call_party_total (
  roll_call_id, party, yea_total, nay_total, present_total, not_voting_total, source_artifact_id
) VALUES (
  %(roll_call_id)s, %(party)s, %(yea_total)s, %(nay_total)s, %(present_total)s, %(not_voting_total)s,
  %(source_artifact_id)s
)
ON CONFLICT (roll_call_id, party) DO UPDATE SET
  yea_total = EXCLUDED.yea_total,
  nay_total = EXCLUDED.nay_total,
  present_total = EXCLUDED.present_total,
  not_voting_total = EXCLUDED.not_voting_total,
  source_artifact_id = EXCLUDED.source_artifact_id;
