UPDATE core.bill_sponsorship AS sponsorship
SET person_id = identifier.person_id
FROM core.person_identifier AS identifier
WHERE sponsorship.person_id IS NULL
  AND sponsorship.member_namespace = identifier.namespace
  AND sponsorship.member_external_id = identifier.external_id
RETURNING sponsorship.bill_sponsorship_id;
