CREATE TABLE IF NOT EXISTS fact.measurement (
  measurement_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  dataset_id text NOT NULL REFERENCES catalog.dataset(dataset_id),
  field_id text NOT NULL,
  geography_id uuid REFERENCES core.geography(geography_id),
  period_start date NOT NULL,
  period_end date,
  vintage_date date,
  value_numeric numeric,
  value_text text,
  unit text,
  margin_of_error numeric,
  flags jsonb NOT NULL DEFAULT '{}'::jsonb,
  source_payload_id uuid NOT NULL REFERENCES ingest.raw_payload(payload_id),
  UNIQUE NULLS NOT DISTINCT (dataset_id, field_id, geography_id, period_start, period_end, vintage_date)
);
CREATE INDEX IF NOT EXISTS measurement_lookup_idx ON fact.measurement(dataset_id, field_id, period_start);

CREATE TABLE IF NOT EXISTS fact.market_bar (
  instrument_id uuid NOT NULL REFERENCES core.instrument(instrument_id),
  trade_date date NOT NULL,
  interval text NOT NULL DEFAULT '1d',
  open numeric, high numeric, low numeric, close numeric, adjusted_close numeric, volume numeric,
  source_payload_id uuid NOT NULL REFERENCES ingest.raw_payload(payload_id),
  PRIMARY KEY (instrument_id, trade_date, interval)
);

CREATE TABLE IF NOT EXISTS core.bill (
  bill_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  jurisdiction text NOT NULL,
  legislative_session text NOT NULL,
  bill_type text NOT NULL,
  bill_number text NOT NULL,
  title text,
  introduced_date date,
  latest_action_date date,
  latest_action text,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  UNIQUE (jurisdiction, legislative_session, bill_type, bill_number)
);
CREATE TABLE IF NOT EXISTS core.bill_action (
  bill_action_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  bill_id uuid NOT NULL REFERENCES core.bill(bill_id),
  action_date timestamptz,
  description text NOT NULL,
  classification text[],
  source_payload_id uuid NOT NULL REFERENCES ingest.raw_payload(payload_id)
);
CREATE TABLE IF NOT EXISTS core.roll_call (
  roll_call_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  jurisdiction text NOT NULL,
  legislative_session text NOT NULL,
  chamber text,
  external_id text NOT NULL,
  occurred_at timestamptz,
  question text,
  result text,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  UNIQUE (jurisdiction, legislative_session, external_id)
);
CREATE TABLE IF NOT EXISTS fact.member_vote (
  roll_call_id uuid NOT NULL REFERENCES core.roll_call(roll_call_id),
  person_id uuid REFERENCES core.person(person_id),
  position text NOT NULL,
  source_payload_id uuid NOT NULL REFERENCES ingest.raw_payload(payload_id),
  PRIMARY KEY (roll_call_id, person_id)
);
