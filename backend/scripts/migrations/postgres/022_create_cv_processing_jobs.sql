CREATE SEQUENCE IF NOT EXISTS public.cv_processing_jobs_enqueue_seq START WITH 1 INCREMENT BY 1;

CREATE TABLE IF NOT EXISTS public.cv_processing_jobs (
    job_id VARCHAR(80) PRIMARY KEY,
    enqueue_sequence BIGINT NOT NULL DEFAULT nextval('public.cv_processing_jobs_enqueue_seq'),
    cv_key VARCHAR(255) NOT NULL,
    content_hash VARCHAR(64) NOT NULL,
    filename VARCHAR(255) NOT NULL,
    storage_filename VARCHAR(255) NOT NULL,
    content_type VARCHAR(160),
    candidate_id VARCHAR(255),
    source_candidate_id BIGINT,
    cv_id VARCHAR(255),
    parser_version VARCHAR(80) NOT NULL,
    schema_version VARCHAR(80) NOT NULL,
    state VARCHAR(32) NOT NULL,
    progress INTEGER NOT NULL DEFAULT 10 CHECK (progress BETWEEN 0 AND 100),
    stage VARCHAR(120) NOT NULL DEFAULT 'queued',
    message TEXT NOT NULL DEFAULT 'CV processing is queued.',
    execution_mode VARCHAR(32) NOT NULL,
    rq_job_id VARCHAR(160) UNIQUE,
    attempt INTEGER NOT NULL DEFAULT 0,
    max_attempts INTEGER NOT NULL DEFAULT 1,
    enqueue_count INTEGER NOT NULL DEFAULT 0,
    force_reprocess BOOLEAN NOT NULL DEFAULT FALSE,
    outcome VARCHAR(40),
    error JSONB,
    version INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMPTZ,
    heartbeat_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS ix_cv_processing_jobs_enqueue_sequence ON public.cv_processing_jobs (enqueue_sequence);
CREATE INDEX IF NOT EXISTS ix_cv_processing_jobs_cv_key ON public.cv_processing_jobs (cv_key);
CREATE INDEX IF NOT EXISTS ix_cv_processing_jobs_candidate_id ON public.cv_processing_jobs (candidate_id);
CREATE INDEX IF NOT EXISTS ix_cv_processing_jobs_cv_id ON public.cv_processing_jobs (cv_id);
CREATE INDEX IF NOT EXISTS ix_cv_processing_jobs_state ON public.cv_processing_jobs (state);
CREATE INDEX IF NOT EXISTS ix_cv_processing_jobs_updated_at ON public.cv_processing_jobs (updated_at);
CREATE INDEX IF NOT EXISTS ix_cv_processing_jobs_active_fifo
    ON public.cv_processing_jobs (enqueue_sequence)
    WHERE state IN ('QUEUED', 'PROCESSING', 'RETRYING');
