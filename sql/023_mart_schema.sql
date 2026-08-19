-- Purpose-built research views (bill timelines, member records, place-year
-- panels, impact cohorts) live here, built by the dbt project under dbt/.
-- This schema is created by migration, not by dbt, so init-db always
-- guarantees it exists regardless of whether dbt has run yet.
CREATE SCHEMA IF NOT EXISTS mart;
