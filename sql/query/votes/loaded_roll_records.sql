-- Which of these artifact versions are fully loaded, and what each still could not resolve.
SELECT source_artifact_id, unresolved_bioguide_ids
FROM core.roll_call_source_record
WHERE source_artifact_id = ANY(%(artifact_ids)s::uuid[]);
