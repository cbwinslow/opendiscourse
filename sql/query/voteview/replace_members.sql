-- Replace every Voteview member row from one file.
-- Link on an ICPSR that already belongs to exactly one person when a non-empty
-- BioGuide on the row agrees with that person. An empty BioGuide does not block
-- that link.
-- When the ICPSR belongs to nobody and the BioGuide matches exactly one person
-- who has no ICPSR yet, link that person and store this ICPSR. One ICPSR must
-- not land on two people, and one person must not gain two ICPSRs from one file.
-- A conflicting number is left untouched. Nobody is created.
-- The caller skips this statement when the file did not change.
WITH incoming AS (
  SELECT r.*, icpsr_owner.people AS icpsr_people, guide_owner.people AS guide_people
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
  ) AS icpsr_owner ON true
  LEFT JOIN LATERAL (
    SELECT array_agg(DISTINCT person_id) AS people
    FROM core.person_identifier
    WHERE namespace = 'bioguide'
      AND external_id = NULLIF(btrim(r.bioguide), '')
  ) AS guide_owner ON true
), bios AS (
  SELECT incoming.*, known.bioguides
  FROM incoming
  LEFT JOIN LATERAL (
    SELECT array_agg(DISTINCT external_id) AS bioguides
    FROM core.person_identifier
    WHERE namespace = 'bioguide'
      AND cardinality(incoming.icpsr_people) = 1
      AND person_id = (incoming.icpsr_people)[1]
  ) AS known ON true
), claimed AS (
  SELECT
    icpsr,
    (guide_people)[1] AS person_id,
    min(source_artifact_id::text)::uuid AS source_artifact_id,
    min(run_id::text)::uuid AS run_id
  FROM bios
  WHERE cardinality(guide_people) = 1
    AND icpsr_people IS NULL
    AND NOT EXISTS (
      SELECT 1
      FROM core.person_identifier AS existing
      WHERE existing.namespace = 'icpsr'
        AND existing.person_id = (bios.guide_people)[1]
    )
  GROUP BY icpsr, (guide_people)[1]
), ambiguous AS (
  SELECT icpsr
  FROM claimed
  GROUP BY icpsr
  HAVING count(DISTINCT person_id) > 1
  UNION
  SELECT claimed.icpsr
  FROM claimed
  JOIN claimed AS other
    ON other.person_id = claimed.person_id
   AND other.icpsr <> claimed.icpsr
), safe AS (
  SELECT claimed.*
  FROM claimed
  WHERE NOT EXISTS (
    SELECT 1 FROM ambiguous WHERE ambiguous.icpsr = claimed.icpsr
  )
), added AS (
  INSERT INTO core.person_identifier (
    person_id, namespace, external_id, source_artifact_id, source_run_id
  )
  SELECT person_id, 'icpsr', icpsr, source_artifact_id, run_id
  FROM safe
  ON CONFLICT (namespace, external_id) DO NOTHING
  RETURNING 1
), inserted AS (
  INSERT INTO core.voteview_member (
    congress, chamber, icpsr, state_icpsr, district_code, state_abbrev, party_code,
    occupancy, last_means, bioname, bioguide, born, died, nominate_dim1, nominate_dim2,
    nominate_log_likelihood, nominate_geo_mean_probability, nominate_number_of_votes,
    nominate_number_of_errors, conditional, nokken_poole_dim1, nokken_poole_dim2,
    person_id, record, source_artifact_id, run_id
  )
  SELECT
    bios.congress, bios.chamber, bios.icpsr, bios.state_icpsr, bios.district_code,
    bios.state_abbrev, bios.party_code, bios.occupancy, bios.last_means, bios.bioname,
    NULLIF(btrim(bios.bioguide), ''), bios.born, bios.died, bios.nominate_dim1,
    bios.nominate_dim2, bios.nominate_log_likelihood, bios.nominate_geo_mean_probability,
    bios.nominate_number_of_votes, bios.nominate_number_of_errors, bios.conditional,
    bios.nokken_poole_dim1, bios.nokken_poole_dim2,
    CASE
      WHEN cardinality(bios.icpsr_people) = 1 AND (
        bios.bioguide IS NULL OR btrim(bios.bioguide) = ''
        OR bios.bioguides IS NULL
        OR bios.bioguide = ANY (bios.bioguides)
      ) THEN (bios.icpsr_people)[1]
      WHEN safe.person_id IS NOT NULL
       AND cardinality(bios.guide_people) = 1
       AND (bios.guide_people)[1] = safe.person_id THEN safe.person_id
      ELSE NULL
    END,
    bios.record, bios.source_artifact_id, bios.run_id
  FROM bios
  LEFT JOIN safe ON safe.icpsr = bios.icpsr
  RETURNING 1
)
SELECT count(*) AS inserted FROM inserted
