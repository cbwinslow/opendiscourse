-- Every LIS member id we hold and the person it names. The only way a senator's vote reaches a
-- person: votes never match on a printed name.
SELECT external_id AS lis_member_id, person_id
FROM core.person_identifier
WHERE namespace = 'lis';
