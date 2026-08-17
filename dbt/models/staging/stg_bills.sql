select
    bill_id,
    jurisdiction,
    legislative_session,
    bill_type,
    bill_number,
    title,
    introduced_date,
    latest_action_date,
    latest_action
from {{ source('core', 'bill') }}
