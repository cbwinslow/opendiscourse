WITH upserted AS (
  INSERT INTO core.jurisdiction (jurisdiction_id, name, classification, metadata)
  SELECT
    j.id,
    j.name,
    j.classification,
    jsonb_build_object('canonical_baseline', 'openstates')
  FROM openstates_source.opencivicdata_jurisdiction AS j
  WHERE j.id = %(jurisdiction_id)s
  ON CONFLICT (jurisdiction_id) DO NOTHING
  RETURNING jurisdiction_id
)
SELECT count(*)::int AS n FROM upserted;
