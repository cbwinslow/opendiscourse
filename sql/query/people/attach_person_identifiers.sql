-- Add identifiers (parallel arrays) to one person. One that exists stays where it is.
INSERT INTO core.person_identifier (person_id, namespace, external_id, source_artifact_id, source_run_id)
SELECT %(person_id)s, t.namespace, t.external_id, %(artifact_id)s, %(run_id)s
FROM unnest(%(namespaces)s::text[], %(external_ids)s::text[]) AS t(namespace, external_id)
ON CONFLICT (namespace, external_id) DO NOTHING
RETURNING namespace
