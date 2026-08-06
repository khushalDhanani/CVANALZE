ALTER TABLE integration.sync_runs DROP COLUMN records_processed;
ALTER TABLE integration.sync_runs DROP COLUMN error_count;
ALTER TABLE integration.sync_runs ADD COLUMN records_read INTEGER NOT NULL DEFAULT 0;
ALTER TABLE integration.sync_runs ADD COLUMN records_inserted INTEGER NOT NULL DEFAULT 0;
ALTER TABLE integration.sync_runs ADD COLUMN records_updated INTEGER NOT NULL DEFAULT 0;
ALTER TABLE integration.sync_runs ADD COLUMN records_skipped INTEGER NOT NULL DEFAULT 0;
ALTER TABLE integration.sync_runs ADD COLUMN records_failed INTEGER NOT NULL DEFAULT 0;
ALTER TABLE integration.sync_runs ADD COLUMN watermark_before TIMESTAMP WITH TIME ZONE;
ALTER TABLE integration.sync_runs ADD COLUMN watermark_after TIMESTAMP WITH TIME ZONE;

ALTER TABLE integration.sync_errors ADD COLUMN is_resolved BOOLEAN NOT NULL DEFAULT FALSE;
