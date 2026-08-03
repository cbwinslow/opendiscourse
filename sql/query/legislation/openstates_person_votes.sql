SELECT voter_id, option, note
FROM openstates_source.opencivicdata_personvote
WHERE vote_event_id = %(vote_ocd_id)s;
