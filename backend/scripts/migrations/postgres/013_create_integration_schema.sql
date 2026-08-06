CREATE SCHEMA IF NOT EXISTS integration;

CREATE TABLE integration.sync_runs (
    id SERIAL PRIMARY KEY,
    entity_type VARCHAR(50) NOT NULL,
    status VARCHAR(20) NOT NULL,
    started_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE,
    records_processed INTEGER NOT NULL DEFAULT 0,
    error_count INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX ix_sync_runs_id ON integration.sync_runs (id);

CREATE TABLE integration.sync_watermarks (
    entity_type VARCHAR(50) PRIMARY KEY,
    last_source_updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
    synced_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE TABLE integration.sync_errors (
    id BIGSERIAL PRIMARY KEY,
    sync_run_id INTEGER NOT NULL REFERENCES integration.sync_runs(id),
    entity_type VARCHAR(50) NOT NULL,
    source_id VARCHAR(100) NOT NULL,
    error_type VARCHAR(100) NOT NULL,
    error_message TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);
CREATE INDEX ix_sync_errors_id ON integration.sync_errors (id);

-- Snapshot Tables
CREATE TABLE integration.department_snapshots (
    source_id VARCHAR(100) PRIMARY KEY,
    source_hash VARCHAR(64) NOT NULL,
    source_updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    synced_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    payload JSONB NOT NULL
);
CREATE INDEX ix_department_snapshots_is_active ON integration.department_snapshots (is_active);

CREATE TABLE integration.designation_snapshots (
    source_id VARCHAR(100) PRIMARY KEY,
    source_hash VARCHAR(64) NOT NULL,
    source_updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    synced_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    payload JSONB NOT NULL
);
CREATE INDEX ix_designation_snapshots_is_active ON integration.designation_snapshots (is_active);

CREATE TABLE integration.job_profile_snapshots (
    source_id VARCHAR(100) PRIMARY KEY,
    source_hash VARCHAR(64) NOT NULL,
    source_updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    synced_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    payload JSONB NOT NULL
);
CREATE INDEX ix_job_profile_snapshots_is_active ON integration.job_profile_snapshots (is_active);

CREATE TABLE integration.candidate_snapshots (
    source_id VARCHAR(100) PRIMARY KEY,
    source_hash VARCHAR(64) NOT NULL,
    source_updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    synced_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    payload JSONB NOT NULL
);
CREATE INDEX ix_candidate_snapshots_is_active ON integration.candidate_snapshots (is_active);

CREATE TABLE integration.vacancy_snapshots (
    source_id VARCHAR(100) PRIMARY KEY,
    source_hash VARCHAR(64) NOT NULL,
    source_updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    synced_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    payload JSONB NOT NULL
);
CREATE INDEX ix_vacancy_snapshots_is_active ON integration.vacancy_snapshots (is_active);
