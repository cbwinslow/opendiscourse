-- Replace every Voteview member row from one file. A person is linked only when
-- the ICPSR belongs to exactly one person and a non-empty BioGuide on the row
-- is one that person already has. Nobody is created and no identifier moves.
-- An empty BioGuide does not block the ICPSR link. The same values are not
-- written here: the caller skips this statement when the file did not change.
WITH incoming AS (
  SELECT r.*, owners.people, bios.bioguides
  FROM jsonb_to_recordset(%(rows)s::jsonb) AS r(
    congress integer,
    chamber text,
    icpsr text,
    state_icpsr integer,
    district_code integer,
    state_abbrev text,
    party_code integer,
    occupancy integer,
    last_means integer,
    bioname text,
    bioguide text,
    born double precision,
    died double precision,
    nominate_dim1 double precision,
    nominate_dim2 double precision,
    nominate_log_likelihood double precision,
    nominate_geo_mean_probability double precision,
    nominate_number_of_votes integer,
    nominate_number_of_errors integer,
    conditional text,
    nokken_poole_dim1 double precision,
    nokken_poole_dim2 double precision,
    record jsonb,
    source_artifact_id uuid,
    run_id uuid
  )
  LEFT JOIN LATERAL (
    SELECT array_agg(DISTINCT person_id) AS people
    FROM core.person_identifier
    WHERE namespace = 'icpsr' AND external_id = r.icpsr
  ) AS owners ON true
  LEFT JOIN LATERAL (
    SELECT array_agg(DISTINCT external_id) AS bioguides
    FROM core.person_identifier
    WHERE namespace = 'bioguide'
      AND cardinality(owners.people) = 1
      AND person_id = (owners.people)[1]
  ) AS bios ON true
), inserted AS (
  INSERT INTO core.voteview_member (
    congress, chamber, icpsr, state_icpsr, district_code, state_abbrev, party_code,
    occupancy, last_means, bioname, bioguide, born, died, nominate_dim1, nominate_dim2,
    nominate_log_likelihood, nominate_geo_mean_probability, nominate_number_of_votes,
    nominate_number_of_errors, conditional, nokken_poole_dim1, nokken_poole_dim2,
    person_id, record, source_artifact_id, run_id
  )
  SELECT
    congress, chamber, icpsr, state_icpsr, district_code, state_abbrev, party_code,
    occupancy, last_means, bioname, NULLIF(btrim(bioguide), ''), born, died,
    nominate_dim1, nominate_dim2, nominate_log_likelihood, nominate_geo_mean_probability,
    nominate_number_of_votes, nominate_number_of_errors, conditional,
    nokken_poole_dim1, nokken_poole_dim2,
    CASE
      WHEN cardinality(people) = 1 AND (
        bioguide IS NULL OR btrim(bioguide) = ''
        OR bioguides IS NULL
        OR bioguide = ANY (bioguides)
      ) THEN (people)[1]
      ELSE NULL
    END,
    record, source_artifact_id, run_id
  FROM incoming
  RETURNING 1
)
SELECT count(*) AS inserted FROM inserted
