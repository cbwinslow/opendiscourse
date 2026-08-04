SELECT jsonb_build_object(
  'bills_118', (SELECT count(*) FROM core.bill WHERE legislative_session = '118'),
  'bills_119', (SELECT count(*) FROM core.bill WHERE legislative_session = '119'),
  'people', (SELECT count(*) FROM core.person),
  'organizations', (SELECT count(*) FROM core.organization),
  'roll_calls_118', (SELECT count(*) FROM core.roll_call WHERE legislative_session = '118'),
  'roll_calls_119', (SELECT count(*) FROM core.roll_call WHERE legislative_session = '119'),
  'member_votes_118', (SELECT count(*) FROM fact.member_vote mv JOIN core.roll_call rc ON rc.roll_call_id = mv.roll_call_id WHERE rc.legislative_session = '118'),
  'member_votes_119', (SELECT count(*) FROM fact.member_vote mv JOIN core.roll_call rc ON rc.roll_call_id = mv.roll_call_id WHERE rc.legislative_session = '119'),
  'unresolved_sponsorships', (SELECT count(*) FROM core.bill_sponsorship WHERE person_id IS NULL),
  'unresolved_voters', COALESCE((
    SELECT sum(e.reference_count)
    FROM ingest.identity_exception e
    WHERE NOT EXISTS (
      SELECT 1
      FROM core.person_identifier pi
      WHERE pi.namespace = e.namespace AND pi.external_id = e.external_id
    )
  ), 0),
  'latest_runs', COALESCE((SELECT jsonb_agg(row_to_json(r) ORDER BY r.started_at DESC) FROM (SELECT dataset_id, status, started_at, finished_at, record_count, error_message, parameters FROM ingest.run WHERE dataset_id IN ('congress.govinfo_billstatus', 'openstates.legislation') ORDER BY started_at DESC LIMIT 10) r), '[]'::jsonb)
) AS health;
