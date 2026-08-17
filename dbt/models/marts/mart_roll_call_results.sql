-- One row per roll call: bill identity, chamber, jurisdiction, session, and
-- vote tallies. See docs/blueprint.md's "mart" layer examples ("bill
-- timelines"). Position values are lowercase and provider-normalized
-- ('yes'/'no'/'not voting'/'other') by the loaders that write
-- fact.member_vote, not raw provider text.
with votes as (
    select
        roll_call_id,
        count(*) filter (where position = 'yes') as yea_count,
        count(*) filter (where position = 'no') as nay_count,
        count(*) filter (where position not in ('yes', 'no')) as other_count,
        count(*) as total_votes
    from {{ ref('stg_member_votes') }}
    group by roll_call_id
)

select
    rc.roll_call_id,
    rc.jurisdiction,
    rc.legislative_session,
    rc.chamber,
    rc.roll_call_external_id,
    rc.occurred_at,
    rc.question,
    rc.result,
    b.bill_id,
    b.bill_type,
    b.bill_number,
    b.title as bill_title,
    b.introduced_date,
    coalesce(v.yea_count, 0) as yea_count,
    coalesce(v.nay_count, 0) as nay_count,
    coalesce(v.other_count, 0) as other_count,
    coalesce(v.total_votes, 0) as total_votes
from {{ ref('stg_roll_calls') }} rc
left join {{ ref('stg_bills') }} b on b.bill_id = rc.bill_id
left join votes v on v.roll_call_id = rc.roll_call_id
