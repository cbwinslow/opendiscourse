SELECT
  s.identifier AS congress,
  count(*) AS source_events,
  count(DISTINCT v.identifier) AS source_keys,
  min(v.updated_at) AS source_updated_at_min,
  max(v.updated_at) AS source_updated_at_max
FROM openstates_source.opencivicdata_voteevent v
JOIN openstates_source.opencivicdata_legislativesession s
  ON s.id = v.legislative_session_id
WHERE s.identifier = ANY(%(congresses)s)
GROUP BY s.identifier
ORDER BY s.identifier;
