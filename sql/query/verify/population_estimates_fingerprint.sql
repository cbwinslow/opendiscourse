-- Population estimates for one vintage and the geography rows they use. Usage: psql -f population_estimates_fingerprint.sql
select 'pep 2010-2020' t, count(*) n, md5(string_agg(concat_ws('|',g.geography_type,g.geoid,f.estimate_year,f.release_vintage,f.population), E'\n' order by g.geography_type,g.geoid,f.estimate_year)) h
from fact.population_estimate f join core.geography g using (geography_id) join ingest.artifact a on a.artifact_id=f.source_artifact_id where a.artifact_key like 'pep-2010-2020-%'
union all select 'geography (used by pep)', count(*), md5(string_agg(concat_ws('|',geography_type,geoid,name,parent_geoid,state_fips,county_fips), E'\n' order by geography_type,geoid))
from core.geography g where exists (select 1 from fact.population_estimate f join ingest.artifact a on a.artifact_id=f.source_artifact_id where f.geography_id=g.geography_id and a.artifact_key like 'pep-2010-2020-%');
