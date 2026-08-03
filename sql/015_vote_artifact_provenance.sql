ALTER TABLE fact.member_vote
  ADD COLUMN IF NOT EXISTS source_artifact_id uuid REFERENCES ingest.artifact(artifact_id);

ALTER TABLE fact.member_vote
  ALTER COLUMN source_payload_id DROP NOT NULL;

ALTER TABLE fact.member_vote
  DROP CONSTRAINT IF EXISTS member_vote_source_evidence;

ALTER TABLE fact.member_vote
  ADD CONSTRAINT member_vote_source_evidence
  CHECK (source_artifact_id IS NOT NULL OR source_payload_id IS NOT NULL);
