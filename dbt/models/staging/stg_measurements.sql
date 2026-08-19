select
    measurement_id,
    dataset_id,
    field_id,
    geography_id,
    period_start,
    period_end,
    vintage_date,
    value_numeric,
    unit
from {{ source('fact', 'measurement') }}
