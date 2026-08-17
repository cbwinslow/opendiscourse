-- Tidy geography x year panel pivoted from fact.measurement -- the join
-- point for combining vote/bill research with place-level economic and
-- demographic series (FRED today; BLS/BEA land in the same table later).
-- One row per (geography, dataset, field, year); period_start is truncated
-- to the reporting year so sub-annual series (e.g. monthly FRED) roll up
-- alongside annual ones.
select
    g.geography_id,
    g.geography_type,
    g.geoid,
    g.name as geography_name,
    g.state_fips,
    g.county_fips,
    m.dataset_id,
    m.field_id,
    extract(year from m.period_start)::int as period_year,
    m.unit,
    avg(m.value_numeric) as value_numeric_avg,
    min(m.value_numeric) as value_numeric_min,
    max(m.value_numeric) as value_numeric_max,
    count(*) as observation_count
from {{ ref('stg_measurements') }} m
left join {{ ref('stg_geography') }} g on g.geography_id = m.geography_id
group by
    g.geography_id, g.geography_type, g.geoid, g.name, g.state_fips,
    g.county_fips, m.dataset_id, m.field_id,
    extract(year from m.period_start), m.unit
