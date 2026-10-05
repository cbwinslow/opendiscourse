INSERT INTO stage.tiger_feature
    (artifact_id, layer, source_ordinal, geoid, name, state_fips, county_fips, raw, geom)
VALUES
    (%s, %s, %s, %s, %s, %s, %s, %s,
     ST_Transform(ST_SetSRID(ST_GeomFromWKB(%s), 4269), 4326))
ON CONFLICT DO NOTHING;
