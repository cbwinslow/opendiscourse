--
-- PostgreSQL database dump
--

\restrict opendiscourseschemasnapshot

-- Dumped from database version 17.11 (Ubuntu 17.11-1.pgdg24.04+2)
-- Dumped by pg_dump version 17.11 (Ubuntu 17.11-1.pgdg24.04+2)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: api; Type: SCHEMA; Schema: -; Owner: cbwinslow
--

CREATE SCHEMA api;


ALTER SCHEMA api OWNER TO cbwinslow;

--
-- Name: SCHEMA api; Type: COMMENT; Schema: -; Owner: cbwinslow
--

COMMENT ON SCHEMA api IS 'Read-only PostgREST/research HTTP surface. Views are reviewed; core/ingest stay private.';


--
-- Name: catalog; Type: SCHEMA; Schema: -; Owner: cbwinslow
--

CREATE SCHEMA catalog;


ALTER SCHEMA catalog OWNER TO cbwinslow;

--
-- Name: core; Type: SCHEMA; Schema: -; Owner: cbwinslow
--

CREATE SCHEMA core;


ALTER SCHEMA core OWNER TO cbwinslow;

--
-- Name: fact; Type: SCHEMA; Schema: -; Owner: cbwinslow
--

CREATE SCHEMA fact;


ALTER SCHEMA fact OWNER TO cbwinslow;

--
-- Name: ingest; Type: SCHEMA; Schema: -; Owner: cbwinslow
--

CREATE SCHEMA ingest;


ALTER SCHEMA ingest OWNER TO cbwinslow;

--
-- Name: leg; Type: SCHEMA; Schema: -; Owner: cbwinslow
--

CREATE SCHEMA leg;


ALTER SCHEMA leg OWNER TO cbwinslow;

--
-- Name: mart; Type: SCHEMA; Schema: -; Owner: cbwinslow
--

CREATE SCHEMA mart;


ALTER SCHEMA mart OWNER TO cbwinslow;

--
-- Name: openstates_source; Type: SCHEMA; Schema: -; Owner: postgres
--

CREATE SCHEMA openstates_source;


ALTER SCHEMA openstates_source OWNER TO postgres;

--
-- Name: stage; Type: SCHEMA; Schema: -; Owner: cbwinslow
--

CREATE SCHEMA stage;


ALTER SCHEMA stage OWNER TO cbwinslow;

--
-- Name: pg_trgm; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS pg_trgm WITH SCHEMA public;


--
-- Name: EXTENSION pg_trgm; Type: COMMENT; Schema: -; Owner: 
--

COMMENT ON EXTENSION pg_trgm IS 'text similarity measurement and index searching based on trigrams';


--
-- Name: pgcrypto; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS pgcrypto WITH SCHEMA public;


--
-- Name: EXTENSION pgcrypto; Type: COMMENT; Schema: -; Owner: 
--

COMMENT ON EXTENSION pgcrypto IS 'cryptographic functions';


--
-- Name: postgis; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS postgis WITH SCHEMA public;


--
-- Name: EXTENSION postgis; Type: COMMENT; Schema: -; Owner: 
--

COMMENT ON EXTENSION postgis IS 'PostGIS geometry and geography spatial types and functions';


--
-- Name: postgres_fdw; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS postgres_fdw WITH SCHEMA public;


--
-- Name: EXTENSION postgres_fdw; Type: COMMENT; Schema: -; Owner: 
--

COMMENT ON EXTENSION postgres_fdw IS 'foreign-data wrapper for remote PostgreSQL servers';


--
-- Name: unaccent; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS unaccent WITH SCHEMA public;


--
-- Name: EXTENSION unaccent; Type: COMMENT; Schema: -; Owner: 
--

COMMENT ON EXTENSION unaccent IS 'text search dictionary that removes accents';


--
-- Name: vector; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA public;


--
-- Name: EXTENSION vector; Type: COMMENT; Schema: -; Owner: 
--

COMMENT ON EXTENSION vector IS 'vector data type and ivfflat and hnsw access methods';


--
-- Name: openstates_local; Type: SERVER; Schema: -; Owner: postgres
--

CREATE SERVER openstates_local FOREIGN DATA WRAPPER postgres_fdw OPTIONS (
    dbname 'openstates',
    host '/var/run/postgresql',
    options '-c role=openstates_fdw',
    port '5434'
);


ALTER SERVER openstates_local OWNER TO postgres;

--
-- Name: USER MAPPING cbwinslow SERVER openstates_local; Type: USER MAPPING; Schema: -; Owner: postgres
--

CREATE USER MAPPING FOR cbwinslow SERVER openstates_local OPTIONS (
    password_required 'false',
    "user" 'postgres'
);


--
-- Name: USER MAPPING postgres SERVER openstates_local; Type: USER MAPPING; Schema: -; Owner: postgres
--

CREATE USER MAPPING FOR postgres SERVER openstates_local;


SET default_table_access_method = heap;

--
-- Name: basket; Type: TABLE; Schema: catalog; Owner: cbwinslow
--

CREATE TABLE catalog.basket (
    basket_id uuid DEFAULT gen_random_uuid() NOT NULL,
    name text NOT NULL,
    state text DEFAULT 'draft'::text NOT NULL,
    metadata jsonb DEFAULT '{}'::jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT basket_state_check CHECK ((state = ANY (ARRAY['draft'::text, 'review'::text, 'approved'::text, 'archived'::text])))
);


ALTER TABLE catalog.basket OWNER TO cbwinslow;

--
-- Name: basket_item; Type: TABLE; Schema: catalog; Owner: cbwinslow
--

CREATE TABLE catalog.basket_item (
    basket_id uuid NOT NULL,
    resource_id uuid NOT NULL,
    selected_fields jsonb DEFAULT '[]'::jsonb NOT NULL,
    metadata jsonb DEFAULT '{}'::jsonb NOT NULL,
    added_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE catalog.basket_item OWNER TO cbwinslow;

--
-- Name: dataset; Type: TABLE; Schema: catalog; Owner: cbwinslow
--

CREATE TABLE catalog.dataset (
    dataset_id text NOT NULL,
    provider_id text NOT NULL,
    title text NOT NULL,
    access_method text,
    grain_description text,
    refresh_cadence text,
    priority smallint,
    active boolean DEFAULT true NOT NULL,
    metadata jsonb DEFAULT '{}'::jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE catalog.dataset OWNER TO cbwinslow;

--
-- Name: dataset_field; Type: TABLE; Schema: catalog; Owner: cbwinslow
--

CREATE TABLE catalog.dataset_field (
    dataset_id text NOT NULL,
    field_id text NOT NULL,
    label text,
    data_type text,
    description text,
    valid_from date NOT NULL,
    valid_to date,
    metadata jsonb DEFAULT '{}'::jsonb NOT NULL
);


ALTER TABLE catalog.dataset_field OWNER TO cbwinslow;

--
-- Name: discovery; Type: TABLE; Schema: catalog; Owner: cbwinslow
--

CREATE TABLE catalog.discovery (
    discovery_id text NOT NULL,
    dataset_id text NOT NULL,
    state text DEFAULT 'idle'::text NOT NULL,
    cursor jsonb DEFAULT '{}'::jsonb NOT NULL,
    statistics jsonb DEFAULT '{}'::jsonb NOT NULL,
    error_message text,
    started_at timestamp with time zone,
    finished_at timestamp with time zone,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT discovery_state_check CHECK ((state = ANY (ARRAY['idle'::text, 'running'::text, 'paused'::text, 'complete'::text, 'failed'::text])))
);


ALTER TABLE catalog.discovery OWNER TO cbwinslow;

--
-- Name: plan; Type: TABLE; Schema: catalog; Owner: cbwinslow
--

CREATE TABLE catalog.plan (
    plan_id text NOT NULL,
    dataset_id text NOT NULL,
    handler text NOT NULL,
    cadence text NOT NULL,
    enabled boolean DEFAULT true NOT NULL,
    parameters jsonb DEFAULT '{}'::jsonb NOT NULL,
    metadata jsonb DEFAULT '{}'::jsonb NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE catalog.plan OWNER TO cbwinslow;

--
-- Name: provider; Type: TABLE; Schema: catalog; Owner: cbwinslow
--

CREATE TABLE catalog.provider (
    provider_id text NOT NULL,
    name text NOT NULL,
    base_url text,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE catalog.provider OWNER TO cbwinslow;

--
-- Name: resource; Type: TABLE; Schema: catalog; Owner: cbwinslow
--

CREATE TABLE catalog.resource (
    resource_id uuid DEFAULT gen_random_uuid() NOT NULL,
    dataset_id text NOT NULL,
    resource_key text NOT NULL,
    resource_type text NOT NULL,
    title text NOT NULL,
    summary text,
    universe text,
    release_year integer,
    metadata jsonb DEFAULT '{}'::jsonb NOT NULL,
    source_artifact_id uuid,
    discovered_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE catalog.resource OWNER TO cbwinslow;

--
-- Name: resource_field; Type: TABLE; Schema: catalog; Owner: cbwinslow
--

CREATE TABLE catalog.resource_field (
    resource_id uuid NOT NULL,
    field_key text NOT NULL,
    label text,
    description text,
    data_type text,
    metadata jsonb DEFAULT '{}'::jsonb NOT NULL,
    discovered_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE catalog.resource_field OWNER TO cbwinslow;

--
-- Name: snapshot; Type: TABLE; Schema: catalog; Owner: cbwinslow
--

CREATE TABLE catalog.snapshot (
    snapshot_id uuid DEFAULT gen_random_uuid() NOT NULL,
    dataset_id text NOT NULL,
    source_url text NOT NULL,
    checksum_sha256 text NOT NULL,
    artifact_id uuid,
    captured_at timestamp with time zone DEFAULT now() NOT NULL,
    metadata jsonb DEFAULT '{}'::jsonb NOT NULL
);


ALTER TABLE catalog.snapshot OWNER TO cbwinslow;

--
-- Name: snapshot_resource; Type: TABLE; Schema: catalog; Owner: cbwinslow
--

CREATE TABLE catalog.snapshot_resource (
    snapshot_id uuid NOT NULL,
    resource_id uuid NOT NULL
);


ALTER TABLE catalog.snapshot_resource OWNER TO cbwinslow;

--
-- Name: bill; Type: TABLE; Schema: core; Owner: cbwinslow
--

CREATE TABLE core.bill (
    bill_id uuid DEFAULT gen_random_uuid() NOT NULL,
    jurisdiction text NOT NULL,
    legislative_session text NOT NULL,
    bill_type text NOT NULL,
    bill_number text NOT NULL,
    title text,
    introduced_date date,
    latest_action_date date,
    latest_action text,
    metadata jsonb DEFAULT '{}'::jsonb NOT NULL,
    legislative_session_id uuid,
    ocd_id text
);


ALTER TABLE core.bill OWNER TO cbwinslow;

--
-- Name: bill_action; Type: TABLE; Schema: core; Owner: cbwinslow
--

CREATE TABLE core.bill_action (
    bill_action_id uuid DEFAULT gen_random_uuid() NOT NULL,
    bill_id uuid NOT NULL,
    action_date timestamp with time zone,
    description text NOT NULL,
    classification text[],
    source_payload_id uuid,
    source_artifact_id uuid,
    source_member text,
    source_ordinal integer,
    metadata jsonb DEFAULT '{}'::jsonb NOT NULL,
    CONSTRAINT bill_action_source_evidence CHECK (((source_artifact_id IS NOT NULL) OR (source_payload_id IS NOT NULL)))
);


ALTER TABLE core.bill_action OWNER TO cbwinslow;

--
-- Name: bill_committee; Type: TABLE; Schema: core; Owner: cbwinslow
--

CREATE TABLE core.bill_committee (
    bill_committee_id uuid DEFAULT gen_random_uuid() NOT NULL,
    bill_id uuid NOT NULL,
    namespace text DEFAULT 'congress.gov.committee'::text NOT NULL,
    external_id text NOT NULL,
    name text,
    chamber text,
    source_artifact_id uuid,
    source_payload_id uuid,
    source_member text,
    metadata jsonb DEFAULT '{}'::jsonb NOT NULL,
    CONSTRAINT bill_committee_check CHECK (((source_artifact_id IS NOT NULL) OR (source_payload_id IS NOT NULL)))
);


ALTER TABLE core.bill_committee OWNER TO cbwinslow;

--
-- Name: bill_document; Type: TABLE; Schema: core; Owner: cbwinslow
--

CREATE TABLE core.bill_document (
    bill_id uuid NOT NULL,
    document_id uuid NOT NULL,
    relation text DEFAULT 'text'::text NOT NULL
);


ALTER TABLE core.bill_document OWNER TO cbwinslow;

--
-- Name: bill_identifier; Type: TABLE; Schema: core; Owner: cbwinslow
--

CREATE TABLE core.bill_identifier (
    bill_id uuid NOT NULL,
    namespace text NOT NULL,
    external_id text NOT NULL,
    source_artifact_id uuid,
    source_payload_id uuid,
    source_url text,
    metadata jsonb DEFAULT '{}'::jsonb NOT NULL,
    CONSTRAINT bill_identifier_check CHECK (((source_artifact_id IS NOT NULL) OR (source_payload_id IS NOT NULL)))
);


ALTER TABLE core.bill_identifier OWNER TO cbwinslow;

--
-- Name: bill_sponsorship; Type: TABLE; Schema: core; Owner: cbwinslow
--

CREATE TABLE core.bill_sponsorship (
    bill_sponsorship_id uuid DEFAULT gen_random_uuid() NOT NULL,
    bill_id uuid NOT NULL,
    person_id uuid,
    member_namespace text DEFAULT 'bioguide'::text NOT NULL,
    member_external_id text NOT NULL,
    role text NOT NULL,
    source_artifact_id uuid,
    source_payload_id uuid,
    source_member text,
    metadata jsonb DEFAULT '{}'::jsonb NOT NULL,
    CONSTRAINT bill_sponsorship_check CHECK (((source_artifact_id IS NOT NULL) OR (source_payload_id IS NOT NULL))),
    CONSTRAINT bill_sponsorship_role_check CHECK ((role = ANY (ARRAY['sponsor'::text, 'cosponsor'::text])))
);


ALTER TABLE core.bill_sponsorship OWNER TO cbwinslow;

--
-- Name: bill_subject; Type: TABLE; Schema: core; Owner: cbwinslow
--

CREATE TABLE core.bill_subject (
    bill_subject_id uuid DEFAULT gen_random_uuid() NOT NULL,
    bill_id uuid NOT NULL,
    namespace text DEFAULT 'congress.gov.subject'::text NOT NULL,
    external_id text NOT NULL,
    label text NOT NULL,
    source_artifact_id uuid,
    source_payload_id uuid,
    source_member text,
    metadata jsonb DEFAULT '{}'::jsonb NOT NULL,
    CONSTRAINT bill_subject_check CHECK (((source_artifact_id IS NOT NULL) OR (source_payload_id IS NOT NULL)))
);


ALTER TABLE core.bill_subject OWNER TO cbwinslow;

--
-- Name: document; Type: TABLE; Schema: core; Owner: cbwinslow
--

CREATE TABLE core.document (
    document_id uuid DEFAULT gen_random_uuid() NOT NULL,
    document_type text NOT NULL,
    source_key text NOT NULL,
    title text,
    published_at timestamp with time zone,
    language text DEFAULT 'en'::text NOT NULL,
    canonical_url text,
    checksum_sha256 text,
    metadata jsonb DEFAULT '{}'::jsonb NOT NULL,
    source_payload_id uuid,
    artifact_id uuid,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE core.document OWNER TO cbwinslow;

--
-- Name: document_chunk; Type: TABLE; Schema: core; Owner: cbwinslow
--

CREATE TABLE core.document_chunk (
    chunk_id uuid DEFAULT gen_random_uuid() NOT NULL,
    document_id uuid NOT NULL,
    ordinal integer NOT NULL,
    text text NOT NULL,
    token_count integer,
    checksum_sha256 text NOT NULL,
    metadata jsonb DEFAULT '{}'::jsonb NOT NULL,
    CONSTRAINT document_chunk_ordinal_check CHECK ((ordinal >= 0))
);


ALTER TABLE core.document_chunk OWNER TO cbwinslow;

--
-- Name: embedding; Type: TABLE; Schema: core; Owner: cbwinslow
--

CREATE TABLE core.embedding (
    embedding_id uuid DEFAULT gen_random_uuid() NOT NULL,
    chunk_id uuid NOT NULL,
    model text NOT NULL,
    dimensions integer NOT NULL,
    vector_values real[] NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT embedding_check CHECK ((cardinality(vector_values) = dimensions)),
    CONSTRAINT embedding_dimensions_check CHECK ((dimensions > 0))
);


ALTER TABLE core.embedding OWNER TO cbwinslow;

--
-- Name: geography; Type: TABLE; Schema: core; Owner: cbwinslow
--

CREATE TABLE core.geography (
    geography_id uuid DEFAULT gen_random_uuid() NOT NULL,
    geography_type text NOT NULL,
    geoid text NOT NULL,
    name text,
    parent_geoid text,
    state_fips text,
    county_fips text,
    metadata jsonb DEFAULT '{}'::jsonb NOT NULL
);


ALTER TABLE core.geography OWNER TO cbwinslow;

--
-- Name: geography_boundary; Type: TABLE; Schema: core; Owner: cbwinslow
--

CREATE TABLE core.geography_boundary (
    boundary_id uuid DEFAULT gen_random_uuid() NOT NULL,
    geography_id uuid NOT NULL,
    boundary_vintage integer NOT NULL,
    valid_from date,
    valid_to date,
    geom public.geometry(Geometry,4326) NOT NULL,
    source_payload_id uuid,
    source_artifact_id uuid
);


ALTER TABLE core.geography_boundary OWNER TO cbwinslow;

--
-- Name: instrument; Type: TABLE; Schema: core; Owner: cbwinslow
--

CREATE TABLE core.instrument (
    instrument_id uuid DEFAULT gen_random_uuid() NOT NULL,
    instrument_type text NOT NULL,
    name text,
    currency text,
    metadata jsonb DEFAULT '{}'::jsonb NOT NULL
);


ALTER TABLE core.instrument OWNER TO cbwinslow;

--
-- Name: instrument_symbol; Type: TABLE; Schema: core; Owner: cbwinslow
--

CREATE TABLE core.instrument_symbol (
    instrument_id uuid NOT NULL,
    symbol text NOT NULL,
    exchange text DEFAULT ''::text NOT NULL,
    valid_from date NOT NULL,
    valid_to date
);


ALTER TABLE core.instrument_symbol OWNER TO cbwinslow;

--
-- Name: jurisdiction; Type: TABLE; Schema: core; Owner: cbwinslow
--

CREATE TABLE core.jurisdiction (
    jurisdiction_id text NOT NULL,
    name text NOT NULL,
    classification text NOT NULL,
    metadata jsonb DEFAULT '{}'::jsonb NOT NULL
);


ALTER TABLE core.jurisdiction OWNER TO cbwinslow;

--
-- Name: legislative_session; Type: TABLE; Schema: core; Owner: cbwinslow
--

CREATE TABLE core.legislative_session (
    legislative_session_id uuid DEFAULT gen_random_uuid() NOT NULL,
    jurisdiction_id text NOT NULL,
    identifier text NOT NULL,
    name text,
    classification text,
    starts_on date,
    ends_on date,
    active boolean,
    source_artifact_id uuid,
    source_payload_id uuid,
    metadata jsonb DEFAULT '{}'::jsonb NOT NULL,
    CONSTRAINT legislative_session_check CHECK (((source_artifact_id IS NOT NULL) OR (source_payload_id IS NOT NULL)))
);


ALTER TABLE core.legislative_session OWNER TO cbwinslow;

--
-- Name: membership; Type: TABLE; Schema: core; Owner: cbwinslow
--

CREATE TABLE core.membership (
    membership_id uuid DEFAULT gen_random_uuid() NOT NULL,
    person_id uuid NOT NULL,
    organization_id uuid NOT NULL,
    legislative_session_id uuid,
    role text NOT NULL,
    start_date date,
    end_date date,
    source_artifact_id uuid,
    source_payload_id uuid,
    metadata jsonb DEFAULT '{}'::jsonb NOT NULL,
    CONSTRAINT membership_check CHECK (((source_artifact_id IS NOT NULL) OR (source_payload_id IS NOT NULL)))
);


ALTER TABLE core.membership OWNER TO cbwinslow;

--
-- Name: organization; Type: TABLE; Schema: core; Owner: cbwinslow
--

CREATE TABLE core.organization (
    organization_id uuid DEFAULT gen_random_uuid() NOT NULL,
    organization_type text NOT NULL,
    name text NOT NULL,
    jurisdiction_geoid text,
    metadata jsonb DEFAULT '{}'::jsonb NOT NULL
);


ALTER TABLE core.organization OWNER TO cbwinslow;

--
-- Name: organization_identifier; Type: TABLE; Schema: core; Owner: cbwinslow
--

CREATE TABLE core.organization_identifier (
    organization_id uuid NOT NULL,
    namespace text NOT NULL,
    external_id text NOT NULL,
    metadata jsonb DEFAULT '{}'::jsonb NOT NULL
);


ALTER TABLE core.organization_identifier OWNER TO cbwinslow;

--
-- Name: person; Type: TABLE; Schema: core; Owner: cbwinslow
--

CREATE TABLE core.person (
    person_id uuid DEFAULT gen_random_uuid() NOT NULL,
    full_name text NOT NULL,
    given_name text,
    family_name text,
    metadata jsonb DEFAULT '{}'::jsonb NOT NULL
);


ALTER TABLE core.person OWNER TO cbwinslow;

--
-- Name: person_identifier; Type: TABLE; Schema: core; Owner: cbwinslow
--

CREATE TABLE core.person_identifier (
    person_id uuid NOT NULL,
    namespace text NOT NULL,
    external_id text NOT NULL,
    valid_from date,
    valid_to date
);


ALTER TABLE core.person_identifier OWNER TO cbwinslow;

--
-- Name: roll_call; Type: TABLE; Schema: core; Owner: cbwinslow
--

CREATE TABLE core.roll_call (
    roll_call_id uuid DEFAULT gen_random_uuid() NOT NULL,
    jurisdiction text NOT NULL,
    legislative_session text NOT NULL,
    chamber text,
    external_id text NOT NULL,
    occurred_at timestamp with time zone,
    question text,
    result text,
    metadata jsonb DEFAULT '{}'::jsonb NOT NULL,
    bill_id uuid,
    legislative_session_id uuid,
    organization_id uuid,
    ocd_id text
);


ALTER TABLE core.roll_call OWNER TO cbwinslow;

--
-- Name: acs_bulk_estimate; Type: TABLE; Schema: fact; Owner: cbwinslow
--

CREATE TABLE fact.acs_bulk_estimate (
    acs_bulk_estimate_id uuid DEFAULT gen_random_uuid() NOT NULL,
    release_year integer NOT NULL,
    geography_id uuid NOT NULL,
    table_id text NOT NULL,
    field_id text NOT NULL,
    measure text NOT NULL,
    value numeric,
    source_artifact_id uuid NOT NULL,
    source_ordinal bigint NOT NULL,
    CONSTRAINT acs_bulk_estimate_measure_check CHECK ((measure = ANY (ARRAY['estimate'::text, 'margin_of_error'::text])))
);


ALTER TABLE fact.acs_bulk_estimate OWNER TO cbwinslow;

--
-- Name: business_pattern; Type: TABLE; Schema: fact; Owner: cbwinslow
--

CREATE TABLE fact.business_pattern (
    business_pattern_id uuid DEFAULT gen_random_uuid() NOT NULL,
    release_year integer NOT NULL,
    geography_id uuid NOT NULL,
    naics text NOT NULL,
    legal_form text DEFAULT ''::text NOT NULL,
    establishments bigint,
    employment bigint,
    first_quarter_payroll numeric,
    annual_payroll numeric,
    flags jsonb DEFAULT '{}'::jsonb NOT NULL,
    source_artifact_id uuid NOT NULL,
    source_member text NOT NULL,
    source_ordinal bigint NOT NULL,
    loaded_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE fact.business_pattern OWNER TO cbwinslow;

--
-- Name: decennial_dhc_value; Type: TABLE; Schema: fact; Owner: cbwinslow
--

CREATE TABLE fact.decennial_dhc_value (
    dhc_value_id uuid DEFAULT gen_random_uuid() NOT NULL,
    release_year integer NOT NULL,
    geography_id uuid NOT NULL,
    table_id text NOT NULL,
    variable_id text NOT NULL,
    value bigint,
    source_artifact_id uuid NOT NULL,
    source_member text NOT NULL,
    source_ordinal bigint NOT NULL
);


ALTER TABLE fact.decennial_dhc_value OWNER TO cbwinslow;

--
-- Name: market_bar; Type: TABLE; Schema: fact; Owner: cbwinslow
--

CREATE TABLE fact.market_bar (
    instrument_id uuid NOT NULL,
    trade_date date NOT NULL,
    "interval" text DEFAULT '1d'::text NOT NULL,
    open numeric,
    high numeric,
    low numeric,
    close numeric,
    adjusted_close numeric,
    volume numeric,
    source_payload_id uuid NOT NULL
);


ALTER TABLE fact.market_bar OWNER TO cbwinslow;

--
-- Name: measurement; Type: TABLE; Schema: fact; Owner: cbwinslow
--

CREATE TABLE fact.measurement (
    measurement_id uuid DEFAULT gen_random_uuid() NOT NULL,
    dataset_id text NOT NULL,
    field_id text NOT NULL,
    geography_id uuid,
    period_start date NOT NULL,
    period_end date,
    vintage_date date,
    value_numeric numeric,
    value_text text,
    unit text,
    margin_of_error numeric,
    flags jsonb DEFAULT '{}'::jsonb NOT NULL,
    source_payload_id uuid NOT NULL
);


ALTER TABLE fact.measurement OWNER TO cbwinslow;

--
-- Name: member_vote; Type: TABLE; Schema: fact; Owner: cbwinslow
--

CREATE TABLE fact.member_vote (
    roll_call_id uuid NOT NULL,
    person_id uuid NOT NULL,
    "position" text NOT NULL,
    source_payload_id uuid,
    source_artifact_id uuid,
    CONSTRAINT member_vote_source_evidence CHECK (((source_artifact_id IS NOT NULL) OR (source_payload_id IS NOT NULL)))
);


ALTER TABLE fact.member_vote OWNER TO cbwinslow;

--
-- Name: population_estimate; Type: TABLE; Schema: fact; Owner: cbwinslow
--

CREATE TABLE fact.population_estimate (
    population_estimate_id uuid DEFAULT gen_random_uuid() NOT NULL,
    release_vintage integer NOT NULL,
    estimate_year integer NOT NULL,
    geography_id uuid NOT NULL,
    population bigint NOT NULL,
    source_artifact_id uuid NOT NULL,
    source_member text NOT NULL,
    source_ordinal bigint NOT NULL,
    loaded_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE fact.population_estimate OWNER TO cbwinslow;

--
-- Name: artifact; Type: TABLE; Schema: ingest; Owner: cbwinslow
--

CREATE TABLE ingest.artifact (
    artifact_id uuid DEFAULT gen_random_uuid() NOT NULL,
    dataset_id text NOT NULL,
    remote_url text NOT NULL,
    local_path text NOT NULL,
    artifact_key text NOT NULL,
    period_start date,
    period_end date,
    content_type text,
    bytes_downloaded bigint,
    checksum_sha256 text,
    status text NOT NULL,
    discovered_at timestamp with time zone DEFAULT now() NOT NULL,
    downloaded_at timestamp with time zone,
    loaded_at timestamp with time zone,
    metadata jsonb DEFAULT '{}'::jsonb NOT NULL,
    error_message text,
    CONSTRAINT artifact_status_check CHECK ((status = ANY (ARRAY['planned'::text, 'downloading'::text, 'downloaded'::text, 'loaded'::text, 'failed'::text, 'skipped'::text])))
);


ALTER TABLE ingest.artifact OWNER TO cbwinslow;

--
-- Name: cursor; Type: TABLE; Schema: ingest; Owner: cbwinslow
--

CREATE TABLE ingest.cursor (
    plan_id text NOT NULL,
    cursor jsonb DEFAULT '{}'::jsonb NOT NULL,
    successful_run_id uuid,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE ingest.cursor OWNER TO cbwinslow;

--
-- Name: identity_exception; Type: TABLE; Schema: ingest; Owner: cbwinslow
--

CREATE TABLE ingest.identity_exception (
    identity_exception_id uuid DEFAULT gen_random_uuid() NOT NULL,
    dataset_id text NOT NULL,
    run_id uuid NOT NULL,
    source_artifact_id uuid NOT NULL,
    congress integer NOT NULL,
    kind text NOT NULL,
    namespace text NOT NULL,
    external_id text NOT NULL,
    reason text NOT NULL,
    reference_count integer DEFAULT 1 NOT NULL,
    first_seen_at timestamp with time zone DEFAULT now() NOT NULL,
    last_seen_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT identity_exception_kind_check CHECK ((kind = 'voter'::text)),
    CONSTRAINT identity_exception_reference_count_check CHECK ((reference_count > 0))
);


ALTER TABLE ingest.identity_exception OWNER TO cbwinslow;

--
-- Name: raw_payload; Type: TABLE; Schema: ingest; Owner: cbwinslow
--

CREATE TABLE ingest.raw_payload (
    payload_id uuid DEFAULT gen_random_uuid() NOT NULL,
    run_id uuid NOT NULL,
    source_url text NOT NULL,
    fetched_at timestamp with time zone DEFAULT now() NOT NULL,
    http_status integer,
    content_type text,
    checksum_sha256 text NOT NULL,
    payload jsonb NOT NULL
);


ALTER TABLE ingest.raw_payload OWNER TO cbwinslow;

--
-- Name: resume_cursor; Type: TABLE; Schema: ingest; Owner: cbwinslow
--

CREATE TABLE ingest.resume_cursor (
    dataset_id text NOT NULL,
    cursor_key text NOT NULL,
    cursor jsonb DEFAULT '{}'::jsonb NOT NULL,
    source_artifact_id uuid,
    last_run_id uuid,
    state text NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT resume_cursor_state_check CHECK ((state = ANY (ARRAY['running'::text, 'paused'::text, 'complete'::text])))
);


ALTER TABLE ingest.resume_cursor OWNER TO cbwinslow;

--
-- Name: run; Type: TABLE; Schema: ingest; Owner: cbwinslow
--

CREATE TABLE ingest.run (
    run_id uuid DEFAULT gen_random_uuid() NOT NULL,
    dataset_id text NOT NULL,
    mode text NOT NULL,
    status text NOT NULL,
    started_at timestamp with time zone DEFAULT now() NOT NULL,
    finished_at timestamp with time zone,
    parameters jsonb DEFAULT '{}'::jsonb NOT NULL,
    record_count bigint DEFAULT 0 NOT NULL,
    error_message text,
    code_version text,
    CONSTRAINT run_mode_check CHECK ((mode = ANY (ARRAY['backfill'::text, 'incremental'::text, 'manual'::text, 'plan'::text]))),
    CONSTRAINT run_status_check CHECK ((status = ANY (ARRAY['running'::text, 'succeeded'::text, 'failed'::text, 'partial'::text])))
);


ALTER TABLE ingest.run OWNER TO cbwinslow;

--
-- Name: opencivicdata_bill; Type: FOREIGN TABLE; Schema: openstates_source; Owner: postgres
--

CREATE FOREIGN TABLE openstates_source.opencivicdata_bill (
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL,
    extras jsonb NOT NULL,
    id character varying(45) NOT NULL,
    identifier character varying(100) NOT NULL,
    title text NOT NULL,
    classification text[] NOT NULL,
    subject text[] NOT NULL,
    from_organization_id character varying(53),
    legislative_session_id uuid NOT NULL,
    first_action_date character varying(25),
    latest_action_date character varying(25),
    latest_action_description text NOT NULL,
    latest_passage_date character varying(25),
    citations jsonb NOT NULL
)
SERVER openstates_local
OPTIONS (
    schema_name 'public',
    table_name 'opencivicdata_bill'
);
ALTER FOREIGN TABLE ONLY openstates_source.opencivicdata_bill ALTER COLUMN created_at OPTIONS (
    column_name 'created_at'
);
ALTER FOREIGN TABLE ONLY openstates_source.opencivicdata_bill ALTER COLUMN updated_at OPTIONS (
    column_name 'updated_at'
);
ALTER FOREIGN TABLE ONLY openstates_source.opencivicdata_bill ALTER COLUMN extras OPTIONS (
    column_name 'extras'
);
ALTER FOREIGN TABLE ONLY openstates_source.opencivicdata_bill ALTER COLUMN id OPTIONS (
    column_name 'id'
);
ALTER FOREIGN TABLE ONLY openstates_source.opencivicdata_bill ALTER COLUMN identifier OPTIONS (
    column_name 'identifier'
);
ALTER FOREIGN TABLE ONLY openstates_source.opencivicdata_bill ALTER COLUMN title OPTIONS (
    column_name 'title'
);
ALTER FOREIGN TABLE ONLY openstates_source.opencivicdata_bill ALTER COLUMN classification OPTIONS (
    column_name 'classification'
);
ALTER FOREIGN TABLE ONLY openstates_source.opencivicdata_bill ALTER COLUMN subject OPTIONS (
    column_name 'subject'
);
ALTER FOREIGN TABLE ONLY openstates_source.opencivicdata_bill ALTER COLUMN from_organization_id OPTIONS (
    column_name 'from_organization_id'
);
ALTER FOREIGN TABLE ONLY openstates_source.opencivicdata_bill ALTER COLUMN legislative_session_id OPTIONS (
    column_name 'legislative_session_id'
);
ALTER FOREIGN TABLE ONLY openstates_source.opencivicdata_bill ALTER COLUMN first_action_date OPTIONS (
    column_name 'first_action_date'
);
ALTER FOREIGN TABLE ONLY openstates_source.opencivicdata_bill ALTER COLUMN latest_action_date OPTIONS (
    column_name 'latest_action_date'
);
ALTER FOREIGN TABLE ONLY openstates_source.opencivicdata_bill ALTER COLUMN latest_action_description OPTIONS (
    column_name 'latest_action_description'
);
ALTER FOREIGN TABLE ONLY openstates_source.opencivicdata_bill ALTER COLUMN latest_passage_date OPTIONS (
    column_name 'latest_passage_date'
);
ALTER FOREIGN TABLE ONLY openstates_source.opencivicdata_bill ALTER COLUMN citations OPTIONS (
    column_name 'citations'
);


ALTER FOREIGN TABLE openstates_source.opencivicdata_bill OWNER TO postgres;

--
-- Name: opencivicdata_jurisdiction; Type: FOREIGN TABLE; Schema: openstates_source; Owner: postgres
--

CREATE FOREIGN TABLE openstates_source.opencivicdata_jurisdiction (
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL,
    extras jsonb NOT NULL,
    id character varying(300) NOT NULL,
    name character varying(300) NOT NULL,
    url character varying(2000) NOT NULL,
    classification character varying(50) NOT NULL,
    division_id character varying(300),
    latest_bill_update timestamp with time zone NOT NULL,
    latest_people_update timestamp with time zone NOT NULL
)
SERVER openstates_local
OPTIONS (
    schema_name 'public',
    table_name 'opencivicdata_jurisdiction'
);
ALTER FOREIGN TABLE ONLY openstates_source.opencivicdata_jurisdiction ALTER COLUMN created_at OPTIONS (
    column_name 'created_at'
);
ALTER FOREIGN TABLE ONLY openstates_source.opencivicdata_jurisdiction ALTER COLUMN updated_at OPTIONS (
    column_name 'updated_at'
);
ALTER FOREIGN TABLE ONLY openstates_source.opencivicdata_jurisdiction ALTER COLUMN extras OPTIONS (
    column_name 'extras'
);
ALTER FOREIGN TABLE ONLY openstates_source.opencivicdata_jurisdiction ALTER COLUMN id OPTIONS (
    column_name 'id'
);
ALTER FOREIGN TABLE ONLY openstates_source.opencivicdata_jurisdiction ALTER COLUMN name OPTIONS (
    column_name 'name'
);
ALTER FOREIGN TABLE ONLY openstates_source.opencivicdata_jurisdiction ALTER COLUMN url OPTIONS (
    column_name 'url'
);
ALTER FOREIGN TABLE ONLY openstates_source.opencivicdata_jurisdiction ALTER COLUMN classification OPTIONS (
    column_name 'classification'
);
ALTER FOREIGN TABLE ONLY openstates_source.opencivicdata_jurisdiction ALTER COLUMN division_id OPTIONS (
    column_name 'division_id'
);
ALTER FOREIGN TABLE ONLY openstates_source.opencivicdata_jurisdiction ALTER COLUMN latest_bill_update OPTIONS (
    column_name 'latest_bill_update'
);
ALTER FOREIGN TABLE ONLY openstates_source.opencivicdata_jurisdiction ALTER COLUMN latest_people_update OPTIONS (
    column_name 'latest_people_update'
);


ALTER FOREIGN TABLE openstates_source.opencivicdata_jurisdiction OWNER TO postgres;

--
-- Name: opencivicdata_legislativesession; Type: FOREIGN TABLE; Schema: openstates_source; Owner: postgres
--

CREATE FOREIGN TABLE openstates_source.opencivicdata_legislativesession (
    id uuid NOT NULL,
    identifier character varying(100) NOT NULL,
    name character varying(300) NOT NULL,
    classification character varying(100) NOT NULL,
    start_date character varying(10) NOT NULL,
    end_date character varying(10) NOT NULL,
    jurisdiction_id character varying(300) NOT NULL,
    active boolean NOT NULL
)
SERVER openstates_local
OPTIONS (
    schema_name 'public',
    table_name 'opencivicdata_legislativesession'
);
ALTER FOREIGN TABLE ONLY openstates_source.opencivicdata_legislativesession ALTER COLUMN id OPTIONS (
    column_name 'id'
);
ALTER FOREIGN TABLE ONLY openstates_source.opencivicdata_legislativesession ALTER COLUMN identifier OPTIONS (
    column_name 'identifier'
);
ALTER FOREIGN TABLE ONLY openstates_source.opencivicdata_legislativesession ALTER COLUMN name OPTIONS (
    column_name 'name'
);
ALTER FOREIGN TABLE ONLY openstates_source.opencivicdata_legislativesession ALTER COLUMN classification OPTIONS (
    column_name 'classification'
);
ALTER FOREIGN TABLE ONLY openstates_source.opencivicdata_legislativesession ALTER COLUMN start_date OPTIONS (
    column_name 'start_date'
);
ALTER FOREIGN TABLE ONLY openstates_source.opencivicdata_legislativesession ALTER COLUMN end_date OPTIONS (
    column_name 'end_date'
);
ALTER FOREIGN TABLE ONLY openstates_source.opencivicdata_legislativesession ALTER COLUMN jurisdiction_id OPTIONS (
    column_name 'jurisdiction_id'
);
ALTER FOREIGN TABLE ONLY openstates_source.opencivicdata_legislativesession ALTER COLUMN active OPTIONS (
    column_name 'active'
);


ALTER FOREIGN TABLE openstates_source.opencivicdata_legislativesession OWNER TO postgres;

--
-- Name: bill; Type: VIEW; Schema: leg; Owner: cbwinslow
--

CREATE VIEW leg.bill AS
 SELECT bill.id AS entity_id,
    bill.id AS ocd_id,
    'openstates'::text AS source_system,
    jurisdiction.id AS jurisdiction_id,
    session.identifier AS legislative_session_identifier,
    bill.identifier,
    bill.title,
    bill.classification,
    bill.subject,
    bill.first_action_date,
    bill.latest_action_date,
    bill.latest_action_description,
    bill.extras AS metadata
   FROM ((openstates_source.opencivicdata_bill bill
     JOIN openstates_source.opencivicdata_legislativesession session ON ((session.id = bill.legislative_session_id)))
     JOIN openstates_source.opencivicdata_jurisdiction jurisdiction ON (((jurisdiction.id)::text = (session.jurisdiction_id)::text)))
UNION ALL
 SELECT (bill.bill_id)::text AS entity_id,
    bill.ocd_id,
    'opendiscourse'::text AS source_system,
    COALESCE(session.jurisdiction_id, bill.jurisdiction) AS jurisdiction_id,
    COALESCE(session.identifier, bill.legislative_session) AS legislative_session_identifier,
    ((bill.bill_type || ' '::text) || bill.bill_number) AS identifier,
    bill.title,
    ARRAY[bill.bill_type] AS classification,
    ARRAY[]::text[] AS subject,
    (bill.introduced_date)::text AS first_action_date,
    (bill.latest_action_date)::text AS latest_action_date,
    bill.latest_action AS latest_action_description,
    bill.metadata
   FROM (core.bill bill
     LEFT JOIN core.legislative_session session ON ((session.legislative_session_id = bill.legislative_session_id)));


ALTER VIEW leg.bill OWNER TO cbwinslow;

--
-- Name: opencivicdata_person; Type: FOREIGN TABLE; Schema: openstates_source; Owner: postgres
--

CREATE FOREIGN TABLE openstates_source.opencivicdata_person (
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL,
    extras jsonb NOT NULL,
    id character varying(47) NOT NULL,
    name character varying(300) NOT NULL,
    family_name character varying(100) NOT NULL,
    given_name character varying(100) NOT NULL,
    image character varying(2000) NOT NULL,
    gender character varying(100) NOT NULL,
    biography text NOT NULL,
    birth_date character varying(10) NOT NULL,
    death_date character varying(10) NOT NULL,
    primary_party character varying(100) NOT NULL,
    current_jurisdiction_id character varying(300),
    "current_role" jsonb,
    email character varying(300) NOT NULL
)
SERVER openstates_local
OPTIONS (
    schema_name 'public',
    table_name 'opencivicdata_person'
);
ALTER FOREIGN TABLE ONLY openstates_source.opencivicdata_person ALTER COLUMN created_at OPTIONS (
    column_name 'created_at'
);
ALTER FOREIGN TABLE ONLY openstates_source.opencivicdata_person ALTER COLUMN updated_at OPTIONS (
    column_name 'updated_at'
);
ALTER FOREIGN TABLE ONLY openstates_source.opencivicdata_person ALTER COLUMN extras OPTIONS (
    column_name 'extras'
);
ALTER FOREIGN TABLE ONLY openstates_source.opencivicdata_person ALTER COLUMN id OPTIONS (
    column_name 'id'
);
ALTER FOREIGN TABLE ONLY openstates_source.opencivicdata_person ALTER COLUMN name OPTIONS (
    column_name 'name'
);
ALTER FOREIGN TABLE ONLY openstates_source.opencivicdata_person ALTER COLUMN family_name OPTIONS (
    column_name 'family_name'
);
ALTER FOREIGN TABLE ONLY openstates_source.opencivicdata_person ALTER COLUMN given_name OPTIONS (
    column_name 'given_name'
);
ALTER FOREIGN TABLE ONLY openstates_source.opencivicdata_person ALTER COLUMN image OPTIONS (
    column_name 'image'
);
ALTER FOREIGN TABLE ONLY openstates_source.opencivicdata_person ALTER COLUMN gender OPTIONS (
    column_name 'gender'
);
ALTER FOREIGN TABLE ONLY openstates_source.opencivicdata_person ALTER COLUMN biography OPTIONS (
    column_name 'biography'
);
ALTER FOREIGN TABLE ONLY openstates_source.opencivicdata_person ALTER COLUMN birth_date OPTIONS (
    column_name 'birth_date'
);
ALTER FOREIGN TABLE ONLY openstates_source.opencivicdata_person ALTER COLUMN death_date OPTIONS (
    column_name 'death_date'
);
ALTER FOREIGN TABLE ONLY openstates_source.opencivicdata_person ALTER COLUMN primary_party OPTIONS (
    column_name 'primary_party'
);
ALTER FOREIGN TABLE ONLY openstates_source.opencivicdata_person ALTER COLUMN current_jurisdiction_id OPTIONS (
    column_name 'current_jurisdiction_id'
);
ALTER FOREIGN TABLE ONLY openstates_source.opencivicdata_person ALTER COLUMN "current_role" OPTIONS (
    column_name 'current_role'
);
ALTER FOREIGN TABLE ONLY openstates_source.opencivicdata_person ALTER COLUMN email OPTIONS (
    column_name 'email'
);


ALTER FOREIGN TABLE openstates_source.opencivicdata_person OWNER TO postgres;

--
-- Name: person; Type: VIEW; Schema: leg; Owner: cbwinslow
--

CREATE VIEW leg.person AS
 SELECT person.id AS entity_id,
    person.id AS ocd_id,
    'openstates'::text AS source_system,
    person.name,
    person.given_name,
    person.family_name,
    person.current_jurisdiction_id,
    person.extras AS metadata
   FROM openstates_source.opencivicdata_person person
UNION ALL
 SELECT (person.person_id)::text AS entity_id,
    identifier.external_id AS ocd_id,
    'opendiscourse'::text AS source_system,
    person.full_name AS name,
    person.given_name,
    person.family_name,
    NULL::text AS current_jurisdiction_id,
    person.metadata
   FROM (core.person person
     LEFT JOIN LATERAL ( SELECT person_identifier.external_id
           FROM core.person_identifier
          WHERE ((person_identifier.person_id = person.person_id) AND (person_identifier.namespace = 'ocd'::text))
          ORDER BY person_identifier.valid_from
         LIMIT 1) identifier ON (true));


ALTER VIEW leg.person OWNER TO cbwinslow;

--
-- Name: stg_geography; Type: VIEW; Schema: mart; Owner: cbwinslow
--

CREATE VIEW mart.stg_geography AS
 SELECT geography_id,
    geography_type,
    geoid,
    name,
    state_fips,
    county_fips
   FROM core.geography;


ALTER VIEW mart.stg_geography OWNER TO cbwinslow;

--
-- Name: stg_measurements; Type: VIEW; Schema: mart; Owner: cbwinslow
--

CREATE VIEW mart.stg_measurements AS
 SELECT measurement_id,
    dataset_id,
    field_id,
    geography_id,
    period_start,
    period_end,
    vintage_date,
    value_numeric,
    unit
   FROM fact.measurement;


ALTER VIEW mart.stg_measurements OWNER TO cbwinslow;

--
-- Name: mart_geography_year_measurement; Type: VIEW; Schema: mart; Owner: cbwinslow
--

CREATE VIEW mart.mart_geography_year_measurement AS
 SELECT g.geography_id,
    g.geography_type,
    g.geoid,
    g.name AS geography_name,
    g.state_fips,
    g.county_fips,
    m.dataset_id,
    m.field_id,
    (EXTRACT(year FROM m.period_start))::integer AS period_year,
    m.unit,
    avg(m.value_numeric) AS value_numeric_avg,
    min(m.value_numeric) AS value_numeric_min,
    max(m.value_numeric) AS value_numeric_max,
    count(*) AS observation_count
   FROM (mart.stg_measurements m
     LEFT JOIN mart.stg_geography g ON ((g.geography_id = m.geography_id)))
  GROUP BY g.geography_id, g.geography_type, g.geoid, g.name, g.state_fips, g.county_fips, m.dataset_id, m.field_id, (EXTRACT(year FROM m.period_start)), m.unit;


ALTER VIEW mart.mart_geography_year_measurement OWNER TO cbwinslow;

--
-- Name: stg_bills; Type: VIEW; Schema: mart; Owner: cbwinslow
--

CREATE VIEW mart.stg_bills AS
 SELECT bill_id,
    jurisdiction,
    legislative_session,
    bill_type,
    bill_number,
    title,
    introduced_date,
    latest_action_date,
    latest_action
   FROM core.bill;


ALTER VIEW mart.stg_bills OWNER TO cbwinslow;

--
-- Name: stg_member_votes; Type: VIEW; Schema: mart; Owner: cbwinslow
--

CREATE VIEW mart.stg_member_votes AS
 SELECT roll_call_id,
    person_id,
    "position"
   FROM fact.member_vote;


ALTER VIEW mart.stg_member_votes OWNER TO cbwinslow;

--
-- Name: stg_roll_calls; Type: VIEW; Schema: mart; Owner: cbwinslow
--

CREATE VIEW mart.stg_roll_calls AS
 SELECT roll_call_id,
    bill_id,
    jurisdiction,
    legislative_session,
    chamber,
    external_id AS roll_call_external_id,
    occurred_at,
    question,
    result
   FROM core.roll_call;


ALTER VIEW mart.stg_roll_calls OWNER TO cbwinslow;

--
-- Name: mart_roll_call_results; Type: VIEW; Schema: mart; Owner: cbwinslow
--

CREATE VIEW mart.mart_roll_call_results AS
 WITH votes AS (
         SELECT stg_member_votes.roll_call_id,
            count(*) FILTER (WHERE (stg_member_votes."position" = 'yes'::text)) AS yea_count,
            count(*) FILTER (WHERE (stg_member_votes."position" = 'no'::text)) AS nay_count,
            count(*) FILTER (WHERE (stg_member_votes."position" <> ALL (ARRAY['yes'::text, 'no'::text]))) AS other_count,
            count(*) AS total_votes
           FROM mart.stg_member_votes
          GROUP BY stg_member_votes.roll_call_id
        )
 SELECT rc.roll_call_id,
    rc.jurisdiction,
    rc.legislative_session,
    rc.chamber,
    rc.roll_call_external_id,
    rc.occurred_at,
    rc.question,
    rc.result,
    b.bill_id,
    b.bill_type,
    b.bill_number,
    b.title AS bill_title,
    b.introduced_date,
    COALESCE(v.yea_count, (0)::bigint) AS yea_count,
    COALESCE(v.nay_count, (0)::bigint) AS nay_count,
    COALESCE(v.other_count, (0)::bigint) AS other_count,
    COALESCE(v.total_votes, (0)::bigint) AS total_votes
   FROM ((mart.stg_roll_calls rc
     LEFT JOIN mart.stg_bills b ON ((b.bill_id = rc.bill_id)))
     LEFT JOIN votes v ON ((v.roll_call_id = rc.roll_call_id)));


ALTER VIEW mart.mart_roll_call_results OWNER TO cbwinslow;

--
-- Name: opencivicdata_billaction; Type: FOREIGN TABLE; Schema: openstates_source; Owner: postgres
--

CREATE FOREIGN TABLE openstates_source.opencivicdata_billaction (
    id uuid NOT NULL,
    description text NOT NULL,
    date character varying(25) NOT NULL,
    classification text[] NOT NULL,
    "order" integer NOT NULL,
    bill_id character varying(45) NOT NULL,
    organization_id character varying(53) NOT NULL
)
SERVER openstates_local
OPTIONS (
    schema_name 'public',
    table_name 'opencivicdata_billaction'
);
ALTER FOREIGN TABLE ONLY openstates_source.opencivicdata_billaction ALTER COLUMN id OPTIONS (
    column_name 'id'
);
ALTER FOREIGN TABLE ONLY openstates_source.opencivicdata_billaction ALTER COLUMN description OPTIONS (
    column_name 'description'
);
ALTER FOREIGN TABLE ONLY openstates_source.opencivicdata_billaction ALTER COLUMN date OPTIONS (
    column_name 'date'
);
ALTER FOREIGN TABLE ONLY openstates_source.opencivicdata_billaction ALTER COLUMN classification OPTIONS (
    column_name 'classification'
);
ALTER FOREIGN TABLE ONLY openstates_source.opencivicdata_billaction ALTER COLUMN "order" OPTIONS (
    column_name 'order'
);
ALTER FOREIGN TABLE ONLY openstates_source.opencivicdata_billaction ALTER COLUMN bill_id OPTIONS (
    column_name 'bill_id'
);
ALTER FOREIGN TABLE ONLY openstates_source.opencivicdata_billaction ALTER COLUMN organization_id OPTIONS (
    column_name 'organization_id'
);


ALTER FOREIGN TABLE openstates_source.opencivicdata_billaction OWNER TO postgres;

--
-- Name: opencivicdata_billdocument; Type: FOREIGN TABLE; Schema: openstates_source; Owner: postgres
--

CREATE FOREIGN TABLE openstates_source.opencivicdata_billdocument (
    id uuid NOT NULL,
    note character varying(300) NOT NULL,
    date character varying(10) NOT NULL,
    bill_id character varying(45) NOT NULL,
    extras jsonb NOT NULL,
    classification character varying(100) NOT NULL
)
SERVER openstates_local
OPTIONS (
    schema_name 'public',
    table_name 'opencivicdata_billdocument'
);
ALTER FOREIGN TABLE ONLY openstates_source.opencivicdata_billdocument ALTER COLUMN id OPTIONS (
    column_name 'id'
);
ALTER FOREIGN TABLE ONLY openstates_source.opencivicdata_billdocument ALTER COLUMN note OPTIONS (
    column_name 'note'
);
ALTER FOREIGN TABLE ONLY openstates_source.opencivicdata_billdocument ALTER COLUMN date OPTIONS (
    column_name 'date'
);
ALTER FOREIGN TABLE ONLY openstates_source.opencivicdata_billdocument ALTER COLUMN bill_id OPTIONS (
    column_name 'bill_id'
);
ALTER FOREIGN TABLE ONLY openstates_source.opencivicdata_billdocument ALTER COLUMN extras OPTIONS (
    column_name 'extras'
);
ALTER FOREIGN TABLE ONLY openstates_source.opencivicdata_billdocument ALTER COLUMN classification OPTIONS (
    column_name 'classification'
);


ALTER FOREIGN TABLE openstates_source.opencivicdata_billdocument OWNER TO postgres;

--
-- Name: opencivicdata_billsponsorship; Type: FOREIGN TABLE; Schema: openstates_source; Owner: postgres
--

CREATE FOREIGN TABLE openstates_source.opencivicdata_billsponsorship (
    id uuid NOT NULL,
    name character varying(2000) NOT NULL,
    entity_type character varying(20) NOT NULL,
    "primary" boolean NOT NULL,
    classification character varying(100) NOT NULL,
    bill_id character varying(45) NOT NULL,
    organization_id character varying(53),
    person_id character varying(47)
)
SERVER openstates_local
OPTIONS (
    schema_name 'public',
    table_name 'opencivicdata_billsponsorship'
);
ALTER FOREIGN TABLE ONLY openstates_source.opencivicdata_billsponsorship ALTER COLUMN id OPTIONS (
    column_name 'id'
);
ALTER FOREIGN TABLE ONLY openstates_source.opencivicdata_billsponsorship ALTER COLUMN name OPTIONS (
    column_name 'name'
);
ALTER FOREIGN TABLE ONLY openstates_source.opencivicdata_billsponsorship ALTER COLUMN entity_type OPTIONS (
    column_name 'entity_type'
);
ALTER FOREIGN TABLE ONLY openstates_source.opencivicdata_billsponsorship ALTER COLUMN "primary" OPTIONS (
    column_name 'primary'
);
ALTER FOREIGN TABLE ONLY openstates_source.opencivicdata_billsponsorship ALTER COLUMN classification OPTIONS (
    column_name 'classification'
);
ALTER FOREIGN TABLE ONLY openstates_source.opencivicdata_billsponsorship ALTER COLUMN bill_id OPTIONS (
    column_name 'bill_id'
);
ALTER FOREIGN TABLE ONLY openstates_source.opencivicdata_billsponsorship ALTER COLUMN organization_id OPTIONS (
    column_name 'organization_id'
);
ALTER FOREIGN TABLE ONLY openstates_source.opencivicdata_billsponsorship ALTER COLUMN person_id OPTIONS (
    column_name 'person_id'
);


ALTER FOREIGN TABLE openstates_source.opencivicdata_billsponsorship OWNER TO postgres;

--
-- Name: opencivicdata_organization; Type: FOREIGN TABLE; Schema: openstates_source; Owner: postgres
--

CREATE FOREIGN TABLE openstates_source.opencivicdata_organization (
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL,
    extras jsonb NOT NULL,
    id character varying(53) NOT NULL,
    name character varying(300) NOT NULL,
    classification character varying(100) NOT NULL,
    jurisdiction_id character varying(300),
    parent_id character varying(53),
    links jsonb NOT NULL,
    sources jsonb NOT NULL,
    other_names jsonb NOT NULL
)
SERVER openstates_local
OPTIONS (
    schema_name 'public',
    table_name 'opencivicdata_organization'
);
ALTER FOREIGN TABLE ONLY openstates_source.opencivicdata_organization ALTER COLUMN created_at OPTIONS (
    column_name 'created_at'
);
ALTER FOREIGN TABLE ONLY openstates_source.opencivicdata_organization ALTER COLUMN updated_at OPTIONS (
    column_name 'updated_at'
);
ALTER FOREIGN TABLE ONLY openstates_source.opencivicdata_organization ALTER COLUMN extras OPTIONS (
    column_name 'extras'
);
ALTER FOREIGN TABLE ONLY openstates_source.opencivicdata_organization ALTER COLUMN id OPTIONS (
    column_name 'id'
);
ALTER FOREIGN TABLE ONLY openstates_source.opencivicdata_organization ALTER COLUMN name OPTIONS (
    column_name 'name'
);
ALTER FOREIGN TABLE ONLY openstates_source.opencivicdata_organization ALTER COLUMN classification OPTIONS (
    column_name 'classification'
);
ALTER FOREIGN TABLE ONLY openstates_source.opencivicdata_organization ALTER COLUMN jurisdiction_id OPTIONS (
    column_name 'jurisdiction_id'
);
ALTER FOREIGN TABLE ONLY openstates_source.opencivicdata_organization ALTER COLUMN parent_id OPTIONS (
    column_name 'parent_id'
);
ALTER FOREIGN TABLE ONLY openstates_source.opencivicdata_organization ALTER COLUMN links OPTIONS (
    column_name 'links'
);
ALTER FOREIGN TABLE ONLY openstates_source.opencivicdata_organization ALTER COLUMN sources OPTIONS (
    column_name 'sources'
);
ALTER FOREIGN TABLE ONLY openstates_source.opencivicdata_organization ALTER COLUMN other_names OPTIONS (
    column_name 'other_names'
);


ALTER FOREIGN TABLE openstates_source.opencivicdata_organization OWNER TO postgres;

--
-- Name: opencivicdata_personidentifier; Type: FOREIGN TABLE; Schema: openstates_source; Owner: postgres
--

CREATE FOREIGN TABLE openstates_source.opencivicdata_personidentifier (
    id uuid NOT NULL,
    identifier character varying(300) NOT NULL,
    scheme character varying(300) NOT NULL,
    person_id character varying(47) NOT NULL
)
SERVER openstates_local
OPTIONS (
    schema_name 'public',
    table_name 'opencivicdata_personidentifier'
);
ALTER FOREIGN TABLE ONLY openstates_source.opencivicdata_personidentifier ALTER COLUMN id OPTIONS (
    column_name 'id'
);
ALTER FOREIGN TABLE ONLY openstates_source.opencivicdata_personidentifier ALTER COLUMN identifier OPTIONS (
    column_name 'identifier'
);
ALTER FOREIGN TABLE ONLY openstates_source.opencivicdata_personidentifier ALTER COLUMN scheme OPTIONS (
    column_name 'scheme'
);
ALTER FOREIGN TABLE ONLY openstates_source.opencivicdata_personidentifier ALTER COLUMN person_id OPTIONS (
    column_name 'person_id'
);


ALTER FOREIGN TABLE openstates_source.opencivicdata_personidentifier OWNER TO postgres;

--
-- Name: opencivicdata_personvote; Type: FOREIGN TABLE; Schema: openstates_source; Owner: postgres
--

CREATE FOREIGN TABLE openstates_source.opencivicdata_personvote (
    id uuid NOT NULL,
    option character varying(50) NOT NULL,
    voter_name character varying(300) NOT NULL,
    note text NOT NULL,
    vote_event_id character varying(45) NOT NULL,
    voter_id character varying(47)
)
SERVER openstates_local
OPTIONS (
    schema_name 'public',
    table_name 'opencivicdata_personvote'
);
ALTER FOREIGN TABLE ONLY openstates_source.opencivicdata_personvote ALTER COLUMN id OPTIONS (
    column_name 'id'
);
ALTER FOREIGN TABLE ONLY openstates_source.opencivicdata_personvote ALTER COLUMN option OPTIONS (
    column_name 'option'
);
ALTER FOREIGN TABLE ONLY openstates_source.opencivicdata_personvote ALTER COLUMN voter_name OPTIONS (
    column_name 'voter_name'
);
ALTER FOREIGN TABLE ONLY openstates_source.opencivicdata_personvote ALTER COLUMN note OPTIONS (
    column_name 'note'
);
ALTER FOREIGN TABLE ONLY openstates_source.opencivicdata_personvote ALTER COLUMN vote_event_id OPTIONS (
    column_name 'vote_event_id'
);
ALTER FOREIGN TABLE ONLY openstates_source.opencivicdata_personvote ALTER COLUMN voter_id OPTIONS (
    column_name 'voter_id'
);


ALTER FOREIGN TABLE openstates_source.opencivicdata_personvote OWNER TO postgres;

--
-- Name: opencivicdata_voteevent; Type: FOREIGN TABLE; Schema: openstates_source; Owner: postgres
--

CREATE FOREIGN TABLE openstates_source.opencivicdata_voteevent (
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL,
    extras jsonb NOT NULL,
    id character varying(45) NOT NULL,
    identifier character varying(300) NOT NULL,
    motion_text text NOT NULL,
    motion_classification text[] NOT NULL,
    start_date character varying(25) NOT NULL,
    result character varying(50) NOT NULL,
    bill_id character varying(45),
    bill_action_id uuid,
    legislative_session_id uuid NOT NULL,
    organization_id character varying(53) NOT NULL,
    "order" integer NOT NULL,
    dedupe_key character varying(500)
)
SERVER openstates_local
OPTIONS (
    schema_name 'public',
    table_name 'opencivicdata_voteevent'
);
ALTER FOREIGN TABLE ONLY openstates_source.opencivicdata_voteevent ALTER COLUMN created_at OPTIONS (
    column_name 'created_at'
);
ALTER FOREIGN TABLE ONLY openstates_source.opencivicdata_voteevent ALTER COLUMN updated_at OPTIONS (
    column_name 'updated_at'
);
ALTER FOREIGN TABLE ONLY openstates_source.opencivicdata_voteevent ALTER COLUMN extras OPTIONS (
    column_name 'extras'
);
ALTER FOREIGN TABLE ONLY openstates_source.opencivicdata_voteevent ALTER COLUMN id OPTIONS (
    column_name 'id'
);
ALTER FOREIGN TABLE ONLY openstates_source.opencivicdata_voteevent ALTER COLUMN identifier OPTIONS (
    column_name 'identifier'
);
ALTER FOREIGN TABLE ONLY openstates_source.opencivicdata_voteevent ALTER COLUMN motion_text OPTIONS (
    column_name 'motion_text'
);
ALTER FOREIGN TABLE ONLY openstates_source.opencivicdata_voteevent ALTER COLUMN motion_classification OPTIONS (
    column_name 'motion_classification'
);
ALTER FOREIGN TABLE ONLY openstates_source.opencivicdata_voteevent ALTER COLUMN start_date OPTIONS (
    column_name 'start_date'
);
ALTER FOREIGN TABLE ONLY openstates_source.opencivicdata_voteevent ALTER COLUMN result OPTIONS (
    column_name 'result'
);
ALTER FOREIGN TABLE ONLY openstates_source.opencivicdata_voteevent ALTER COLUMN bill_id OPTIONS (
    column_name 'bill_id'
);
ALTER FOREIGN TABLE ONLY openstates_source.opencivicdata_voteevent ALTER COLUMN bill_action_id OPTIONS (
    column_name 'bill_action_id'
);
ALTER FOREIGN TABLE ONLY openstates_source.opencivicdata_voteevent ALTER COLUMN legislative_session_id OPTIONS (
    column_name 'legislative_session_id'
);
ALTER FOREIGN TABLE ONLY openstates_source.opencivicdata_voteevent ALTER COLUMN organization_id OPTIONS (
    column_name 'organization_id'
);
ALTER FOREIGN TABLE ONLY openstates_source.opencivicdata_voteevent ALTER COLUMN "order" OPTIONS (
    column_name 'order'
);
ALTER FOREIGN TABLE ONLY openstates_source.opencivicdata_voteevent ALTER COLUMN dedupe_key OPTIONS (
    column_name 'dedupe_key'
);


ALTER FOREIGN TABLE openstates_source.opencivicdata_voteevent OWNER TO postgres;

--
-- Name: alembic_version; Type: TABLE; Schema: public; Owner: cbwinslow
--

CREATE TABLE public.alembic_version (
    version_num character varying(32) NOT NULL
);


ALTER TABLE public.alembic_version OWNER TO cbwinslow;

--
-- Name: acs_bulk_row; Type: TABLE; Schema: stage; Owner: cbwinslow
--

CREATE TABLE stage.acs_bulk_row (
    artifact_id uuid NOT NULL,
    source_ordinal bigint NOT NULL,
    release_year integer NOT NULL,
    table_id text NOT NULL,
    geography_type text NOT NULL,
    geoid text NOT NULL,
    raw jsonb NOT NULL
);


ALTER TABLE stage.acs_bulk_row OWNER TO cbwinslow;

--
-- Name: cbp_row; Type: TABLE; Schema: stage; Owner: cbwinslow
--

CREATE TABLE stage.cbp_row (
    artifact_id uuid NOT NULL,
    source_member text NOT NULL,
    source_ordinal bigint NOT NULL,
    geography_level text NOT NULL,
    raw jsonb NOT NULL,
    staged_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE stage.cbp_row OWNER TO cbwinslow;

--
-- Name: dhc_geo_row; Type: TABLE; Schema: stage; Owner: cbwinslow
--

CREATE TABLE stage.dhc_geo_row (
    artifact_id uuid NOT NULL,
    source_member text NOT NULL,
    source_ordinal bigint NOT NULL,
    logrecno text NOT NULL,
    sumlev text NOT NULL,
    geoid text,
    raw jsonb NOT NULL
);


ALTER TABLE stage.dhc_geo_row OWNER TO cbwinslow;

--
-- Name: fec_row; Type: TABLE; Schema: stage; Owner: cbwinslow
--

CREATE TABLE stage.fec_row (
    artifact_id uuid NOT NULL,
    family text NOT NULL,
    cycle smallint NOT NULL,
    source_ordinal bigint NOT NULL,
    raw jsonb NOT NULL,
    staged_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE stage.fec_row OWNER TO cbwinslow;

--
-- Name: pep_row; Type: TABLE; Schema: stage; Owner: cbwinslow
--

CREATE TABLE stage.pep_row (
    artifact_id uuid NOT NULL,
    source_member text NOT NULL,
    source_ordinal bigint NOT NULL,
    geography_level text NOT NULL,
    raw jsonb NOT NULL,
    staged_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE stage.pep_row OWNER TO cbwinslow;

--
-- Name: tiger_feature; Type: TABLE; Schema: stage; Owner: cbwinslow
--

CREATE TABLE stage.tiger_feature (
    artifact_id uuid NOT NULL,
    layer text NOT NULL,
    source_ordinal bigint NOT NULL,
    geoid text NOT NULL,
    name text,
    state_fips text,
    county_fips text,
    raw jsonb NOT NULL,
    geom public.geometry(Geometry,4326) NOT NULL,
    staged_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE stage.tiger_feature OWNER TO cbwinslow;

--
-- Name: basket_item basket_item_pkey; Type: CONSTRAINT; Schema: catalog; Owner: cbwinslow
--

ALTER TABLE ONLY catalog.basket_item
    ADD CONSTRAINT basket_item_pkey PRIMARY KEY (basket_id, resource_id);


--
-- Name: basket basket_name_key; Type: CONSTRAINT; Schema: catalog; Owner: cbwinslow
--

ALTER TABLE ONLY catalog.basket
    ADD CONSTRAINT basket_name_key UNIQUE (name);


--
-- Name: basket basket_pkey; Type: CONSTRAINT; Schema: catalog; Owner: cbwinslow
--

ALTER TABLE ONLY catalog.basket
    ADD CONSTRAINT basket_pkey PRIMARY KEY (basket_id);


--
-- Name: dataset_field dataset_field_pkey; Type: CONSTRAINT; Schema: catalog; Owner: cbwinslow
--

ALTER TABLE ONLY catalog.dataset_field
    ADD CONSTRAINT dataset_field_pkey PRIMARY KEY (dataset_id, field_id, valid_from);


--
-- Name: dataset dataset_pkey; Type: CONSTRAINT; Schema: catalog; Owner: cbwinslow
--

ALTER TABLE ONLY catalog.dataset
    ADD CONSTRAINT dataset_pkey PRIMARY KEY (dataset_id);


--
-- Name: discovery discovery_pkey; Type: CONSTRAINT; Schema: catalog; Owner: cbwinslow
--

ALTER TABLE ONLY catalog.discovery
    ADD CONSTRAINT discovery_pkey PRIMARY KEY (discovery_id);


--
-- Name: plan plan_pkey; Type: CONSTRAINT; Schema: catalog; Owner: cbwinslow
--

ALTER TABLE ONLY catalog.plan
    ADD CONSTRAINT plan_pkey PRIMARY KEY (plan_id);


--
-- Name: provider provider_pkey; Type: CONSTRAINT; Schema: catalog; Owner: cbwinslow
--

ALTER TABLE ONLY catalog.provider
    ADD CONSTRAINT provider_pkey PRIMARY KEY (provider_id);


--
-- Name: resource resource_dataset_id_resource_key_key; Type: CONSTRAINT; Schema: catalog; Owner: cbwinslow
--

ALTER TABLE ONLY catalog.resource
    ADD CONSTRAINT resource_dataset_id_resource_key_key UNIQUE (dataset_id, resource_key);


--
-- Name: resource_field resource_field_pkey; Type: CONSTRAINT; Schema: catalog; Owner: cbwinslow
--

ALTER TABLE ONLY catalog.resource_field
    ADD CONSTRAINT resource_field_pkey PRIMARY KEY (resource_id, field_key);


--
-- Name: resource resource_pkey; Type: CONSTRAINT; Schema: catalog; Owner: cbwinslow
--

ALTER TABLE ONLY catalog.resource
    ADD CONSTRAINT resource_pkey PRIMARY KEY (resource_id);


--
-- Name: snapshot snapshot_dataset_id_checksum_sha256_key; Type: CONSTRAINT; Schema: catalog; Owner: cbwinslow
--

ALTER TABLE ONLY catalog.snapshot
    ADD CONSTRAINT snapshot_dataset_id_checksum_sha256_key UNIQUE (dataset_id, checksum_sha256);


--
-- Name: snapshot snapshot_pkey; Type: CONSTRAINT; Schema: catalog; Owner: cbwinslow
--

ALTER TABLE ONLY catalog.snapshot
    ADD CONSTRAINT snapshot_pkey PRIMARY KEY (snapshot_id);


--
-- Name: snapshot_resource snapshot_resource_pkey; Type: CONSTRAINT; Schema: catalog; Owner: cbwinslow
--

ALTER TABLE ONLY catalog.snapshot_resource
    ADD CONSTRAINT snapshot_resource_pkey PRIMARY KEY (snapshot_id, resource_id);


--
-- Name: bill_action bill_action_pkey; Type: CONSTRAINT; Schema: core; Owner: cbwinslow
--

ALTER TABLE ONLY core.bill_action
    ADD CONSTRAINT bill_action_pkey PRIMARY KEY (bill_action_id);


--
-- Name: bill_committee bill_committee_bill_id_namespace_external_id_source_artifac_key; Type: CONSTRAINT; Schema: core; Owner: cbwinslow
--

ALTER TABLE ONLY core.bill_committee
    ADD CONSTRAINT bill_committee_bill_id_namespace_external_id_source_artifac_key UNIQUE NULLS NOT DISTINCT (bill_id, namespace, external_id, source_artifact_id, source_member);


--
-- Name: bill_committee bill_committee_pkey; Type: CONSTRAINT; Schema: core; Owner: cbwinslow
--

ALTER TABLE ONLY core.bill_committee
    ADD CONSTRAINT bill_committee_pkey PRIMARY KEY (bill_committee_id);


--
-- Name: bill_document bill_document_pkey; Type: CONSTRAINT; Schema: core; Owner: cbwinslow
--

ALTER TABLE ONLY core.bill_document
    ADD CONSTRAINT bill_document_pkey PRIMARY KEY (bill_id, document_id, relation);


--
-- Name: bill_identifier bill_identifier_pkey; Type: CONSTRAINT; Schema: core; Owner: cbwinslow
--

ALTER TABLE ONLY core.bill_identifier
    ADD CONSTRAINT bill_identifier_pkey PRIMARY KEY (namespace, external_id);


--
-- Name: bill bill_jurisdiction_legislative_session_bill_type_bill_number_key; Type: CONSTRAINT; Schema: core; Owner: cbwinslow
--

ALTER TABLE ONLY core.bill
    ADD CONSTRAINT bill_jurisdiction_legislative_session_bill_type_bill_number_key UNIQUE (jurisdiction, legislative_session, bill_type, bill_number);


--
-- Name: bill bill_pkey; Type: CONSTRAINT; Schema: core; Owner: cbwinslow
--

ALTER TABLE ONLY core.bill
    ADD CONSTRAINT bill_pkey PRIMARY KEY (bill_id);


--
-- Name: bill_sponsorship bill_sponsorship_bill_id_member_namespace_member_external_i_key; Type: CONSTRAINT; Schema: core; Owner: cbwinslow
--

ALTER TABLE ONLY core.bill_sponsorship
    ADD CONSTRAINT bill_sponsorship_bill_id_member_namespace_member_external_i_key UNIQUE NULLS NOT DISTINCT (bill_id, member_namespace, member_external_id, role, source_artifact_id, source_member);


--
-- Name: bill_sponsorship bill_sponsorship_pkey; Type: CONSTRAINT; Schema: core; Owner: cbwinslow
--

ALTER TABLE ONLY core.bill_sponsorship
    ADD CONSTRAINT bill_sponsorship_pkey PRIMARY KEY (bill_sponsorship_id);


--
-- Name: bill_subject bill_subject_bill_id_namespace_external_id_source_artifact__key; Type: CONSTRAINT; Schema: core; Owner: cbwinslow
--

ALTER TABLE ONLY core.bill_subject
    ADD CONSTRAINT bill_subject_bill_id_namespace_external_id_source_artifact__key UNIQUE NULLS NOT DISTINCT (bill_id, namespace, external_id, source_artifact_id, source_member);


--
-- Name: bill_subject bill_subject_pkey; Type: CONSTRAINT; Schema: core; Owner: cbwinslow
--

ALTER TABLE ONLY core.bill_subject
    ADD CONSTRAINT bill_subject_pkey PRIMARY KEY (bill_subject_id);


--
-- Name: document_chunk document_chunk_document_id_checksum_sha256_key; Type: CONSTRAINT; Schema: core; Owner: cbwinslow
--

ALTER TABLE ONLY core.document_chunk
    ADD CONSTRAINT document_chunk_document_id_checksum_sha256_key UNIQUE (document_id, checksum_sha256);


--
-- Name: document_chunk document_chunk_document_id_ordinal_key; Type: CONSTRAINT; Schema: core; Owner: cbwinslow
--

ALTER TABLE ONLY core.document_chunk
    ADD CONSTRAINT document_chunk_document_id_ordinal_key UNIQUE (document_id, ordinal);


--
-- Name: document_chunk document_chunk_pkey; Type: CONSTRAINT; Schema: core; Owner: cbwinslow
--

ALTER TABLE ONLY core.document_chunk
    ADD CONSTRAINT document_chunk_pkey PRIMARY KEY (chunk_id);


--
-- Name: document document_document_type_source_key_key; Type: CONSTRAINT; Schema: core; Owner: cbwinslow
--

ALTER TABLE ONLY core.document
    ADD CONSTRAINT document_document_type_source_key_key UNIQUE (document_type, source_key);


--
-- Name: document document_pkey; Type: CONSTRAINT; Schema: core; Owner: cbwinslow
--

ALTER TABLE ONLY core.document
    ADD CONSTRAINT document_pkey PRIMARY KEY (document_id);


--
-- Name: embedding embedding_chunk_id_model_key; Type: CONSTRAINT; Schema: core; Owner: cbwinslow
--

ALTER TABLE ONLY core.embedding
    ADD CONSTRAINT embedding_chunk_id_model_key UNIQUE (chunk_id, model);


--
-- Name: embedding embedding_pkey; Type: CONSTRAINT; Schema: core; Owner: cbwinslow
--

ALTER TABLE ONLY core.embedding
    ADD CONSTRAINT embedding_pkey PRIMARY KEY (embedding_id);


--
-- Name: geography_boundary geography_boundary_geography_id_boundary_vintage_key; Type: CONSTRAINT; Schema: core; Owner: cbwinslow
--

ALTER TABLE ONLY core.geography_boundary
    ADD CONSTRAINT geography_boundary_geography_id_boundary_vintage_key UNIQUE (geography_id, boundary_vintage);


--
-- Name: geography_boundary geography_boundary_pkey; Type: CONSTRAINT; Schema: core; Owner: cbwinslow
--

ALTER TABLE ONLY core.geography_boundary
    ADD CONSTRAINT geography_boundary_pkey PRIMARY KEY (boundary_id);


--
-- Name: geography geography_geography_type_geoid_key; Type: CONSTRAINT; Schema: core; Owner: cbwinslow
--

ALTER TABLE ONLY core.geography
    ADD CONSTRAINT geography_geography_type_geoid_key UNIQUE (geography_type, geoid);


--
-- Name: geography geography_pkey; Type: CONSTRAINT; Schema: core; Owner: cbwinslow
--

ALTER TABLE ONLY core.geography
    ADD CONSTRAINT geography_pkey PRIMARY KEY (geography_id);


--
-- Name: instrument instrument_pkey; Type: CONSTRAINT; Schema: core; Owner: cbwinslow
--

ALTER TABLE ONLY core.instrument
    ADD CONSTRAINT instrument_pkey PRIMARY KEY (instrument_id);


--
-- Name: instrument_symbol instrument_symbol_pkey; Type: CONSTRAINT; Schema: core; Owner: cbwinslow
--

ALTER TABLE ONLY core.instrument_symbol
    ADD CONSTRAINT instrument_symbol_pkey PRIMARY KEY (symbol, exchange, valid_from);


--
-- Name: jurisdiction jurisdiction_pkey; Type: CONSTRAINT; Schema: core; Owner: cbwinslow
--

ALTER TABLE ONLY core.jurisdiction
    ADD CONSTRAINT jurisdiction_pkey PRIMARY KEY (jurisdiction_id);


--
-- Name: legislative_session legislative_session_jurisdiction_id_identifier_key; Type: CONSTRAINT; Schema: core; Owner: cbwinslow
--

ALTER TABLE ONLY core.legislative_session
    ADD CONSTRAINT legislative_session_jurisdiction_id_identifier_key UNIQUE (jurisdiction_id, identifier);


--
-- Name: legislative_session legislative_session_pkey; Type: CONSTRAINT; Schema: core; Owner: cbwinslow
--

ALTER TABLE ONLY core.legislative_session
    ADD CONSTRAINT legislative_session_pkey PRIMARY KEY (legislative_session_id);


--
-- Name: membership membership_pkey; Type: CONSTRAINT; Schema: core; Owner: cbwinslow
--

ALTER TABLE ONLY core.membership
    ADD CONSTRAINT membership_pkey PRIMARY KEY (membership_id);


--
-- Name: organization_identifier organization_identifier_pkey; Type: CONSTRAINT; Schema: core; Owner: cbwinslow
--

ALTER TABLE ONLY core.organization_identifier
    ADD CONSTRAINT organization_identifier_pkey PRIMARY KEY (namespace, external_id);


--
-- Name: organization organization_pkey; Type: CONSTRAINT; Schema: core; Owner: cbwinslow
--

ALTER TABLE ONLY core.organization
    ADD CONSTRAINT organization_pkey PRIMARY KEY (organization_id);


--
-- Name: person_identifier person_identifier_pkey; Type: CONSTRAINT; Schema: core; Owner: cbwinslow
--

ALTER TABLE ONLY core.person_identifier
    ADD CONSTRAINT person_identifier_pkey PRIMARY KEY (namespace, external_id);


--
-- Name: person person_pkey; Type: CONSTRAINT; Schema: core; Owner: cbwinslow
--

ALTER TABLE ONLY core.person
    ADD CONSTRAINT person_pkey PRIMARY KEY (person_id);


--
-- Name: roll_call roll_call_jurisdiction_legislative_session_external_id_key; Type: CONSTRAINT; Schema: core; Owner: cbwinslow
--

ALTER TABLE ONLY core.roll_call
    ADD CONSTRAINT roll_call_jurisdiction_legislative_session_external_id_key UNIQUE (jurisdiction, legislative_session, external_id);


--
-- Name: roll_call roll_call_pkey; Type: CONSTRAINT; Schema: core; Owner: cbwinslow
--

ALTER TABLE ONLY core.roll_call
    ADD CONSTRAINT roll_call_pkey PRIMARY KEY (roll_call_id);


--
-- Name: acs_bulk_estimate acs_bulk_estimate_pkey; Type: CONSTRAINT; Schema: fact; Owner: cbwinslow
--

ALTER TABLE ONLY fact.acs_bulk_estimate
    ADD CONSTRAINT acs_bulk_estimate_pkey PRIMARY KEY (acs_bulk_estimate_id);


--
-- Name: acs_bulk_estimate acs_bulk_estimate_source_artifact_id_source_ordinal_field_i_key; Type: CONSTRAINT; Schema: fact; Owner: cbwinslow
--

ALTER TABLE ONLY fact.acs_bulk_estimate
    ADD CONSTRAINT acs_bulk_estimate_source_artifact_id_source_ordinal_field_i_key UNIQUE (source_artifact_id, source_ordinal, field_id);


--
-- Name: business_pattern business_pattern_pkey; Type: CONSTRAINT; Schema: fact; Owner: cbwinslow
--

ALTER TABLE ONLY fact.business_pattern
    ADD CONSTRAINT business_pattern_pkey PRIMARY KEY (business_pattern_id);


--
-- Name: business_pattern business_pattern_source_artifact_id_source_member_source_or_key; Type: CONSTRAINT; Schema: fact; Owner: cbwinslow
--

ALTER TABLE ONLY fact.business_pattern
    ADD CONSTRAINT business_pattern_source_artifact_id_source_member_source_or_key UNIQUE (source_artifact_id, source_member, source_ordinal);


--
-- Name: decennial_dhc_value decennial_dhc_value_pkey; Type: CONSTRAINT; Schema: fact; Owner: cbwinslow
--

ALTER TABLE ONLY fact.decennial_dhc_value
    ADD CONSTRAINT decennial_dhc_value_pkey PRIMARY KEY (dhc_value_id);


--
-- Name: decennial_dhc_value decennial_dhc_value_source_artifact_id_source_member_source_key; Type: CONSTRAINT; Schema: fact; Owner: cbwinslow
--

ALTER TABLE ONLY fact.decennial_dhc_value
    ADD CONSTRAINT decennial_dhc_value_source_artifact_id_source_member_source_key UNIQUE (source_artifact_id, source_member, source_ordinal, variable_id);


--
-- Name: market_bar market_bar_pkey; Type: CONSTRAINT; Schema: fact; Owner: cbwinslow
--

ALTER TABLE ONLY fact.market_bar
    ADD CONSTRAINT market_bar_pkey PRIMARY KEY (instrument_id, trade_date, "interval");


--
-- Name: measurement measurement_dataset_id_field_id_geography_id_period_start_p_key; Type: CONSTRAINT; Schema: fact; Owner: cbwinslow
--

ALTER TABLE ONLY fact.measurement
    ADD CONSTRAINT measurement_dataset_id_field_id_geography_id_period_start_p_key UNIQUE NULLS NOT DISTINCT (dataset_id, field_id, geography_id, period_start, period_end, vintage_date);


--
-- Name: measurement measurement_pkey; Type: CONSTRAINT; Schema: fact; Owner: cbwinslow
--

ALTER TABLE ONLY fact.measurement
    ADD CONSTRAINT measurement_pkey PRIMARY KEY (measurement_id);


--
-- Name: member_vote member_vote_pkey; Type: CONSTRAINT; Schema: fact; Owner: cbwinslow
--

ALTER TABLE ONLY fact.member_vote
    ADD CONSTRAINT member_vote_pkey PRIMARY KEY (roll_call_id, person_id);


--
-- Name: population_estimate population_estimate_pkey; Type: CONSTRAINT; Schema: fact; Owner: cbwinslow
--

ALTER TABLE ONLY fact.population_estimate
    ADD CONSTRAINT population_estimate_pkey PRIMARY KEY (population_estimate_id);


--
-- Name: population_estimate population_estimate_source_artifact_id_source_member_source_key; Type: CONSTRAINT; Schema: fact; Owner: cbwinslow
--

ALTER TABLE ONLY fact.population_estimate
    ADD CONSTRAINT population_estimate_source_artifact_id_source_member_source_key UNIQUE (source_artifact_id, source_member, source_ordinal, estimate_year);


--
-- Name: artifact artifact_dataset_id_artifact_key_key; Type: CONSTRAINT; Schema: ingest; Owner: cbwinslow
--

ALTER TABLE ONLY ingest.artifact
    ADD CONSTRAINT artifact_dataset_id_artifact_key_key UNIQUE (dataset_id, artifact_key);


--
-- Name: artifact artifact_pkey; Type: CONSTRAINT; Schema: ingest; Owner: cbwinslow
--

ALTER TABLE ONLY ingest.artifact
    ADD CONSTRAINT artifact_pkey PRIMARY KEY (artifact_id);


--
-- Name: cursor cursor_pkey; Type: CONSTRAINT; Schema: ingest; Owner: cbwinslow
--

ALTER TABLE ONLY ingest.cursor
    ADD CONSTRAINT cursor_pkey PRIMARY KEY (plan_id);


--
-- Name: identity_exception identity_exception_pkey; Type: CONSTRAINT; Schema: ingest; Owner: cbwinslow
--

ALTER TABLE ONLY ingest.identity_exception
    ADD CONSTRAINT identity_exception_pkey PRIMARY KEY (identity_exception_id);


--
-- Name: identity_exception identity_exception_run_id_kind_namespace_external_id_reason_key; Type: CONSTRAINT; Schema: ingest; Owner: cbwinslow
--

ALTER TABLE ONLY ingest.identity_exception
    ADD CONSTRAINT identity_exception_run_id_kind_namespace_external_id_reason_key UNIQUE (run_id, kind, namespace, external_id, reason);


--
-- Name: raw_payload raw_payload_pkey; Type: CONSTRAINT; Schema: ingest; Owner: cbwinslow
--

ALTER TABLE ONLY ingest.raw_payload
    ADD CONSTRAINT raw_payload_pkey PRIMARY KEY (payload_id);


--
-- Name: raw_payload raw_payload_run_id_checksum_sha256_key; Type: CONSTRAINT; Schema: ingest; Owner: cbwinslow
--

ALTER TABLE ONLY ingest.raw_payload
    ADD CONSTRAINT raw_payload_run_id_checksum_sha256_key UNIQUE (run_id, checksum_sha256);


--
-- Name: resume_cursor resume_cursor_pkey; Type: CONSTRAINT; Schema: ingest; Owner: cbwinslow
--

ALTER TABLE ONLY ingest.resume_cursor
    ADD CONSTRAINT resume_cursor_pkey PRIMARY KEY (dataset_id, cursor_key);


--
-- Name: run run_pkey; Type: CONSTRAINT; Schema: ingest; Owner: cbwinslow
--

ALTER TABLE ONLY ingest.run
    ADD CONSTRAINT run_pkey PRIMARY KEY (run_id);


--
-- Name: alembic_version alembic_version_pkc; Type: CONSTRAINT; Schema: public; Owner: cbwinslow
--

ALTER TABLE ONLY public.alembic_version
    ADD CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num);


--
-- Name: acs_bulk_row acs_bulk_row_pkey; Type: CONSTRAINT; Schema: stage; Owner: cbwinslow
--

ALTER TABLE ONLY stage.acs_bulk_row
    ADD CONSTRAINT acs_bulk_row_pkey PRIMARY KEY (artifact_id, source_ordinal);


--
-- Name: cbp_row cbp_row_pkey; Type: CONSTRAINT; Schema: stage; Owner: cbwinslow
--

ALTER TABLE ONLY stage.cbp_row
    ADD CONSTRAINT cbp_row_pkey PRIMARY KEY (artifact_id, source_member, source_ordinal);


--
-- Name: dhc_geo_row dhc_geo_row_pkey; Type: CONSTRAINT; Schema: stage; Owner: cbwinslow
--

ALTER TABLE ONLY stage.dhc_geo_row
    ADD CONSTRAINT dhc_geo_row_pkey PRIMARY KEY (artifact_id, source_member, source_ordinal);


--
-- Name: fec_row fec_row_pkey; Type: CONSTRAINT; Schema: stage; Owner: cbwinslow
--

ALTER TABLE ONLY stage.fec_row
    ADD CONSTRAINT fec_row_pkey PRIMARY KEY (artifact_id, source_ordinal);


--
-- Name: pep_row pep_row_pkey; Type: CONSTRAINT; Schema: stage; Owner: cbwinslow
--

ALTER TABLE ONLY stage.pep_row
    ADD CONSTRAINT pep_row_pkey PRIMARY KEY (artifact_id, source_member, source_ordinal);


--
-- Name: tiger_feature tiger_feature_pkey; Type: CONSTRAINT; Schema: stage; Owner: cbwinslow
--

ALTER TABLE ONLY stage.tiger_feature
    ADD CONSTRAINT tiger_feature_pkey PRIMARY KEY (artifact_id, source_ordinal);


--
-- Name: resource_fts_idx; Type: INDEX; Schema: catalog; Owner: cbwinslow
--

CREATE INDEX resource_fts_idx ON catalog.resource USING gin (to_tsvector('english'::regconfig, ((((((((((COALESCE(resource_key, ''::text) || ' '::text) || COALESCE(title, ''::text)) || ' '::text) || COALESCE(summary, ''::text)) || ' '::text) || COALESCE(universe, ''::text)) || ' '::text) || COALESCE(resource_type, ''::text)) || ' '::text) || COALESCE((metadata)::text, ''::text))));


--
-- Name: resource_search_idx; Type: INDEX; Schema: catalog; Owner: cbwinslow
--

CREATE INDEX resource_search_idx ON catalog.resource USING btree (dataset_id, release_year, resource_type);


--
-- Name: resource_title_trgm_idx; Type: INDEX; Schema: catalog; Owner: cbwinslow
--

CREATE INDEX resource_title_trgm_idx ON catalog.resource USING gin (title public.gin_trgm_ops);


--
-- Name: bill_action_source_member_idx; Type: INDEX; Schema: core; Owner: cbwinslow
--

CREATE UNIQUE INDEX bill_action_source_member_idx ON core.bill_action USING btree (bill_id, source_artifact_id, source_member, source_ordinal) WHERE (source_artifact_id IS NOT NULL);


--
-- Name: bill_identifier_bill_idx; Type: INDEX; Schema: core; Owner: cbwinslow
--

CREATE INDEX bill_identifier_bill_idx ON core.bill_identifier USING btree (bill_id);


--
-- Name: bill_ocd_id_idx; Type: INDEX; Schema: core; Owner: cbwinslow
--

CREATE UNIQUE INDEX bill_ocd_id_idx ON core.bill USING btree (ocd_id) WHERE (ocd_id IS NOT NULL);


--
-- Name: bill_sponsorship_person_idx; Type: INDEX; Schema: core; Owner: cbwinslow
--

CREATE INDEX bill_sponsorship_person_idx ON core.bill_sponsorship USING btree (person_id);


--
-- Name: geography_boundary_geom_idx; Type: INDEX; Schema: core; Owner: cbwinslow
--

CREATE INDEX geography_boundary_geom_idx ON core.geography_boundary USING gist (geom);


--
-- Name: membership_organization_idx; Type: INDEX; Schema: core; Owner: cbwinslow
--

CREATE INDEX membership_organization_idx ON core.membership USING btree (organization_id);


--
-- Name: membership_person_idx; Type: INDEX; Schema: core; Owner: cbwinslow
--

CREATE INDEX membership_person_idx ON core.membership USING btree (person_id);


--
-- Name: roll_call_ocd_id_idx; Type: INDEX; Schema: core; Owner: cbwinslow
--

CREATE UNIQUE INDEX roll_call_ocd_id_idx ON core.roll_call USING btree (ocd_id) WHERE (ocd_id IS NOT NULL);


--
-- Name: acs_bulk_estimate_lookup_idx; Type: INDEX; Schema: fact; Owner: cbwinslow
--

CREATE INDEX acs_bulk_estimate_lookup_idx ON fact.acs_bulk_estimate USING btree (release_year, geography_id, table_id, field_id);


--
-- Name: business_pattern_lookup_idx; Type: INDEX; Schema: fact; Owner: cbwinslow
--

CREATE INDEX business_pattern_lookup_idx ON fact.business_pattern USING btree (release_year, geography_id, naics);


--
-- Name: dhc_value_lookup_idx; Type: INDEX; Schema: fact; Owner: cbwinslow
--

CREATE INDEX dhc_value_lookup_idx ON fact.decennial_dhc_value USING btree (release_year, geography_id, table_id, variable_id);


--
-- Name: measurement_lookup_idx; Type: INDEX; Schema: fact; Owner: cbwinslow
--

CREATE INDEX measurement_lookup_idx ON fact.measurement USING btree (dataset_id, field_id, period_start);


--
-- Name: population_estimate_lookup_idx; Type: INDEX; Schema: fact; Owner: cbwinslow
--

CREATE INDEX population_estimate_lookup_idx ON fact.population_estimate USING btree (release_vintage, estimate_year, geography_id);


--
-- Name: artifact_dataset_status_idx; Type: INDEX; Schema: ingest; Owner: cbwinslow
--

CREATE INDEX artifact_dataset_status_idx ON ingest.artifact USING btree (dataset_id, status);


--
-- Name: identity_exception_lookup_idx; Type: INDEX; Schema: ingest; Owner: cbwinslow
--

CREATE INDEX identity_exception_lookup_idx ON ingest.identity_exception USING btree (congress, namespace, external_id);


--
-- Name: raw_payload_run_idx; Type: INDEX; Schema: ingest; Owner: cbwinslow
--

CREATE INDEX raw_payload_run_idx ON ingest.raw_payload USING btree (run_id);


--
-- Name: dhc_geo_lookup_idx; Type: INDEX; Schema: stage; Owner: cbwinslow
--

CREATE INDEX dhc_geo_lookup_idx ON stage.dhc_geo_row USING btree (artifact_id, logrecno, sumlev);


--
-- Name: fec_row_family_cycle_idx; Type: INDEX; Schema: stage; Owner: cbwinslow
--

CREATE INDEX fec_row_family_cycle_idx ON stage.fec_row USING btree (family, cycle);


--
-- Name: tiger_feature_geom_idx; Type: INDEX; Schema: stage; Owner: cbwinslow
--

CREATE INDEX tiger_feature_geom_idx ON stage.tiger_feature USING gist (geom);


--
-- Name: basket_item basket_item_basket_id_fkey; Type: FK CONSTRAINT; Schema: catalog; Owner: cbwinslow
--

ALTER TABLE ONLY catalog.basket_item
    ADD CONSTRAINT basket_item_basket_id_fkey FOREIGN KEY (basket_id) REFERENCES catalog.basket(basket_id) ON DELETE CASCADE;


--
-- Name: basket_item basket_item_resource_id_fkey; Type: FK CONSTRAINT; Schema: catalog; Owner: cbwinslow
--

ALTER TABLE ONLY catalog.basket_item
    ADD CONSTRAINT basket_item_resource_id_fkey FOREIGN KEY (resource_id) REFERENCES catalog.resource(resource_id) ON DELETE RESTRICT;


--
-- Name: dataset_field dataset_field_dataset_id_fkey; Type: FK CONSTRAINT; Schema: catalog; Owner: cbwinslow
--

ALTER TABLE ONLY catalog.dataset_field
    ADD CONSTRAINT dataset_field_dataset_id_fkey FOREIGN KEY (dataset_id) REFERENCES catalog.dataset(dataset_id);


--
-- Name: dataset dataset_provider_id_fkey; Type: FK CONSTRAINT; Schema: catalog; Owner: cbwinslow
--

ALTER TABLE ONLY catalog.dataset
    ADD CONSTRAINT dataset_provider_id_fkey FOREIGN KEY (provider_id) REFERENCES catalog.provider(provider_id);


--
-- Name: discovery discovery_dataset_id_fkey; Type: FK CONSTRAINT; Schema: catalog; Owner: cbwinslow
--

ALTER TABLE ONLY catalog.discovery
    ADD CONSTRAINT discovery_dataset_id_fkey FOREIGN KEY (dataset_id) REFERENCES catalog.dataset(dataset_id);


--
-- Name: plan plan_dataset_id_fkey; Type: FK CONSTRAINT; Schema: catalog; Owner: cbwinslow
--

ALTER TABLE ONLY catalog.plan
    ADD CONSTRAINT plan_dataset_id_fkey FOREIGN KEY (dataset_id) REFERENCES catalog.dataset(dataset_id);


--
-- Name: resource resource_dataset_id_fkey; Type: FK CONSTRAINT; Schema: catalog; Owner: cbwinslow
--

ALTER TABLE ONLY catalog.resource
    ADD CONSTRAINT resource_dataset_id_fkey FOREIGN KEY (dataset_id) REFERENCES catalog.dataset(dataset_id);


--
-- Name: resource_field resource_field_resource_id_fkey; Type: FK CONSTRAINT; Schema: catalog; Owner: cbwinslow
--

ALTER TABLE ONLY catalog.resource_field
    ADD CONSTRAINT resource_field_resource_id_fkey FOREIGN KEY (resource_id) REFERENCES catalog.resource(resource_id) ON DELETE CASCADE;


--
-- Name: resource resource_source_artifact_id_fkey; Type: FK CONSTRAINT; Schema: catalog; Owner: cbwinslow
--

ALTER TABLE ONLY catalog.resource
    ADD CONSTRAINT resource_source_artifact_id_fkey FOREIGN KEY (source_artifact_id) REFERENCES ingest.artifact(artifact_id);


--
-- Name: snapshot snapshot_artifact_id_fkey; Type: FK CONSTRAINT; Schema: catalog; Owner: cbwinslow
--

ALTER TABLE ONLY catalog.snapshot
    ADD CONSTRAINT snapshot_artifact_id_fkey FOREIGN KEY (artifact_id) REFERENCES ingest.artifact(artifact_id);


--
-- Name: snapshot snapshot_dataset_id_fkey; Type: FK CONSTRAINT; Schema: catalog; Owner: cbwinslow
--

ALTER TABLE ONLY catalog.snapshot
    ADD CONSTRAINT snapshot_dataset_id_fkey FOREIGN KEY (dataset_id) REFERENCES catalog.dataset(dataset_id);


--
-- Name: snapshot_resource snapshot_resource_resource_id_fkey; Type: FK CONSTRAINT; Schema: catalog; Owner: cbwinslow
--

ALTER TABLE ONLY catalog.snapshot_resource
    ADD CONSTRAINT snapshot_resource_resource_id_fkey FOREIGN KEY (resource_id) REFERENCES catalog.resource(resource_id) ON DELETE RESTRICT;


--
-- Name: snapshot_resource snapshot_resource_snapshot_id_fkey; Type: FK CONSTRAINT; Schema: catalog; Owner: cbwinslow
--

ALTER TABLE ONLY catalog.snapshot_resource
    ADD CONSTRAINT snapshot_resource_snapshot_id_fkey FOREIGN KEY (snapshot_id) REFERENCES catalog.snapshot(snapshot_id) ON DELETE CASCADE;


--
-- Name: bill_action bill_action_bill_id_fkey; Type: FK CONSTRAINT; Schema: core; Owner: cbwinslow
--

ALTER TABLE ONLY core.bill_action
    ADD CONSTRAINT bill_action_bill_id_fkey FOREIGN KEY (bill_id) REFERENCES core.bill(bill_id);


--
-- Name: bill_action bill_action_source_artifact_id_fkey; Type: FK CONSTRAINT; Schema: core; Owner: cbwinslow
--

ALTER TABLE ONLY core.bill_action
    ADD CONSTRAINT bill_action_source_artifact_id_fkey FOREIGN KEY (source_artifact_id) REFERENCES ingest.artifact(artifact_id);


--
-- Name: bill_action bill_action_source_payload_id_fkey; Type: FK CONSTRAINT; Schema: core; Owner: cbwinslow
--

ALTER TABLE ONLY core.bill_action
    ADD CONSTRAINT bill_action_source_payload_id_fkey FOREIGN KEY (source_payload_id) REFERENCES ingest.raw_payload(payload_id);


--
-- Name: bill_committee bill_committee_bill_id_fkey; Type: FK CONSTRAINT; Schema: core; Owner: cbwinslow
--

ALTER TABLE ONLY core.bill_committee
    ADD CONSTRAINT bill_committee_bill_id_fkey FOREIGN KEY (bill_id) REFERENCES core.bill(bill_id);


--
-- Name: bill_committee bill_committee_source_artifact_id_fkey; Type: FK CONSTRAINT; Schema: core; Owner: cbwinslow
--

ALTER TABLE ONLY core.bill_committee
    ADD CONSTRAINT bill_committee_source_artifact_id_fkey FOREIGN KEY (source_artifact_id) REFERENCES ingest.artifact(artifact_id);


--
-- Name: bill_committee bill_committee_source_payload_id_fkey; Type: FK CONSTRAINT; Schema: core; Owner: cbwinslow
--

ALTER TABLE ONLY core.bill_committee
    ADD CONSTRAINT bill_committee_source_payload_id_fkey FOREIGN KEY (source_payload_id) REFERENCES ingest.raw_payload(payload_id);


--
-- Name: bill_document bill_document_bill_id_fkey; Type: FK CONSTRAINT; Schema: core; Owner: cbwinslow
--

ALTER TABLE ONLY core.bill_document
    ADD CONSTRAINT bill_document_bill_id_fkey FOREIGN KEY (bill_id) REFERENCES core.bill(bill_id);


--
-- Name: bill_document bill_document_document_id_fkey; Type: FK CONSTRAINT; Schema: core; Owner: cbwinslow
--

ALTER TABLE ONLY core.bill_document
    ADD CONSTRAINT bill_document_document_id_fkey FOREIGN KEY (document_id) REFERENCES core.document(document_id);


--
-- Name: bill_identifier bill_identifier_bill_id_fkey; Type: FK CONSTRAINT; Schema: core; Owner: cbwinslow
--

ALTER TABLE ONLY core.bill_identifier
    ADD CONSTRAINT bill_identifier_bill_id_fkey FOREIGN KEY (bill_id) REFERENCES core.bill(bill_id);


--
-- Name: bill_identifier bill_identifier_source_artifact_id_fkey; Type: FK CONSTRAINT; Schema: core; Owner: cbwinslow
--

ALTER TABLE ONLY core.bill_identifier
    ADD CONSTRAINT bill_identifier_source_artifact_id_fkey FOREIGN KEY (source_artifact_id) REFERENCES ingest.artifact(artifact_id);


--
-- Name: bill_identifier bill_identifier_source_payload_id_fkey; Type: FK CONSTRAINT; Schema: core; Owner: cbwinslow
--

ALTER TABLE ONLY core.bill_identifier
    ADD CONSTRAINT bill_identifier_source_payload_id_fkey FOREIGN KEY (source_payload_id) REFERENCES ingest.raw_payload(payload_id);


--
-- Name: bill bill_legislative_session_id_fkey; Type: FK CONSTRAINT; Schema: core; Owner: cbwinslow
--

ALTER TABLE ONLY core.bill
    ADD CONSTRAINT bill_legislative_session_id_fkey FOREIGN KEY (legislative_session_id) REFERENCES core.legislative_session(legislative_session_id);


--
-- Name: bill_sponsorship bill_sponsorship_bill_id_fkey; Type: FK CONSTRAINT; Schema: core; Owner: cbwinslow
--

ALTER TABLE ONLY core.bill_sponsorship
    ADD CONSTRAINT bill_sponsorship_bill_id_fkey FOREIGN KEY (bill_id) REFERENCES core.bill(bill_id);


--
-- Name: bill_sponsorship bill_sponsorship_person_id_fkey; Type: FK CONSTRAINT; Schema: core; Owner: cbwinslow
--

ALTER TABLE ONLY core.bill_sponsorship
    ADD CONSTRAINT bill_sponsorship_person_id_fkey FOREIGN KEY (person_id) REFERENCES core.person(person_id);


--
-- Name: bill_sponsorship bill_sponsorship_source_artifact_id_fkey; Type: FK CONSTRAINT; Schema: core; Owner: cbwinslow
--

ALTER TABLE ONLY core.bill_sponsorship
    ADD CONSTRAINT bill_sponsorship_source_artifact_id_fkey FOREIGN KEY (source_artifact_id) REFERENCES ingest.artifact(artifact_id);


--
-- Name: bill_sponsorship bill_sponsorship_source_payload_id_fkey; Type: FK CONSTRAINT; Schema: core; Owner: cbwinslow
--

ALTER TABLE ONLY core.bill_sponsorship
    ADD CONSTRAINT bill_sponsorship_source_payload_id_fkey FOREIGN KEY (source_payload_id) REFERENCES ingest.raw_payload(payload_id);


--
-- Name: bill_subject bill_subject_bill_id_fkey; Type: FK CONSTRAINT; Schema: core; Owner: cbwinslow
--

ALTER TABLE ONLY core.bill_subject
    ADD CONSTRAINT bill_subject_bill_id_fkey FOREIGN KEY (bill_id) REFERENCES core.bill(bill_id);


--
-- Name: bill_subject bill_subject_source_artifact_id_fkey; Type: FK CONSTRAINT; Schema: core; Owner: cbwinslow
--

ALTER TABLE ONLY core.bill_subject
    ADD CONSTRAINT bill_subject_source_artifact_id_fkey FOREIGN KEY (source_artifact_id) REFERENCES ingest.artifact(artifact_id);


--
-- Name: bill_subject bill_subject_source_payload_id_fkey; Type: FK CONSTRAINT; Schema: core; Owner: cbwinslow
--

ALTER TABLE ONLY core.bill_subject
    ADD CONSTRAINT bill_subject_source_payload_id_fkey FOREIGN KEY (source_payload_id) REFERENCES ingest.raw_payload(payload_id);


--
-- Name: document document_artifact_id_fkey; Type: FK CONSTRAINT; Schema: core; Owner: cbwinslow
--

ALTER TABLE ONLY core.document
    ADD CONSTRAINT document_artifact_id_fkey FOREIGN KEY (artifact_id) REFERENCES ingest.artifact(artifact_id);


--
-- Name: document_chunk document_chunk_document_id_fkey; Type: FK CONSTRAINT; Schema: core; Owner: cbwinslow
--

ALTER TABLE ONLY core.document_chunk
    ADD CONSTRAINT document_chunk_document_id_fkey FOREIGN KEY (document_id) REFERENCES core.document(document_id);


--
-- Name: document document_source_payload_id_fkey; Type: FK CONSTRAINT; Schema: core; Owner: cbwinslow
--

ALTER TABLE ONLY core.document
    ADD CONSTRAINT document_source_payload_id_fkey FOREIGN KEY (source_payload_id) REFERENCES ingest.raw_payload(payload_id);


--
-- Name: embedding embedding_chunk_id_fkey; Type: FK CONSTRAINT; Schema: core; Owner: cbwinslow
--

ALTER TABLE ONLY core.embedding
    ADD CONSTRAINT embedding_chunk_id_fkey FOREIGN KEY (chunk_id) REFERENCES core.document_chunk(chunk_id);


--
-- Name: geography_boundary geography_boundary_geography_id_fkey; Type: FK CONSTRAINT; Schema: core; Owner: cbwinslow
--

ALTER TABLE ONLY core.geography_boundary
    ADD CONSTRAINT geography_boundary_geography_id_fkey FOREIGN KEY (geography_id) REFERENCES core.geography(geography_id);


--
-- Name: geography_boundary geography_boundary_source_artifact_id_fkey; Type: FK CONSTRAINT; Schema: core; Owner: cbwinslow
--

ALTER TABLE ONLY core.geography_boundary
    ADD CONSTRAINT geography_boundary_source_artifact_id_fkey FOREIGN KEY (source_artifact_id) REFERENCES ingest.artifact(artifact_id);


--
-- Name: geography_boundary geography_boundary_source_payload_id_fkey; Type: FK CONSTRAINT; Schema: core; Owner: cbwinslow
--

ALTER TABLE ONLY core.geography_boundary
    ADD CONSTRAINT geography_boundary_source_payload_id_fkey FOREIGN KEY (source_payload_id) REFERENCES ingest.raw_payload(payload_id);


--
-- Name: instrument_symbol instrument_symbol_instrument_id_fkey; Type: FK CONSTRAINT; Schema: core; Owner: cbwinslow
--

ALTER TABLE ONLY core.instrument_symbol
    ADD CONSTRAINT instrument_symbol_instrument_id_fkey FOREIGN KEY (instrument_id) REFERENCES core.instrument(instrument_id);


--
-- Name: legislative_session legislative_session_jurisdiction_id_fkey; Type: FK CONSTRAINT; Schema: core; Owner: cbwinslow
--

ALTER TABLE ONLY core.legislative_session
    ADD CONSTRAINT legislative_session_jurisdiction_id_fkey FOREIGN KEY (jurisdiction_id) REFERENCES core.jurisdiction(jurisdiction_id);


--
-- Name: legislative_session legislative_session_source_artifact_id_fkey; Type: FK CONSTRAINT; Schema: core; Owner: cbwinslow
--

ALTER TABLE ONLY core.legislative_session
    ADD CONSTRAINT legislative_session_source_artifact_id_fkey FOREIGN KEY (source_artifact_id) REFERENCES ingest.artifact(artifact_id);


--
-- Name: legislative_session legislative_session_source_payload_id_fkey; Type: FK CONSTRAINT; Schema: core; Owner: cbwinslow
--

ALTER TABLE ONLY core.legislative_session
    ADD CONSTRAINT legislative_session_source_payload_id_fkey FOREIGN KEY (source_payload_id) REFERENCES ingest.raw_payload(payload_id);


--
-- Name: membership membership_legislative_session_id_fkey; Type: FK CONSTRAINT; Schema: core; Owner: cbwinslow
--

ALTER TABLE ONLY core.membership
    ADD CONSTRAINT membership_legislative_session_id_fkey FOREIGN KEY (legislative_session_id) REFERENCES core.legislative_session(legislative_session_id);


--
-- Name: membership membership_organization_id_fkey; Type: FK CONSTRAINT; Schema: core; Owner: cbwinslow
--

ALTER TABLE ONLY core.membership
    ADD CONSTRAINT membership_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES core.organization(organization_id);


--
-- Name: membership membership_person_id_fkey; Type: FK CONSTRAINT; Schema: core; Owner: cbwinslow
--

ALTER TABLE ONLY core.membership
    ADD CONSTRAINT membership_person_id_fkey FOREIGN KEY (person_id) REFERENCES core.person(person_id);


--
-- Name: membership membership_source_artifact_id_fkey; Type: FK CONSTRAINT; Schema: core; Owner: cbwinslow
--

ALTER TABLE ONLY core.membership
    ADD CONSTRAINT membership_source_artifact_id_fkey FOREIGN KEY (source_artifact_id) REFERENCES ingest.artifact(artifact_id);


--
-- Name: membership membership_source_payload_id_fkey; Type: FK CONSTRAINT; Schema: core; Owner: cbwinslow
--

ALTER TABLE ONLY core.membership
    ADD CONSTRAINT membership_source_payload_id_fkey FOREIGN KEY (source_payload_id) REFERENCES ingest.raw_payload(payload_id);


--
-- Name: organization_identifier organization_identifier_organization_id_fkey; Type: FK CONSTRAINT; Schema: core; Owner: cbwinslow
--

ALTER TABLE ONLY core.organization_identifier
    ADD CONSTRAINT organization_identifier_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES core.organization(organization_id);


--
-- Name: person_identifier person_identifier_person_id_fkey; Type: FK CONSTRAINT; Schema: core; Owner: cbwinslow
--

ALTER TABLE ONLY core.person_identifier
    ADD CONSTRAINT person_identifier_person_id_fkey FOREIGN KEY (person_id) REFERENCES core.person(person_id);


--
-- Name: roll_call roll_call_bill_id_fkey; Type: FK CONSTRAINT; Schema: core; Owner: cbwinslow
--

ALTER TABLE ONLY core.roll_call
    ADD CONSTRAINT roll_call_bill_id_fkey FOREIGN KEY (bill_id) REFERENCES core.bill(bill_id);


--
-- Name: roll_call roll_call_legislative_session_id_fkey; Type: FK CONSTRAINT; Schema: core; Owner: cbwinslow
--

ALTER TABLE ONLY core.roll_call
    ADD CONSTRAINT roll_call_legislative_session_id_fkey FOREIGN KEY (legislative_session_id) REFERENCES core.legislative_session(legislative_session_id);


--
-- Name: roll_call roll_call_organization_id_fkey; Type: FK CONSTRAINT; Schema: core; Owner: cbwinslow
--

ALTER TABLE ONLY core.roll_call
    ADD CONSTRAINT roll_call_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES core.organization(organization_id);


--
-- Name: acs_bulk_estimate acs_bulk_estimate_geography_id_fkey; Type: FK CONSTRAINT; Schema: fact; Owner: cbwinslow
--

ALTER TABLE ONLY fact.acs_bulk_estimate
    ADD CONSTRAINT acs_bulk_estimate_geography_id_fkey FOREIGN KEY (geography_id) REFERENCES core.geography(geography_id);


--
-- Name: acs_bulk_estimate acs_bulk_estimate_source_artifact_id_fkey; Type: FK CONSTRAINT; Schema: fact; Owner: cbwinslow
--

ALTER TABLE ONLY fact.acs_bulk_estimate
    ADD CONSTRAINT acs_bulk_estimate_source_artifact_id_fkey FOREIGN KEY (source_artifact_id) REFERENCES ingest.artifact(artifact_id);


--
-- Name: business_pattern business_pattern_geography_id_fkey; Type: FK CONSTRAINT; Schema: fact; Owner: cbwinslow
--

ALTER TABLE ONLY fact.business_pattern
    ADD CONSTRAINT business_pattern_geography_id_fkey FOREIGN KEY (geography_id) REFERENCES core.geography(geography_id);


--
-- Name: business_pattern business_pattern_source_artifact_id_fkey; Type: FK CONSTRAINT; Schema: fact; Owner: cbwinslow
--

ALTER TABLE ONLY fact.business_pattern
    ADD CONSTRAINT business_pattern_source_artifact_id_fkey FOREIGN KEY (source_artifact_id) REFERENCES ingest.artifact(artifact_id);


--
-- Name: decennial_dhc_value decennial_dhc_value_geography_id_fkey; Type: FK CONSTRAINT; Schema: fact; Owner: cbwinslow
--

ALTER TABLE ONLY fact.decennial_dhc_value
    ADD CONSTRAINT decennial_dhc_value_geography_id_fkey FOREIGN KEY (geography_id) REFERENCES core.geography(geography_id);


--
-- Name: decennial_dhc_value decennial_dhc_value_source_artifact_id_fkey; Type: FK CONSTRAINT; Schema: fact; Owner: cbwinslow
--

ALTER TABLE ONLY fact.decennial_dhc_value
    ADD CONSTRAINT decennial_dhc_value_source_artifact_id_fkey FOREIGN KEY (source_artifact_id) REFERENCES ingest.artifact(artifact_id);


--
-- Name: market_bar market_bar_instrument_id_fkey; Type: FK CONSTRAINT; Schema: fact; Owner: cbwinslow
--

ALTER TABLE ONLY fact.market_bar
    ADD CONSTRAINT market_bar_instrument_id_fkey FOREIGN KEY (instrument_id) REFERENCES core.instrument(instrument_id);


--
-- Name: market_bar market_bar_source_payload_id_fkey; Type: FK CONSTRAINT; Schema: fact; Owner: cbwinslow
--

ALTER TABLE ONLY fact.market_bar
    ADD CONSTRAINT market_bar_source_payload_id_fkey FOREIGN KEY (source_payload_id) REFERENCES ingest.raw_payload(payload_id);


--
-- Name: measurement measurement_dataset_id_fkey; Type: FK CONSTRAINT; Schema: fact; Owner: cbwinslow
--

ALTER TABLE ONLY fact.measurement
    ADD CONSTRAINT measurement_dataset_id_fkey FOREIGN KEY (dataset_id) REFERENCES catalog.dataset(dataset_id);


--
-- Name: measurement measurement_geography_id_fkey; Type: FK CONSTRAINT; Schema: fact; Owner: cbwinslow
--

ALTER TABLE ONLY fact.measurement
    ADD CONSTRAINT measurement_geography_id_fkey FOREIGN KEY (geography_id) REFERENCES core.geography(geography_id);


--
-- Name: measurement measurement_source_payload_id_fkey; Type: FK CONSTRAINT; Schema: fact; Owner: cbwinslow
--

ALTER TABLE ONLY fact.measurement
    ADD CONSTRAINT measurement_source_payload_id_fkey FOREIGN KEY (source_payload_id) REFERENCES ingest.raw_payload(payload_id);


--
-- Name: member_vote member_vote_person_id_fkey; Type: FK CONSTRAINT; Schema: fact; Owner: cbwinslow
--

ALTER TABLE ONLY fact.member_vote
    ADD CONSTRAINT member_vote_person_id_fkey FOREIGN KEY (person_id) REFERENCES core.person(person_id);


--
-- Name: member_vote member_vote_roll_call_id_fkey; Type: FK CONSTRAINT; Schema: fact; Owner: cbwinslow
--

ALTER TABLE ONLY fact.member_vote
    ADD CONSTRAINT member_vote_roll_call_id_fkey FOREIGN KEY (roll_call_id) REFERENCES core.roll_call(roll_call_id);


--
-- Name: member_vote member_vote_source_artifact_id_fkey; Type: FK CONSTRAINT; Schema: fact; Owner: cbwinslow
--

ALTER TABLE ONLY fact.member_vote
    ADD CONSTRAINT member_vote_source_artifact_id_fkey FOREIGN KEY (source_artifact_id) REFERENCES ingest.artifact(artifact_id);


--
-- Name: member_vote member_vote_source_payload_id_fkey; Type: FK CONSTRAINT; Schema: fact; Owner: cbwinslow
--

ALTER TABLE ONLY fact.member_vote
    ADD CONSTRAINT member_vote_source_payload_id_fkey FOREIGN KEY (source_payload_id) REFERENCES ingest.raw_payload(payload_id);


--
-- Name: population_estimate population_estimate_geography_id_fkey; Type: FK CONSTRAINT; Schema: fact; Owner: cbwinslow
--

ALTER TABLE ONLY fact.population_estimate
    ADD CONSTRAINT population_estimate_geography_id_fkey FOREIGN KEY (geography_id) REFERENCES core.geography(geography_id);


--
-- Name: population_estimate population_estimate_source_artifact_id_fkey; Type: FK CONSTRAINT; Schema: fact; Owner: cbwinslow
--

ALTER TABLE ONLY fact.population_estimate
    ADD CONSTRAINT population_estimate_source_artifact_id_fkey FOREIGN KEY (source_artifact_id) REFERENCES ingest.artifact(artifact_id);


--
-- Name: artifact artifact_dataset_id_fkey; Type: FK CONSTRAINT; Schema: ingest; Owner: cbwinslow
--

ALTER TABLE ONLY ingest.artifact
    ADD CONSTRAINT artifact_dataset_id_fkey FOREIGN KEY (dataset_id) REFERENCES catalog.dataset(dataset_id);


--
-- Name: cursor cursor_plan_id_fkey; Type: FK CONSTRAINT; Schema: ingest; Owner: cbwinslow
--

ALTER TABLE ONLY ingest.cursor
    ADD CONSTRAINT cursor_plan_id_fkey FOREIGN KEY (plan_id) REFERENCES catalog.plan(plan_id);


--
-- Name: cursor cursor_successful_run_id_fkey; Type: FK CONSTRAINT; Schema: ingest; Owner: cbwinslow
--

ALTER TABLE ONLY ingest.cursor
    ADD CONSTRAINT cursor_successful_run_id_fkey FOREIGN KEY (successful_run_id) REFERENCES ingest.run(run_id);


--
-- Name: identity_exception identity_exception_dataset_id_fkey; Type: FK CONSTRAINT; Schema: ingest; Owner: cbwinslow
--

ALTER TABLE ONLY ingest.identity_exception
    ADD CONSTRAINT identity_exception_dataset_id_fkey FOREIGN KEY (dataset_id) REFERENCES catalog.dataset(dataset_id);


--
-- Name: identity_exception identity_exception_run_id_fkey; Type: FK CONSTRAINT; Schema: ingest; Owner: cbwinslow
--

ALTER TABLE ONLY ingest.identity_exception
    ADD CONSTRAINT identity_exception_run_id_fkey FOREIGN KEY (run_id) REFERENCES ingest.run(run_id);


--
-- Name: identity_exception identity_exception_source_artifact_id_fkey; Type: FK CONSTRAINT; Schema: ingest; Owner: cbwinslow
--

ALTER TABLE ONLY ingest.identity_exception
    ADD CONSTRAINT identity_exception_source_artifact_id_fkey FOREIGN KEY (source_artifact_id) REFERENCES ingest.artifact(artifact_id);


--
-- Name: raw_payload raw_payload_run_id_fkey; Type: FK CONSTRAINT; Schema: ingest; Owner: cbwinslow
--

ALTER TABLE ONLY ingest.raw_payload
    ADD CONSTRAINT raw_payload_run_id_fkey FOREIGN KEY (run_id) REFERENCES ingest.run(run_id);


--
-- Name: resume_cursor resume_cursor_dataset_id_fkey; Type: FK CONSTRAINT; Schema: ingest; Owner: cbwinslow
--

ALTER TABLE ONLY ingest.resume_cursor
    ADD CONSTRAINT resume_cursor_dataset_id_fkey FOREIGN KEY (dataset_id) REFERENCES catalog.dataset(dataset_id);


--
-- Name: resume_cursor resume_cursor_last_run_id_fkey; Type: FK CONSTRAINT; Schema: ingest; Owner: cbwinslow
--

ALTER TABLE ONLY ingest.resume_cursor
    ADD CONSTRAINT resume_cursor_last_run_id_fkey FOREIGN KEY (last_run_id) REFERENCES ingest.run(run_id);


--
-- Name: resume_cursor resume_cursor_source_artifact_id_fkey; Type: FK CONSTRAINT; Schema: ingest; Owner: cbwinslow
--

ALTER TABLE ONLY ingest.resume_cursor
    ADD CONSTRAINT resume_cursor_source_artifact_id_fkey FOREIGN KEY (source_artifact_id) REFERENCES ingest.artifact(artifact_id);


--
-- Name: run run_dataset_id_fkey; Type: FK CONSTRAINT; Schema: ingest; Owner: cbwinslow
--

ALTER TABLE ONLY ingest.run
    ADD CONSTRAINT run_dataset_id_fkey FOREIGN KEY (dataset_id) REFERENCES catalog.dataset(dataset_id);


--
-- Name: acs_bulk_row acs_bulk_row_artifact_id_fkey; Type: FK CONSTRAINT; Schema: stage; Owner: cbwinslow
--

ALTER TABLE ONLY stage.acs_bulk_row
    ADD CONSTRAINT acs_bulk_row_artifact_id_fkey FOREIGN KEY (artifact_id) REFERENCES ingest.artifact(artifact_id);


--
-- Name: cbp_row cbp_row_artifact_id_fkey; Type: FK CONSTRAINT; Schema: stage; Owner: cbwinslow
--

ALTER TABLE ONLY stage.cbp_row
    ADD CONSTRAINT cbp_row_artifact_id_fkey FOREIGN KEY (artifact_id) REFERENCES ingest.artifact(artifact_id);


--
-- Name: dhc_geo_row dhc_geo_row_artifact_id_fkey; Type: FK CONSTRAINT; Schema: stage; Owner: cbwinslow
--

ALTER TABLE ONLY stage.dhc_geo_row
    ADD CONSTRAINT dhc_geo_row_artifact_id_fkey FOREIGN KEY (artifact_id) REFERENCES ingest.artifact(artifact_id);


--
-- Name: fec_row fec_row_artifact_id_fkey; Type: FK CONSTRAINT; Schema: stage; Owner: cbwinslow
--

ALTER TABLE ONLY stage.fec_row
    ADD CONSTRAINT fec_row_artifact_id_fkey FOREIGN KEY (artifact_id) REFERENCES ingest.artifact(artifact_id);


--
-- Name: pep_row pep_row_artifact_id_fkey; Type: FK CONSTRAINT; Schema: stage; Owner: cbwinslow
--

ALTER TABLE ONLY stage.pep_row
    ADD CONSTRAINT pep_row_artifact_id_fkey FOREIGN KEY (artifact_id) REFERENCES ingest.artifact(artifact_id);


--
-- Name: tiger_feature tiger_feature_artifact_id_fkey; Type: FK CONSTRAINT; Schema: stage; Owner: cbwinslow
--

ALTER TABLE ONLY stage.tiger_feature
    ADD CONSTRAINT tiger_feature_artifact_id_fkey FOREIGN KEY (artifact_id) REFERENCES ingest.artifact(artifact_id);


--
-- Name: SCHEMA openstates_source; Type: ACL; Schema: -; Owner: postgres
--

GRANT USAGE ON SCHEMA openstates_source TO cbwinslow;


--
-- Name: FOREIGN SERVER openstates_local; Type: ACL; Schema: -; Owner: postgres
--

GRANT ALL ON FOREIGN SERVER openstates_local TO cbwinslow;


--
-- Name: TABLE opencivicdata_bill; Type: ACL; Schema: openstates_source; Owner: postgres
--

GRANT SELECT ON TABLE openstates_source.opencivicdata_bill TO cbwinslow;


--
-- Name: TABLE opencivicdata_jurisdiction; Type: ACL; Schema: openstates_source; Owner: postgres
--

GRANT SELECT ON TABLE openstates_source.opencivicdata_jurisdiction TO cbwinslow;


--
-- Name: TABLE opencivicdata_legislativesession; Type: ACL; Schema: openstates_source; Owner: postgres
--

GRANT SELECT ON TABLE openstates_source.opencivicdata_legislativesession TO cbwinslow;


--
-- Name: TABLE opencivicdata_person; Type: ACL; Schema: openstates_source; Owner: postgres
--

GRANT SELECT ON TABLE openstates_source.opencivicdata_person TO cbwinslow;


--
-- Name: TABLE opencivicdata_billaction; Type: ACL; Schema: openstates_source; Owner: postgres
--

GRANT SELECT ON TABLE openstates_source.opencivicdata_billaction TO cbwinslow;


--
-- Name: TABLE opencivicdata_billdocument; Type: ACL; Schema: openstates_source; Owner: postgres
--

GRANT SELECT ON TABLE openstates_source.opencivicdata_billdocument TO cbwinslow;


--
-- Name: TABLE opencivicdata_billsponsorship; Type: ACL; Schema: openstates_source; Owner: postgres
--

GRANT SELECT ON TABLE openstates_source.opencivicdata_billsponsorship TO cbwinslow;


--
-- Name: TABLE opencivicdata_organization; Type: ACL; Schema: openstates_source; Owner: postgres
--

GRANT SELECT ON TABLE openstates_source.opencivicdata_organization TO cbwinslow;


--
-- Name: TABLE opencivicdata_personidentifier; Type: ACL; Schema: openstates_source; Owner: postgres
--

GRANT SELECT ON TABLE openstates_source.opencivicdata_personidentifier TO cbwinslow;


--
-- Name: TABLE opencivicdata_personvote; Type: ACL; Schema: openstates_source; Owner: postgres
--

GRANT SELECT ON TABLE openstates_source.opencivicdata_personvote TO cbwinslow;


--
-- Name: TABLE opencivicdata_voteevent; Type: ACL; Schema: openstates_source; Owner: postgres
--

GRANT SELECT ON TABLE openstates_source.opencivicdata_voteevent TO cbwinslow;


--
-- PostgreSQL database dump complete
--

\unrestrict opendiscourseschemasnapshot

