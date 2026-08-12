-- Migration 019: Widen system_rules.target_value to TEXT to match the SQLAlchemy model.
-- Rule metadata (recommendations, section_patterns, canonical_equivalents, etc.) exceeds VARCHAR(255).

ALTER TABLE cvai.system_rules ALTER COLUMN target_value TYPE TEXT;
