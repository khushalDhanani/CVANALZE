ALTER TABLE validation.shadow_validation_results RENAME COLUMN old_result_payload TO production_result;
ALTER TABLE validation.shadow_validation_results RENAME COLUMN new_result_payload TO shadow_result;
ALTER TABLE validation.shadow_validation_results RENAME COLUMN score_delta TO score_difference;
ALTER TABLE validation.shadow_validation_results RENAME COLUMN department_delta TO department_difference;
ALTER TABLE validation.shadow_validation_results RENAME COLUMN designation_delta TO designation_difference;
ALTER TABLE validation.shadow_validation_results RENAME COLUMN classification_delta TO status_difference;
ALTER TABLE validation.shadow_validation_results RENAME COLUMN reason_and_evidence_delta TO evidence_difference;

ALTER TABLE validation.shadow_validation_results ADD COLUMN historical_airis_result JSONB;

-- Seed baseline AIRIS statuses resolving the placeholder IDs
INSERT INTO validation.airis_historical_benchmarks (status_id, status_name, is_hired, description)
VALUES 
    (4, 'Shortlisted', true, 'Candidate was shortlisted'),
    (5, 'Interviewed', true, 'Candidate was interviewed'),
    (6, 'Offered', true, 'Candidate was offered the position'),
    (7, 'Hired', true, 'Candidate accepted the offer and was hired')
ON CONFLICT (status_id) DO NOTHING;
