SELECT count(*) AS source_person_votes
FROM openstates_source.opencivicdata_personvote pv
WHERE pv.vote_event_id IN (
  SELECT v.id
  FROM openstates_source.opencivicdata_voteevent v
  JOIN openstates_source.opencivicdata_legislativesession s
    ON s.id = v.legislative_session_id
  WHERE s.identifier = %(congress)s
);
