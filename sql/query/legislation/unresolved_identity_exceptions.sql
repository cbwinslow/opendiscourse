SELECT 'sponsor' AS kind, member_namespace AS namespace, member_external_id AS external_id,
       count(*) AS references
FROM core.bill_sponsorship
WHERE person_id IS NULL
GROUP BY member_namespace, member_external_id;
