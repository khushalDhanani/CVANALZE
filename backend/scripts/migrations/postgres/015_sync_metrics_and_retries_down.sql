ALTER TABLE integration.sync_errors DROP COLUMN is_resolved;

ALTER TABLE integration.sync_runs DROP COLUMN watermark_after;
ALTER TABLE integration.sync_runs DROP COLUMN watermark_before;
ALTER TABLE integration.sync_runs DROP COLUMN records_failed;
ALTER TABLE integration.sync_runs DROP COLUMN records_skipped;
ALTER TABLE integration.sync_runs DROP COLUMN records_updated;
ALTER TABLE integration.sync_runs DROP COLUMN records_inserted;
ALTER TABLE integration.sync_runs DROP COLUMN records_read;

ALTER TABLE integration.sync_runs ADD COLUMN records_processed INTEGER NOT NULL DEFAULT 0;
ALTER TABLE integration.sync_runs ADD COLUMN error_count INTEGER NOT NULL DEFAULT 0;
