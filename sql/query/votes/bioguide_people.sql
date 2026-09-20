-- Every BioGuide id we hold and the person it names. The only way a vote reaches a person:
-- votes never match on a printed name.
SELECT external_id AS bioguide_id, person_id
FROM core.person_identifier
WHERE namespace = 'bioguide';
