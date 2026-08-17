select
    geography_id,
    geography_type,
    geoid,
    name,
    state_fips,
    county_fips
from {{ source('core', 'geography') }}
