-- People, identifiers and sponsor-to-person links for one Congress. Usage: psql -v congress=108 -f people_fingerprint.sql
with bio as (select person_id, external_id bioguide from core.person_identifier where namespace='bioguide')
select 'person(bioguide)' t, count(*) n, md5(string_agg(concat_ws('|',bio.bioguide,p.full_name,p.given_name,p.family_name), E'\n' order by bio.bioguide)) h from bio join core.person p using (person_id)
union all select 'person_identifier', count(*), md5(string_agg(concat_ws('|',bio.bioguide,i.namespace,i.external_id,i.valid_from,i.valid_to), E'\n' order by bio.bioguide,i.namespace,i.external_id)) from core.person_identifier i join bio using (person_id)
union all select 'sponsor->person link', count(*), md5(string_agg(concat_ws('|',b.bill_type,b.bill_number,s.role,bio.bioguide), E'\n' order by b.bill_type,b.bill_number,s.role,bio.bioguide)) from core.bill_sponsorship s join core.bill b using (bill_id) join bio on bio.person_id=s.person_id where b.legislative_session=:'congress'
order by 1;
