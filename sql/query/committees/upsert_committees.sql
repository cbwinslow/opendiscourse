-- One committee per membership-file key. A rerun that brings the same values
-- changes nothing, including run_id. %(rows)s is a JSON array.
INSERT INTO core.committee (
  thomas_key, parent_thomas_key, kind, chamber, name,
  url, minority_url, house_committee_id, senate_committee_id,
  address, phone, rss_url, minority_rss_url,
  jurisdiction, jurisdiction_source, wikipedia, youtube_id,
  congresses, former_names, source_artifact_id, history_artifact_id, run_id
)
SELECT
  thomas_key, parent_thomas_key, kind, chamber, name,
  url, minority_url, house_committee_id, senate_committee_id,
  address, phone, rss_url, minority_rss_url,
  jurisdiction, jurisdiction_source, wikipedia, youtube_id,
  COALESCE(ARRAY(SELECT jsonb_array_elements_text(congresses)::integer), '{}'::integer[]),
  former_names, source_artifact_id, history_artifact_id, run_id
FROM jsonb_to_recordset(%(rows)s::jsonb) AS r(
  thomas_key text, parent_thomas_key text, kind text, chamber text, name text,
  url text, minority_url text, house_committee_id text, senate_committee_id text,
  address text, phone text, rss_url text, minority_rss_url text,
  jurisdiction text, jurisdiction_source text, wikipedia text, youtube_id text,
  congresses jsonb, former_names jsonb, source_artifact_id uuid, history_artifact_id uuid,
  run_id uuid
)
ON CONFLICT (thomas_key) DO UPDATE
SET parent_thomas_key = EXCLUDED.parent_thomas_key,
    kind = EXCLUDED.kind,
    chamber = EXCLUDED.chamber,
    name = EXCLUDED.name,
    url = EXCLUDED.url,
    minority_url = EXCLUDED.minority_url,
    house_committee_id = EXCLUDED.house_committee_id,
    senate_committee_id = EXCLUDED.senate_committee_id,
    address = EXCLUDED.address,
    phone = EXCLUDED.phone,
    rss_url = EXCLUDED.rss_url,
    minority_rss_url = EXCLUDED.minority_rss_url,
    jurisdiction = EXCLUDED.jurisdiction,
    jurisdiction_source = EXCLUDED.jurisdiction_source,
    wikipedia = EXCLUDED.wikipedia,
    youtube_id = EXCLUDED.youtube_id,
    congresses = EXCLUDED.congresses,
    former_names = EXCLUDED.former_names,
    source_artifact_id = EXCLUDED.source_artifact_id,
    history_artifact_id = EXCLUDED.history_artifact_id,
    run_id = EXCLUDED.run_id,
    loaded_at = now()
WHERE (
  core.committee.parent_thomas_key, core.committee.kind, core.committee.chamber, core.committee.name,
  core.committee.url, core.committee.minority_url, core.committee.house_committee_id,
  core.committee.senate_committee_id, core.committee.address, core.committee.phone,
  core.committee.rss_url, core.committee.minority_rss_url, core.committee.jurisdiction,
  core.committee.jurisdiction_source, core.committee.wikipedia, core.committee.youtube_id,
  core.committee.congresses, core.committee.former_names, core.committee.source_artifact_id,
  core.committee.history_artifact_id
) IS DISTINCT FROM (
  EXCLUDED.parent_thomas_key, EXCLUDED.kind, EXCLUDED.chamber, EXCLUDED.name,
  EXCLUDED.url, EXCLUDED.minority_url, EXCLUDED.house_committee_id,
  EXCLUDED.senate_committee_id, EXCLUDED.address, EXCLUDED.phone,
  EXCLUDED.rss_url, EXCLUDED.minority_rss_url, EXCLUDED.jurisdiction,
  EXCLUDED.jurisdiction_source, EXCLUDED.wikipedia, EXCLUDED.youtube_id,
  EXCLUDED.congresses, EXCLUDED.former_names, EXCLUDED.source_artifact_id,
  EXCLUDED.history_artifact_id
)
RETURNING (xmax = 0) AS inserted
