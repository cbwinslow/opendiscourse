-- Source rows, staged rows and stored crosswalk rows for one artifact.
SELECT
    (SELECT count(*) FROM stage.census_relationship_row WHERE artifact_id = %(artifact_id)s) AS relationship_staged,
    (SELECT count(*) FROM stage.census_relationship_row
      WHERE artifact_id = %(artifact_id)s AND (district_geoid IS NULL OR overlap_geoid IS NULL)) AS relationship_blank_side,
    (SELECT count(*) FROM stage.census_block_assignment WHERE artifact_id = %(artifact_id)s) AS block_staged,
    (SELECT count(*) FROM core.geography_crosswalk WHERE source_artifact_id = %(artifact_id)s) AS stored,
    (SELECT count(*) FROM core.geography_crosswalk
      WHERE source_artifact_id = %(artifact_id)s AND method = 'relationship' AND weight_type <> 'none') AS weighted_relationship,
    (SELECT count(*) FROM core.geography_crosswalk
      WHERE source_artifact_id = %(artifact_id)s AND method = 'block_assignment'
        AND (weight_type <> 'assignment' OR weight <> 1 OR quality_flag IS DISTINCT FROM 'whole_block_tabulation')) AS bad_assignment;
