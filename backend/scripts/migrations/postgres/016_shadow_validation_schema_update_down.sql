ALTER TABLE validation.shadow_validation_results DROP COLUMN historical_airis_result;

ALTER TABLE validation.shadow_validation_results RENAME COLUMN production_result TO old_result_payload;
ALTER TABLE validation.shadow_validation_results RENAME COLUMN shadow_result TO new_result_payload;
ALTER TABLE validation.shadow_validation_results RENAME COLUMN score_difference TO score_delta;
ALTER TABLE validation.shadow_validation_results RENAME COLUMN department_difference TO department_delta;
ALTER TABLE validation.shadow_validation_results RENAME COLUMN designation_difference TO designation_delta;
ALTER TABLE validation.shadow_validation_results RENAME COLUMN status_difference TO classification_delta;
ALTER TABLE validation.shadow_validation_results RENAME COLUMN evidence_difference TO reason_and_evidence_delta;

DELETE FROM validation.airis_historical_benchmarks WHERE status_id IN (4, 5, 6, 7);
