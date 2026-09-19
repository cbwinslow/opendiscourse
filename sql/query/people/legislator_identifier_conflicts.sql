-- Identifiers the source assigns to one BioGuide person but the database
-- already assigns to a different person. Reported for review, never resolved.
-- bioguide_person_created marks the risky class: this run made a new person for
-- a BioGuide whose other id is already held, i.e. a possible split of one member.
SELECT s.bioguide, s.namespace, s.external_id, i.person_id AS existing_person_id,
       b.person_id AS bioguide_person_id,
       b.person_id = s.new_person_id AS bioguide_person_created
FROM legislator_stage s
JOIN core.person_identifier i
  ON i.namespace = s.namespace AND i.external_id = s.external_id
JOIN core.person_identifier b
  ON b.namespace = 'bioguide' AND b.external_id = s.bioguide
WHERE i.person_id <> b.person_id
ORDER BY s.bioguide, s.namespace, s.external_id
