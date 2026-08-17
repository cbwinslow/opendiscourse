select
    roll_call_id,
    person_id,
    position
from {{ source('fact', 'member_vote') }}
