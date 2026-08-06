CREATE SCHEMA IF NOT EXISTS validation;

CREATE TABLE validation.shadow_validation_runs (
    id BIGSERIAL PRIMARY KEY,
    candidate_id BIGINT NOT NULL,
    vacancy_id BIGINT,
    is_historical BOOLEAN NOT NULL DEFAULT FALSE,
    run_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE,
    status VARCHAR(20) NOT NULL
);
CREATE INDEX ix_shadow_validation_runs_id ON validation.shadow_validation_runs (id);

CREATE TABLE validation.shadow_validation_results (
    id BIGSERIAL PRIMARY KEY,
    run_id BIGINT NOT NULL REFERENCES validation.shadow_validation_runs(id),
    airis_status_id BIGINT,
    airis_is_hired BOOLEAN,
    cvai_score NUMERIC,
    cvai_recommendation VARCHAR(50),
    old_result_payload JSONB,
    new_result_payload JSONB,
    score_delta NUMERIC,
    classification_delta VARCHAR,
    department_delta VARCHAR,
    designation_delta VARCHAR,
    reason_and_evidence_delta JSONB,
    is_false_positive BOOLEAN,
    is_false_negative BOOLEAN,
    is_agreement BOOLEAN
);
CREATE INDEX ix_shadow_validation_results_id ON validation.shadow_validation_results (id);

CREATE TABLE validation.airis_historical_benchmarks (
    id BIGSERIAL PRIMARY KEY,
    status_id BIGINT NOT NULL UNIQUE,
    status_name VARCHAR(100) NOT NULL,
    is_hired BOOLEAN NOT NULL,
    description VARCHAR
);
CREATE INDEX ix_airis_historical_benchmarks_id ON validation.airis_historical_benchmarks (id);

CREATE TABLE validation.validation_metrics_snapshots (
    id BIGSERIAL PRIMARY KEY,
    snapshot_date TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    total_runs INTEGER NOT NULL,
    false_positive_rate NUMERIC NOT NULL,
    false_negative_rate NUMERIC NOT NULL,
    agreement_rate NUMERIC NOT NULL,
    precision NUMERIC NOT NULL,
    recall NUMERIC NOT NULL,
    no_match_accuracy NUMERIC NOT NULL
);
CREATE INDEX ix_validation_metrics_snapshots_id ON validation.validation_metrics_snapshots (id);

CREATE TABLE validation.hr_disagreement_reviews (
    id BIGSERIAL PRIMARY KEY,
    result_id BIGINT NOT NULL REFERENCES validation.shadow_validation_results(id),
    hr_user_id BIGINT NOT NULL,
    agrees_with_cvai BOOLEAN NOT NULL,
    review_notes VARCHAR,
    reviewed_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);
CREATE INDEX ix_hr_disagreement_reviews_id ON validation.hr_disagreement_reviews (id);

-- Insert baseline status mappings for AIRIS
-- Assuming AIRIS standard statuses, normally inserted during seed/run
