CREATE EXTENSION IF NOT EXISTS postgis;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE EXTENSION IF NOT EXISTS unaccent;

CREATE SCHEMA IF NOT EXISTS catalog;

CREATE SCHEMA IF NOT EXISTS core;

CREATE SCHEMA IF NOT EXISTS fact;

CREATE SCHEMA IF NOT EXISTS ingest;

CREATE SCHEMA IF NOT EXISTS stage;

CREATE SCHEMA IF NOT EXISTS leg;

CREATE SCHEMA IF NOT EXISTS mart;

CREATE TABLE catalog.provider (
    provider_id TEXT NOT NULL, 
    name TEXT NOT NULL, 
    base_url TEXT, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (provider_id)
);

CREATE TABLE catalog.basket (
    basket_id UUID DEFAULT gen_random_uuid() NOT NULL, 
    name TEXT NOT NULL, 
    state TEXT DEFAULT 'draft' NOT NULL, 
    metadata JSONB DEFAULT '{}'::jsonb NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (basket_id), 
    CONSTRAINT basket_state_check CHECK (state IN ('draft', 'review', 'approved', 'archived')), 
    UNIQUE (name)
);

CREATE TABLE core.geography (
    geography_id UUID DEFAULT gen_random_uuid() NOT NULL, 
    geography_type TEXT NOT NULL, 
    geoid TEXT NOT NULL, 
    name TEXT, 
    parent_geoid TEXT, 
    state_fips TEXT, 
    county_fips TEXT, 
    metadata JSONB DEFAULT '{}'::jsonb NOT NULL, 
    PRIMARY KEY (geography_id), 
    UNIQUE (geography_type, geoid)
);

CREATE TABLE core.jurisdiction (
    jurisdiction_id TEXT NOT NULL, 
    name TEXT NOT NULL, 
    classification TEXT NOT NULL, 
    metadata JSONB DEFAULT '{}'::jsonb NOT NULL, 
    PRIMARY KEY (jurisdiction_id)
);

CREATE TABLE core.person (
    person_id UUID DEFAULT gen_random_uuid() NOT NULL, 
    full_name TEXT NOT NULL, 
    given_name TEXT, 
    family_name TEXT, 
    metadata JSONB DEFAULT '{}'::jsonb NOT NULL, 
    PRIMARY KEY (person_id)
);

CREATE TABLE core.organization (
    organization_id UUID DEFAULT gen_random_uuid() NOT NULL, 
    organization_type TEXT NOT NULL, 
    name TEXT NOT NULL, 
    jurisdiction_geoid TEXT, 
    metadata JSONB DEFAULT '{}'::jsonb NOT NULL, 
    PRIMARY KEY (organization_id)
);

CREATE TABLE core.instrument (
    instrument_id UUID DEFAULT gen_random_uuid() NOT NULL, 
    instrument_type TEXT NOT NULL, 
    name TEXT, 
    currency TEXT, 
    metadata JSONB DEFAULT '{}'::jsonb NOT NULL, 
    PRIMARY KEY (instrument_id)
);

CREATE TABLE catalog.dataset (
    dataset_id TEXT NOT NULL, 
    provider_id TEXT NOT NULL, 
    title TEXT NOT NULL, 
    access_method TEXT, 
    grain_description TEXT, 
    refresh_cadence TEXT, 
    priority SMALLINT, 
    active BOOLEAN DEFAULT true NOT NULL, 
    metadata JSONB DEFAULT '{}'::jsonb NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (dataset_id), 
    FOREIGN KEY(provider_id) REFERENCES catalog.provider (provider_id)
);

CREATE TABLE core.person_identifier (
    person_id UUID NOT NULL, 
    namespace TEXT NOT NULL, 
    external_id TEXT NOT NULL, 
    valid_from DATE, 
    valid_to DATE, 
    PRIMARY KEY (namespace, external_id), 
    FOREIGN KEY(person_id) REFERENCES core.person (person_id)
);

CREATE TABLE core.organization_identifier (
    organization_id UUID NOT NULL, 
    namespace TEXT NOT NULL, 
    external_id TEXT NOT NULL, 
    metadata JSONB DEFAULT '{}'::jsonb NOT NULL, 
    PRIMARY KEY (namespace, external_id), 
    FOREIGN KEY(organization_id) REFERENCES core.organization (organization_id)
);

CREATE TABLE core.instrument_symbol (
    instrument_id UUID NOT NULL, 
    symbol TEXT NOT NULL, 
    exchange TEXT DEFAULT '' NOT NULL, 
    valid_from DATE NOT NULL, 
    valid_to DATE, 
    PRIMARY KEY (symbol, exchange, valid_from), 
    FOREIGN KEY(instrument_id) REFERENCES core.instrument (instrument_id)
);

CREATE TABLE ingest.artifact (
    artifact_id UUID DEFAULT gen_random_uuid() NOT NULL, 
    dataset_id TEXT NOT NULL, 
    remote_url TEXT NOT NULL, 
    local_path TEXT NOT NULL, 
    artifact_key TEXT NOT NULL, 
    period_start DATE, 
    period_end DATE, 
    content_type TEXT, 
    bytes_downloaded BIGINT, 
    checksum_sha256 TEXT, 
    status TEXT NOT NULL, 
    discovered_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    downloaded_at TIMESTAMP WITH TIME ZONE, 
    loaded_at TIMESTAMP WITH TIME ZONE, 
    metadata JSONB DEFAULT '{}'::jsonb NOT NULL, 
    error_message TEXT, 
    PRIMARY KEY (artifact_id), 
    UNIQUE (dataset_id, artifact_key), 
    CONSTRAINT artifact_status_check CHECK (status IN ('planned', 'downloading', 'downloaded', 'loaded', 'failed', 'skipped')), 
    FOREIGN KEY(dataset_id) REFERENCES catalog.dataset (dataset_id)
);

CREATE INDEX artifact_dataset_status_idx ON ingest.artifact (dataset_id, status);

CREATE TABLE catalog.dataset_field (
    dataset_id TEXT NOT NULL, 
    field_id TEXT NOT NULL, 
    valid_from DATE NOT NULL, 
    label TEXT, 
    data_type TEXT, 
    description TEXT, 
    valid_to DATE, 
    metadata JSONB DEFAULT '{}'::jsonb NOT NULL, 
    PRIMARY KEY (dataset_id, field_id, valid_from), 
    FOREIGN KEY(dataset_id) REFERENCES catalog.dataset (dataset_id)
);

CREATE TABLE catalog.plan (
    plan_id TEXT NOT NULL, 
    dataset_id TEXT NOT NULL, 
    handler TEXT NOT NULL, 
    cadence TEXT NOT NULL, 
    enabled BOOLEAN DEFAULT true NOT NULL, 
    parameters JSONB DEFAULT '{}'::jsonb NOT NULL, 
    metadata JSONB DEFAULT '{}'::jsonb NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (plan_id), 
    FOREIGN KEY(dataset_id) REFERENCES catalog.dataset (dataset_id)
);

CREATE TABLE catalog.discovery (
    discovery_id TEXT NOT NULL, 
    dataset_id TEXT NOT NULL, 
    state TEXT DEFAULT 'idle' NOT NULL, 
    cursor JSONB DEFAULT '{}'::jsonb NOT NULL, 
    statistics JSONB DEFAULT '{}'::jsonb NOT NULL, 
    error_message TEXT, 
    started_at TIMESTAMP WITH TIME ZONE, 
    finished_at TIMESTAMP WITH TIME ZONE, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (discovery_id), 
    CONSTRAINT discovery_state_check CHECK (state IN ('idle', 'running', 'paused', 'complete', 'failed')), 
    FOREIGN KEY(dataset_id) REFERENCES catalog.dataset (dataset_id)
);

CREATE TABLE ingest.run (
    run_id UUID DEFAULT gen_random_uuid() NOT NULL, 
    dataset_id TEXT NOT NULL, 
    mode TEXT NOT NULL, 
    status TEXT NOT NULL, 
    started_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    finished_at TIMESTAMP WITH TIME ZONE, 
    parameters JSONB DEFAULT '{}'::jsonb NOT NULL, 
    record_count BIGINT DEFAULT 0 NOT NULL, 
    error_message TEXT, 
    code_version TEXT, 
    PRIMARY KEY (run_id), 
    CONSTRAINT run_mode_check CHECK (mode IN ('backfill', 'incremental', 'manual', 'plan')), 
    CONSTRAINT run_status_check CHECK (status IN ('running', 'succeeded', 'failed', 'partial')), 
    FOREIGN KEY(dataset_id) REFERENCES catalog.dataset (dataset_id)
);

CREATE TABLE catalog.resource (
    resource_id UUID DEFAULT gen_random_uuid() NOT NULL, 
    dataset_id TEXT NOT NULL, 
    resource_key TEXT NOT NULL, 
    resource_type TEXT NOT NULL, 
    title TEXT NOT NULL, 
    summary TEXT, 
    universe TEXT, 
    release_year INTEGER, 
    metadata JSONB DEFAULT '{}'::jsonb NOT NULL, 
    source_artifact_id UUID, 
    discovered_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (resource_id), 
    UNIQUE (dataset_id, resource_key), 
    FOREIGN KEY(dataset_id) REFERENCES catalog.dataset (dataset_id), 
    FOREIGN KEY(source_artifact_id) REFERENCES ingest.artifact (artifact_id)
);

CREATE INDEX resource_fts_idx ON catalog.resource USING gin (to_tsvector('english', coalesce(resource_key, '') || ' ' || coalesce(title, '') || ' ' || coalesce(summary, '') || ' ' || coalesce(universe, '') || ' ' || coalesce(resource_type, '') || ' ' || coalesce(metadata::text, '')));

CREATE INDEX resource_search_idx ON catalog.resource (dataset_id, release_year, resource_type);

CREATE INDEX resource_title_trgm_idx ON catalog.resource USING gin (title gin_trgm_ops);

CREATE TABLE catalog.snapshot (
    snapshot_id UUID DEFAULT gen_random_uuid() NOT NULL, 
    dataset_id TEXT NOT NULL, 
    source_url TEXT NOT NULL, 
    checksum_sha256 TEXT NOT NULL, 
    artifact_id UUID, 
    captured_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    metadata JSONB DEFAULT '{}'::jsonb NOT NULL, 
    PRIMARY KEY (snapshot_id), 
    UNIQUE (dataset_id, checksum_sha256), 
    FOREIGN KEY(dataset_id) REFERENCES catalog.dataset (dataset_id), 
    FOREIGN KEY(artifact_id) REFERENCES ingest.artifact (artifact_id)
);

CREATE TABLE fact.population_estimate (
    population_estimate_id UUID DEFAULT gen_random_uuid() NOT NULL, 
    release_vintage INTEGER NOT NULL, 
    estimate_year INTEGER NOT NULL, 
    geography_id UUID NOT NULL, 
    population BIGINT NOT NULL, 
    source_artifact_id UUID NOT NULL, 
    source_member TEXT NOT NULL, 
    source_ordinal BIGINT NOT NULL, 
    loaded_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (population_estimate_id), 
    UNIQUE (source_artifact_id, source_member, source_ordinal, estimate_year), 
    FOREIGN KEY(geography_id) REFERENCES core.geography (geography_id), 
    FOREIGN KEY(source_artifact_id) REFERENCES ingest.artifact (artifact_id)
);

CREATE INDEX population_estimate_lookup_idx ON fact.population_estimate (release_vintage, estimate_year, geography_id);

CREATE TABLE fact.business_pattern (
    business_pattern_id UUID DEFAULT gen_random_uuid() NOT NULL, 
    release_year INTEGER NOT NULL, 
    geography_id UUID NOT NULL, 
    naics TEXT NOT NULL, 
    legal_form TEXT DEFAULT '' NOT NULL, 
    establishments BIGINT, 
    employment BIGINT, 
    first_quarter_payroll NUMERIC, 
    annual_payroll NUMERIC, 
    flags JSONB DEFAULT '{}'::jsonb NOT NULL, 
    source_artifact_id UUID NOT NULL, 
    source_member TEXT NOT NULL, 
    source_ordinal BIGINT NOT NULL, 
    loaded_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (business_pattern_id), 
    UNIQUE (source_artifact_id, source_member, source_ordinal), 
    FOREIGN KEY(geography_id) REFERENCES core.geography (geography_id), 
    FOREIGN KEY(source_artifact_id) REFERENCES ingest.artifact (artifact_id)
);

CREATE INDEX business_pattern_lookup_idx ON fact.business_pattern (release_year, geography_id, naics);

CREATE TABLE fact.acs_bulk_estimate (
    acs_bulk_estimate_id UUID DEFAULT gen_random_uuid() NOT NULL, 
    release_year INTEGER NOT NULL, 
    geography_id UUID NOT NULL, 
    table_id TEXT NOT NULL, 
    field_id TEXT NOT NULL, 
    measure TEXT NOT NULL, 
    value NUMERIC, 
    source_artifact_id UUID NOT NULL, 
    source_ordinal BIGINT NOT NULL, 
    PRIMARY KEY (acs_bulk_estimate_id), 
    CONSTRAINT acs_bulk_estimate_measure_check CHECK (measure IN ('estimate', 'margin_of_error')), 
    UNIQUE (source_artifact_id, source_ordinal, field_id), 
    FOREIGN KEY(geography_id) REFERENCES core.geography (geography_id), 
    FOREIGN KEY(source_artifact_id) REFERENCES ingest.artifact (artifact_id)
);

CREATE INDEX acs_bulk_estimate_lookup_idx ON fact.acs_bulk_estimate (release_year, geography_id, table_id, field_id);

CREATE TABLE fact.decennial_dhc_value (
    dhc_value_id UUID DEFAULT gen_random_uuid() NOT NULL, 
    release_year INTEGER NOT NULL, 
    geography_id UUID NOT NULL, 
    table_id TEXT NOT NULL, 
    variable_id TEXT NOT NULL, 
    value BIGINT, 
    source_artifact_id UUID NOT NULL, 
    source_member TEXT NOT NULL, 
    source_ordinal BIGINT NOT NULL, 
    PRIMARY KEY (dhc_value_id), 
    UNIQUE (source_artifact_id, source_member, source_ordinal, variable_id), 
    FOREIGN KEY(geography_id) REFERENCES core.geography (geography_id), 
    FOREIGN KEY(source_artifact_id) REFERENCES ingest.artifact (artifact_id)
);

CREATE INDEX dhc_value_lookup_idx ON fact.decennial_dhc_value (release_year, geography_id, table_id, variable_id);

CREATE TABLE ingest.cursor (
    plan_id TEXT NOT NULL, 
    cursor JSONB DEFAULT '{}'::jsonb NOT NULL, 
    successful_run_id UUID, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (plan_id), 
    FOREIGN KEY(plan_id) REFERENCES catalog.plan (plan_id), 
    FOREIGN KEY(successful_run_id) REFERENCES ingest.run (run_id)
);

CREATE TABLE ingest.raw_payload (
    payload_id UUID DEFAULT gen_random_uuid() NOT NULL, 
    run_id UUID NOT NULL, 
    source_url TEXT NOT NULL, 
    fetched_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    http_status INTEGER, 
    content_type TEXT, 
    checksum_sha256 TEXT NOT NULL, 
    payload JSONB NOT NULL, 
    PRIMARY KEY (payload_id), 
    UNIQUE (run_id, checksum_sha256), 
    FOREIGN KEY(run_id) REFERENCES ingest.run (run_id)
);

CREATE INDEX raw_payload_run_idx ON ingest.raw_payload (run_id);

CREATE TABLE ingest.resume_cursor (
    dataset_id TEXT NOT NULL, 
    cursor_key TEXT NOT NULL, 
    cursor JSONB DEFAULT '{}'::jsonb NOT NULL, 
    source_artifact_id UUID, 
    last_run_id UUID, 
    state TEXT NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (dataset_id, cursor_key), 
    CONSTRAINT resume_cursor_state_check CHECK (state IN ('running', 'paused', 'complete')), 
    FOREIGN KEY(dataset_id) REFERENCES catalog.dataset (dataset_id), 
    FOREIGN KEY(source_artifact_id) REFERENCES ingest.artifact (artifact_id), 
    FOREIGN KEY(last_run_id) REFERENCES ingest.run (run_id)
);

CREATE TABLE ingest.identity_exception (
    identity_exception_id UUID DEFAULT gen_random_uuid() NOT NULL, 
    dataset_id TEXT NOT NULL, 
    run_id UUID NOT NULL, 
    source_artifact_id UUID NOT NULL, 
    congress INTEGER NOT NULL, 
    kind TEXT NOT NULL, 
    namespace TEXT NOT NULL, 
    external_id TEXT NOT NULL, 
    reason TEXT NOT NULL, 
    reference_count INTEGER DEFAULT 1 NOT NULL, 
    first_seen_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    last_seen_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (identity_exception_id), 
    CONSTRAINT identity_exception_kind_check CHECK (kind IN ('voter')), 
    CONSTRAINT identity_exception_reference_count_check CHECK (reference_count > 0), 
    UNIQUE (run_id, kind, namespace, external_id, reason), 
    FOREIGN KEY(dataset_id) REFERENCES catalog.dataset (dataset_id), 
    FOREIGN KEY(run_id) REFERENCES ingest.run (run_id), 
    FOREIGN KEY(source_artifact_id) REFERENCES ingest.artifact (artifact_id)
);

CREATE INDEX identity_exception_lookup_idx ON ingest.identity_exception (congress, namespace, external_id);

CREATE TABLE stage.cbp_row (
    artifact_id UUID NOT NULL, 
    source_member TEXT NOT NULL, 
    source_ordinal BIGINT NOT NULL, 
    geography_level TEXT NOT NULL, 
    raw JSONB NOT NULL, 
    staged_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (artifact_id, source_member, source_ordinal), 
    FOREIGN KEY(artifact_id) REFERENCES ingest.artifact (artifact_id)
);

CREATE TABLE stage.pep_row (
    artifact_id UUID NOT NULL, 
    source_member TEXT NOT NULL, 
    source_ordinal BIGINT NOT NULL, 
    geography_level TEXT NOT NULL, 
    raw JSONB NOT NULL, 
    staged_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (artifact_id, source_member, source_ordinal), 
    FOREIGN KEY(artifact_id) REFERENCES ingest.artifact (artifact_id)
);

CREATE TABLE stage.tiger_feature (
    artifact_id UUID NOT NULL, 
    layer TEXT NOT NULL, 
    source_ordinal BIGINT NOT NULL, 
    geoid TEXT NOT NULL, 
    name TEXT, 
    state_fips TEXT, 
    county_fips TEXT, 
    raw JSONB NOT NULL, 
    geom geometry(GEOMETRY,4326) NOT NULL, 
    staged_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (artifact_id, source_ordinal), 
    FOREIGN KEY(artifact_id) REFERENCES ingest.artifact (artifact_id)
);

CREATE INDEX tiger_feature_geom_idx ON stage.tiger_feature USING gist (geom);

CREATE TABLE stage.dhc_geo_row (
    artifact_id UUID NOT NULL, 
    source_member TEXT NOT NULL, 
    source_ordinal BIGINT NOT NULL, 
    logrecno TEXT NOT NULL, 
    sumlev TEXT NOT NULL, 
    geoid TEXT, 
    raw JSONB NOT NULL, 
    PRIMARY KEY (artifact_id, source_member, source_ordinal), 
    FOREIGN KEY(artifact_id) REFERENCES ingest.artifact (artifact_id)
);

CREATE INDEX dhc_geo_lookup_idx ON stage.dhc_geo_row (artifact_id, logrecno, sumlev);

CREATE TABLE stage.acs_bulk_row (
    artifact_id UUID NOT NULL, 
    source_ordinal BIGINT NOT NULL, 
    release_year INTEGER NOT NULL, 
    table_id TEXT NOT NULL, 
    geography_type TEXT NOT NULL, 
    geoid TEXT NOT NULL, 
    raw JSONB NOT NULL, 
    PRIMARY KEY (artifact_id, source_ordinal), 
    FOREIGN KEY(artifact_id) REFERENCES ingest.artifact (artifact_id)
);

CREATE TABLE stage.fec_row (
    artifact_id UUID NOT NULL, 
    family TEXT NOT NULL, 
    cycle SMALLINT NOT NULL, 
    source_ordinal BIGINT NOT NULL, 
    raw JSONB NOT NULL, 
    staged_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (artifact_id, source_ordinal), 
    FOREIGN KEY(artifact_id) REFERENCES ingest.artifact (artifact_id)
);

CREATE INDEX fec_row_family_cycle_idx ON stage.fec_row (family, cycle);

CREATE TABLE catalog.resource_field (
    resource_id UUID NOT NULL, 
    field_key TEXT NOT NULL, 
    label TEXT, 
    description TEXT, 
    data_type TEXT, 
    metadata JSONB DEFAULT '{}'::jsonb NOT NULL, 
    discovered_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (resource_id, field_key), 
    FOREIGN KEY(resource_id) REFERENCES catalog.resource (resource_id) ON DELETE CASCADE
);

CREATE TABLE catalog.basket_item (
    basket_id UUID NOT NULL, 
    resource_id UUID NOT NULL, 
    selected_fields JSONB DEFAULT '[]'::jsonb NOT NULL, 
    metadata JSONB DEFAULT '{}'::jsonb NOT NULL, 
    added_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (basket_id, resource_id), 
    FOREIGN KEY(basket_id) REFERENCES catalog.basket (basket_id) ON DELETE CASCADE, 
    FOREIGN KEY(resource_id) REFERENCES catalog.resource (resource_id) ON DELETE RESTRICT
);

CREATE TABLE catalog.snapshot_resource (
    snapshot_id UUID NOT NULL, 
    resource_id UUID NOT NULL, 
    PRIMARY KEY (snapshot_id, resource_id), 
    FOREIGN KEY(snapshot_id) REFERENCES catalog.snapshot (snapshot_id) ON DELETE CASCADE, 
    FOREIGN KEY(resource_id) REFERENCES catalog.resource (resource_id) ON DELETE RESTRICT
);

CREATE TABLE fact.measurement (
    measurement_id UUID DEFAULT gen_random_uuid() NOT NULL, 
    dataset_id TEXT NOT NULL, 
    field_id TEXT NOT NULL, 
    geography_id UUID, 
    period_start DATE NOT NULL, 
    period_end DATE, 
    vintage_date DATE, 
    value_numeric NUMERIC, 
    value_text TEXT, 
    unit TEXT, 
    margin_of_error NUMERIC, 
    flags JSONB DEFAULT '{}'::jsonb NOT NULL, 
    source_payload_id UUID NOT NULL, 
    PRIMARY KEY (measurement_id), 
    UNIQUE NULLS NOT DISTINCT (dataset_id, field_id, geography_id, period_start, period_end, vintage_date), 
    FOREIGN KEY(dataset_id) REFERENCES catalog.dataset (dataset_id), 
    FOREIGN KEY(geography_id) REFERENCES core.geography (geography_id), 
    FOREIGN KEY(source_payload_id) REFERENCES ingest.raw_payload (payload_id)
);

CREATE INDEX measurement_lookup_idx ON fact.measurement (dataset_id, field_id, period_start);

CREATE TABLE core.geography_boundary (
    boundary_id UUID DEFAULT gen_random_uuid() NOT NULL, 
    geography_id UUID NOT NULL, 
    boundary_vintage INTEGER NOT NULL, 
    valid_from DATE, 
    valid_to DATE, 
    geom geometry(GEOMETRY,4326) NOT NULL, 
    source_payload_id UUID, 
    source_artifact_id UUID, 
    PRIMARY KEY (boundary_id), 
    UNIQUE (geography_id, boundary_vintage), 
    FOREIGN KEY(geography_id) REFERENCES core.geography (geography_id), 
    FOREIGN KEY(source_payload_id) REFERENCES ingest.raw_payload (payload_id), 
    FOREIGN KEY(source_artifact_id) REFERENCES ingest.artifact (artifact_id)
);

CREATE INDEX geography_boundary_geom_idx ON core.geography_boundary USING gist (geom);

CREATE TABLE core.legislative_session (
    legislative_session_id UUID DEFAULT gen_random_uuid() NOT NULL, 
    jurisdiction_id TEXT NOT NULL, 
    identifier TEXT NOT NULL, 
    name TEXT, 
    classification TEXT, 
    starts_on DATE, 
    ends_on DATE, 
    active BOOLEAN, 
    source_artifact_id UUID, 
    source_payload_id UUID, 
    metadata JSONB DEFAULT '{}'::jsonb NOT NULL, 
    PRIMARY KEY (legislative_session_id), 
    UNIQUE (jurisdiction_id, identifier), 
    CONSTRAINT legislative_session_check CHECK (source_artifact_id IS NOT NULL OR source_payload_id IS NOT NULL), 
    FOREIGN KEY(jurisdiction_id) REFERENCES core.jurisdiction (jurisdiction_id), 
    FOREIGN KEY(source_artifact_id) REFERENCES ingest.artifact (artifact_id), 
    FOREIGN KEY(source_payload_id) REFERENCES ingest.raw_payload (payload_id)
);

CREATE TABLE core.document (
    document_id UUID DEFAULT gen_random_uuid() NOT NULL, 
    document_type TEXT NOT NULL, 
    source_key TEXT NOT NULL, 
    title TEXT, 
    published_at TIMESTAMP WITH TIME ZONE, 
    language TEXT DEFAULT 'en' NOT NULL, 
    canonical_url TEXT, 
    checksum_sha256 TEXT, 
    metadata JSONB DEFAULT '{}'::jsonb NOT NULL, 
    source_payload_id UUID, 
    artifact_id UUID, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (document_id), 
    UNIQUE (document_type, source_key), 
    FOREIGN KEY(source_payload_id) REFERENCES ingest.raw_payload (payload_id), 
    FOREIGN KEY(artifact_id) REFERENCES ingest.artifact (artifact_id)
);

CREATE TABLE fact.market_bar (
    instrument_id UUID NOT NULL, 
    trade_date DATE NOT NULL, 
    interval TEXT DEFAULT '1d' NOT NULL, 
    open NUMERIC, 
    high NUMERIC, 
    low NUMERIC, 
    close NUMERIC, 
    adjusted_close NUMERIC, 
    volume NUMERIC, 
    source_payload_id UUID NOT NULL, 
    PRIMARY KEY (instrument_id, trade_date, interval), 
    FOREIGN KEY(instrument_id) REFERENCES core.instrument (instrument_id), 
    FOREIGN KEY(source_payload_id) REFERENCES ingest.raw_payload (payload_id)
);

CREATE TABLE core.bill (
    bill_id UUID DEFAULT gen_random_uuid() NOT NULL, 
    jurisdiction TEXT NOT NULL, 
    legislative_session TEXT NOT NULL, 
    bill_type TEXT NOT NULL, 
    bill_number TEXT NOT NULL, 
    title TEXT, 
    introduced_date DATE, 
    latest_action_date DATE, 
    latest_action TEXT, 
    metadata JSONB DEFAULT '{}'::jsonb NOT NULL, 
    legislative_session_id UUID, 
    ocd_id TEXT, 
    PRIMARY KEY (bill_id), 
    UNIQUE (jurisdiction, legislative_session, bill_type, bill_number), 
    FOREIGN KEY(legislative_session_id) REFERENCES core.legislative_session (legislative_session_id)
);

CREATE UNIQUE INDEX bill_ocd_id_idx ON core.bill (ocd_id) WHERE ocd_id IS NOT NULL;

CREATE TABLE core.membership (
    membership_id UUID DEFAULT gen_random_uuid() NOT NULL, 
    person_id UUID NOT NULL, 
    organization_id UUID NOT NULL, 
    legislative_session_id UUID, 
    role TEXT NOT NULL, 
    start_date DATE, 
    end_date DATE, 
    source_artifact_id UUID, 
    source_payload_id UUID, 
    metadata JSONB DEFAULT '{}'::jsonb NOT NULL, 
    PRIMARY KEY (membership_id), 
    CONSTRAINT membership_check CHECK (source_artifact_id IS NOT NULL OR source_payload_id IS NOT NULL), 
    FOREIGN KEY(person_id) REFERENCES core.person (person_id), 
    FOREIGN KEY(organization_id) REFERENCES core.organization (organization_id), 
    FOREIGN KEY(legislative_session_id) REFERENCES core.legislative_session (legislative_session_id), 
    FOREIGN KEY(source_artifact_id) REFERENCES ingest.artifact (artifact_id), 
    FOREIGN KEY(source_payload_id) REFERENCES ingest.raw_payload (payload_id)
);

CREATE INDEX membership_person_idx ON core.membership (person_id);

CREATE INDEX membership_organization_idx ON core.membership (organization_id);

CREATE TABLE core.document_chunk (
    chunk_id UUID DEFAULT gen_random_uuid() NOT NULL, 
    document_id UUID NOT NULL, 
    ordinal INTEGER NOT NULL, 
    text TEXT NOT NULL, 
    token_count INTEGER, 
    checksum_sha256 TEXT NOT NULL, 
    metadata JSONB DEFAULT '{}'::jsonb NOT NULL, 
    PRIMARY KEY (chunk_id), 
    CONSTRAINT document_chunk_ordinal_check CHECK (ordinal >= 0), 
    UNIQUE (document_id, ordinal), 
    UNIQUE (document_id, checksum_sha256), 
    FOREIGN KEY(document_id) REFERENCES core.document (document_id)
);

CREATE TABLE core.bill_identifier (
    bill_id UUID NOT NULL, 
    namespace TEXT NOT NULL, 
    external_id TEXT NOT NULL, 
    source_artifact_id UUID, 
    source_payload_id UUID, 
    source_url TEXT, 
    metadata JSONB DEFAULT '{}'::jsonb NOT NULL, 
    PRIMARY KEY (namespace, external_id), 
    CONSTRAINT bill_identifier_check CHECK (source_artifact_id IS NOT NULL OR source_payload_id IS NOT NULL), 
    FOREIGN KEY(bill_id) REFERENCES core.bill (bill_id), 
    FOREIGN KEY(source_artifact_id) REFERENCES ingest.artifact (artifact_id), 
    FOREIGN KEY(source_payload_id) REFERENCES ingest.raw_payload (payload_id)
);

CREATE INDEX bill_identifier_bill_idx ON core.bill_identifier (bill_id);

CREATE TABLE core.bill_action (
    bill_action_id UUID DEFAULT gen_random_uuid() NOT NULL, 
    bill_id UUID NOT NULL, 
    action_date TIMESTAMP WITH TIME ZONE, 
    description TEXT NOT NULL, 
    classification TEXT[], 
    source_payload_id UUID, 
    source_artifact_id UUID, 
    source_member TEXT, 
    source_ordinal INTEGER, 
    metadata JSONB DEFAULT '{}'::jsonb NOT NULL, 
    PRIMARY KEY (bill_action_id), 
    CONSTRAINT bill_action_source_evidence CHECK (source_artifact_id IS NOT NULL OR source_payload_id IS NOT NULL), 
    FOREIGN KEY(bill_id) REFERENCES core.bill (bill_id), 
    FOREIGN KEY(source_payload_id) REFERENCES ingest.raw_payload (payload_id), 
    FOREIGN KEY(source_artifact_id) REFERENCES ingest.artifact (artifact_id)
);

CREATE UNIQUE INDEX bill_action_source_member_idx ON core.bill_action (bill_id, source_artifact_id, source_member, source_ordinal) WHERE source_artifact_id IS NOT NULL;

CREATE TABLE core.bill_sponsorship (
    bill_sponsorship_id UUID DEFAULT gen_random_uuid() NOT NULL, 
    bill_id UUID NOT NULL, 
    person_id UUID, 
    member_namespace TEXT DEFAULT 'bioguide' NOT NULL, 
    member_external_id TEXT NOT NULL, 
    role TEXT NOT NULL, 
    source_artifact_id UUID, 
    source_payload_id UUID, 
    source_member TEXT, 
    metadata JSONB DEFAULT '{}'::jsonb NOT NULL, 
    PRIMARY KEY (bill_sponsorship_id), 
    CONSTRAINT bill_sponsorship_role_check CHECK (role IN ('sponsor', 'cosponsor')), 
    CONSTRAINT bill_sponsorship_check CHECK (source_artifact_id IS NOT NULL OR source_payload_id IS NOT NULL), 
    UNIQUE NULLS NOT DISTINCT (bill_id, member_namespace, member_external_id, role, source_artifact_id, source_member), 
    FOREIGN KEY(bill_id) REFERENCES core.bill (bill_id), 
    FOREIGN KEY(person_id) REFERENCES core.person (person_id), 
    FOREIGN KEY(source_artifact_id) REFERENCES ingest.artifact (artifact_id), 
    FOREIGN KEY(source_payload_id) REFERENCES ingest.raw_payload (payload_id)
);

CREATE INDEX bill_sponsorship_person_idx ON core.bill_sponsorship (person_id);

CREATE TABLE core.bill_committee (
    bill_committee_id UUID DEFAULT gen_random_uuid() NOT NULL, 
    bill_id UUID NOT NULL, 
    namespace TEXT DEFAULT 'congress.gov.committee' NOT NULL, 
    external_id TEXT NOT NULL, 
    name TEXT, 
    chamber TEXT, 
    source_artifact_id UUID, 
    source_payload_id UUID, 
    source_member TEXT, 
    metadata JSONB DEFAULT '{}'::jsonb NOT NULL, 
    PRIMARY KEY (bill_committee_id), 
    CONSTRAINT bill_committee_check CHECK (source_artifact_id IS NOT NULL OR source_payload_id IS NOT NULL), 
    UNIQUE NULLS NOT DISTINCT (bill_id, namespace, external_id, source_artifact_id, source_member), 
    FOREIGN KEY(bill_id) REFERENCES core.bill (bill_id), 
    FOREIGN KEY(source_artifact_id) REFERENCES ingest.artifact (artifact_id), 
    FOREIGN KEY(source_payload_id) REFERENCES ingest.raw_payload (payload_id)
);

CREATE TABLE core.bill_subject (
    bill_subject_id UUID DEFAULT gen_random_uuid() NOT NULL, 
    bill_id UUID NOT NULL, 
    namespace TEXT DEFAULT 'congress.gov.subject' NOT NULL, 
    external_id TEXT NOT NULL, 
    label TEXT NOT NULL, 
    source_artifact_id UUID, 
    source_payload_id UUID, 
    source_member TEXT, 
    metadata JSONB DEFAULT '{}'::jsonb NOT NULL, 
    PRIMARY KEY (bill_subject_id), 
    CONSTRAINT bill_subject_check CHECK (source_artifact_id IS NOT NULL OR source_payload_id IS NOT NULL), 
    UNIQUE NULLS NOT DISTINCT (bill_id, namespace, external_id, source_artifact_id, source_member), 
    FOREIGN KEY(bill_id) REFERENCES core.bill (bill_id), 
    FOREIGN KEY(source_artifact_id) REFERENCES ingest.artifact (artifact_id), 
    FOREIGN KEY(source_payload_id) REFERENCES ingest.raw_payload (payload_id)
);

CREATE TABLE core.bill_document (
    bill_id UUID NOT NULL, 
    document_id UUID NOT NULL, 
    relation TEXT DEFAULT 'text' NOT NULL, 
    PRIMARY KEY (bill_id, document_id, relation), 
    FOREIGN KEY(bill_id) REFERENCES core.bill (bill_id), 
    FOREIGN KEY(document_id) REFERENCES core.document (document_id)
);

CREATE TABLE core.roll_call (
    roll_call_id UUID DEFAULT gen_random_uuid() NOT NULL, 
    jurisdiction TEXT NOT NULL, 
    legislative_session TEXT NOT NULL, 
    chamber TEXT, 
    external_id TEXT NOT NULL, 
    occurred_at TIMESTAMP WITH TIME ZONE, 
    question TEXT, 
    result TEXT, 
    metadata JSONB DEFAULT '{}'::jsonb NOT NULL, 
    bill_id UUID, 
    legislative_session_id UUID, 
    organization_id UUID, 
    ocd_id TEXT, 
    PRIMARY KEY (roll_call_id), 
    UNIQUE (jurisdiction, legislative_session, external_id), 
    FOREIGN KEY(bill_id) REFERENCES core.bill (bill_id), 
    FOREIGN KEY(legislative_session_id) REFERENCES core.legislative_session (legislative_session_id), 
    FOREIGN KEY(organization_id) REFERENCES core.organization (organization_id)
);

CREATE UNIQUE INDEX roll_call_ocd_id_idx ON core.roll_call (ocd_id) WHERE ocd_id IS NOT NULL;

CREATE TABLE core.embedding (
    embedding_id UUID DEFAULT gen_random_uuid() NOT NULL, 
    chunk_id UUID NOT NULL, 
    model TEXT NOT NULL, 
    dimensions INTEGER NOT NULL, 
    vector_values REAL[] NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (embedding_id), 
    CONSTRAINT embedding_dimensions_check CHECK (dimensions > 0), 
    CONSTRAINT embedding_check CHECK (cardinality(vector_values) = dimensions), 
    UNIQUE (chunk_id, model), 
    FOREIGN KEY(chunk_id) REFERENCES core.document_chunk (chunk_id)
);

CREATE TABLE fact.member_vote (
    roll_call_id UUID NOT NULL, 
    person_id UUID NOT NULL, 
    position TEXT NOT NULL, 
    source_payload_id UUID, 
    source_artifact_id UUID, 
    PRIMARY KEY (roll_call_id, person_id), 
    CONSTRAINT member_vote_source_evidence CHECK (source_artifact_id IS NOT NULL OR source_payload_id IS NOT NULL), 
    FOREIGN KEY(roll_call_id) REFERENCES core.roll_call (roll_call_id), 
    FOREIGN KEY(person_id) REFERENCES core.person (person_id), 
    FOREIGN KEY(source_payload_id) REFERENCES ingest.raw_payload (payload_id), 
    FOREIGN KEY(source_artifact_id) REFERENCES ingest.artifact (artifact_id)
);

