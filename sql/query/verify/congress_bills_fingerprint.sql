-- Order-independent fingerprint of one Congress's bills in core (no surrogate uuids).
-- Usage: psql -v congress=108 -f congress_bills_fingerprint.sql
with b as (select bill_id, bill_type, bill_number, title, introduced_date, latest_action_date, latest_action from core.bill where legislative_session = :'congress')
select 'bill' t, count(*) n, md5(string_agg(concat_ws('|',bill_type,bill_number,title,introduced_date,latest_action_date,latest_action), E'\n' order by bill_type,bill_number)) h from b
union all select 'bill_source_record', count(*), md5(string_agg(concat_ws('|',b.bill_type,b.bill_number,r.source_member,r.record_sha256), E'\n' order by b.bill_type,b.bill_number,r.source_member)) from core.bill_source_record r join b using (bill_id)
union all select 'bill_action', count(*), md5(string_agg(concat_ws('|',b.bill_type,b.bill_number,a.source_ordinal,a.action_date,a.description), E'\n' order by b.bill_type,b.bill_number,a.source_ordinal,a.description)) from core.bill_action a join b using (bill_id)
union all select 'bill_sponsorship', count(*), md5(string_agg(concat_ws('|',b.bill_type,b.bill_number,s.member_namespace,s.member_external_id,s.role), E'\n' order by b.bill_type,b.bill_number,s.member_namespace,s.member_external_id,s.role)) from core.bill_sponsorship s join b using (bill_id)
union all select 'bill_subject', count(*), md5(string_agg(concat_ws('|',b.bill_type,b.bill_number,s.namespace,s.external_id,s.label), E'\n' order by b.bill_type,b.bill_number,s.namespace,s.external_id,s.label)) from core.bill_subject s join b using (bill_id)
order by 1;
