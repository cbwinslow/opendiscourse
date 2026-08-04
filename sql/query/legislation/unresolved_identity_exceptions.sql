SELECT 'sponsor' AS kind, member_namespace AS namespace, member_external_id AS external_id,
       'no_canonical_person_identifier' AS reason,
       count(*) AS references
FROM core.bill_sponsorship
WHERE person_id IS NULL
GROUP BY member_namespace, member_external_id
UNION ALL
SELECT 'voter' AS kind, e.namespace, e.external_id, e.reason,
       sum(e.reference_count) AS references
FROM ingest.identity_exception e
WHERE NOT EXISTS (
  SELECT 1
  FROM core.person_identifier pi
  WHERE pi.namespace = e.namespace AND pi.external_id = e.external_id
)
GROUP BY e.namespace, e.external_id, e.reason;
