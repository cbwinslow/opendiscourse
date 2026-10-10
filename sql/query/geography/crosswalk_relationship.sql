-- One unweighted relationship row per staged district/overlap pair. The overlap areas are
-- kept as evidence in metadata; they are not a population, housing or employment weight.
INSERT INTO core.geography_crosswalk
    (from_geography_id, to_geography_id, from_vintage, to_vintage, method, weight_type,
     source_dataset_id, source_artifact_id, source_ordinal, metadata)
SELECT district.geography_id,
       overlap.geography_id,
       %(from_vintage)s,
       %(to_vintage)s,
       'relationship',
       'none',
       %(dataset_id)s,
       staged.artifact_id,
       staged.source_ordinal,
       jsonb_build_object('family', staged.family, 'overlap_kind', staged.overlap_kind,
                          'land_part', staged.area_land_part, 'water_part', staged.area_water_part)
FROM stage.census_relationship_row AS staged
JOIN core.geography AS district
  ON district.geography_type = %(district_type)s AND district.geoid = staged.district_geoid
JOIN core.geography AS overlap
  ON overlap.geography_type = %(geography_type)s AND overlap.geoid = staged.overlap_geoid
WHERE staged.artifact_id = %(artifact_id)s
ON CONFLICT ON CONSTRAINT geography_crosswalk_source_key DO NOTHING
RETURNING geography_crosswalk_id;
