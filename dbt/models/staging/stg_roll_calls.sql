select
    roll_call_id,
    bill_id,
    jurisdiction,
    legislative_session,
    chamber,
    external_id as roll_call_external_id,
    occurred_at,
    question,
    result
from {{ source('core', 'roll_call') }}
