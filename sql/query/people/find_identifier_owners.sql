-- Persons that own any of the asserted identifiers (parallel arrays). Never by name.
SELECT DISTINCT person_id
FROM core.person_identifier
WHERE (namespace, external_id) IN (
  SELECT * FROM unnest(%(namespaces)s::text[], %(external_ids)s::text[])
)
ORDER BY person_id
