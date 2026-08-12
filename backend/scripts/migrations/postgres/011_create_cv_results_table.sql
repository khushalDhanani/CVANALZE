-- 011_create_cv_results_table.sql

CREATE TABLE IF NOT EXISTS cvai.cv_results (
    cv_key VARCHAR PRIMARY KEY,
    status VARCHAR,
    parsed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    full_name VARCHAR,
    candidate_id VARCHAR,
    cv_id VARCHAR,
    cv_hash VARCHAR,
    resume_json JSONB,
    match_analysis JSONB,
    text_content TEXT,
    markdown_content TEXT,
    raw_data JSONB
);

CREATE INDEX IF NOT EXISTS ix_cv_results_cv_hash ON cvai.cv_results(cv_hash);
CREATE INDEX IF NOT EXISTS ix_cv_results_parsed_at ON cvai.cv_results(parsed_at);
