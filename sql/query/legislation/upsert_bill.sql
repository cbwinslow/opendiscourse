INSERT INTO core.bill (
  jurisdiction, legislative_session, bill_type, bill_number,
  title, introduced_date, latest_action_date, latest_action,
  metadata, legislative_session_id, ocd_id
) VALUES (
  %(jurisdiction)s, %(legislative_session)s, %(bill_type)s, %(bill_number)s,
  %(title)s, %(introduced_date)s, %(latest_action_date)s, %(latest_action)s,
  %(metadata)s, %(legislative_session_id)s, %(ocd_id)s
)
ON CONFLICT (jurisdiction, legislative_session, bill_type, bill_number) DO UPDATE SET
  title = COALESCE(EXCLUDED.title, core.bill.title),
  introduced_date = COALESCE(EXCLUDED.introduced_date, core.bill.introduced_date),
  latest_action_date = COALESCE(EXCLUDED.latest_action_date, core.bill.latest_action_date),
  latest_action = COALESCE(EXCLUDED.latest_action, core.bill.latest_action),
  metadata = core.bill.metadata || EXCLUDED.metadata,
  legislative_session_id = COALESCE(EXCLUDED.legislative_session_id, core.bill.legislative_session_id),
  ocd_id = COALESCE(EXCLUDED.ocd_id, core.bill.ocd_id)
RETURNING bill_id;
