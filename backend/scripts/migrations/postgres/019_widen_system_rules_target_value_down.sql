-- Migration 019 Down: Revert system_rules.target_value to VARCHAR(255).

ALTER TABLE cvai.system_rules ALTER COLUMN target_value TYPE VARCHAR(255);
