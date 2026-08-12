# Work Status

## Work Completed
1. **Hierarchy Validation Fix**: 
    - Updated `is_hierarchy_valid` to use tri-state logic (`True`, `False`, `None`) across schemas and the matching evaluator, preventing `None` from blocking valid matches.
    - Added `test_hierarchy_valid_tri_state` to ensure correct handling of all 3 states.
    - Corrected match service logs to clearly separate domain validity, hierarchy validity, and final genuine match decisions.
2. **Seed Data Migration**:
    - Audited and converted all legacy string keywords in `department_domains_seed.json` to the new `KeywordConfig` schema (`term`, `match_type`, `weight`).
    - Configured "IT" as a `CASE_SENSITIVE_ACRONYM` to fix the false-positive pronoun bug.
3. **Taxonomy Fix Validation**:
    - Verified that short-acronyms like HR and QA correctly maintain recall as `CASE_INSENSITIVE_TOKEN`.
    - Added/updated tests in `test_domain_matching.py` (`test_case_insensitive_lowercase_qa`, `test_genuine_active_vacancy_match`) and resolved test mock mismatches to ensure the new matching engine passes unit validation.
4. **Hiring Risks and Concerns Architecture (Chunk 9B)**:
    - Added `HiringRisk` schema and dynamic `HiringRiskConfig` to `app/core/rule_config_manager.py` to drive risk severity and policies.
    - Implemented `HiringRiskAnalyzer` to deterministically translate evaluation gaps (Missing Skills, Minimum Experience, Domain Caps, Unparseable Experience) into structured risks.
    - Integrated Gemma (`OllamaLLMService._execute_structured_generation`) to act merely as a human-readable explanation translator for the deterministic evidence. 
    - Forced all AI generation to respect strict JSON schema guarantees and ignore any hallucinated risks.
    - Verified all edge-cases via a robust test suite (`tests/test_hiring_risk_analyzer.py`), confirming that score and match states remain entirely immutable during this phase.

## Pending Work / Side Effects Found
- The full test suite (`pytest tests/`) reported 72 failures (out of 624 tests) previously regarding schema updates. These are still pending structural fix actions.
- *Side Effect Found* -> Legacy Tests expecting old keyword structures -> *Required Adjustment*: Update mocks in `test_classification_normalization.py`, `test_department_domain_repository.py`, and other taxonomy tests.

## Important Decisions
- Kept the `department_domain_repository` loading logic intact to respect the existing data-driven workflow, modifying only the seed initialization schema.
- Added `QA Team` to the `conftest.py` repository mock to allow `test_domain_matching.py` to properly test case-insensitive matching for `qa`.
- To guarantee we don't break fallback taxonomy matching logic but maintain proper capitalization intent, only words `len <= 3` and strictly `.isalpha()` are routed to case-sensitive acronym generation.
- Original casing is injected natively into `CandidateResumeDTO` during initialization, replacing forced lowercasing. The regular keyword matching ignores the original casing anyway via `re.IGNORECASE`, minimizing any blast radius across legacy domain matchings.
- The `HiringRiskAnalyzer` relies strictly on deterministic `match_result` failures; Gemma acts purely as an explanation generator, preserving full explainability and pipeline integrity.

## Files Changed
- `backend/app/repositories/department_domain.py`
- `backend/app/services/job_taxonomy.py`
- `backend/app/services/candidate_domain_service.py`
- `backend/tests/test_domain_matching.py`
- `backend/tests/conftest.py`
- `backend/app/schemas/match.py`
- `backend/app/core/rule_config_manager.py`
- `backend/app/services/system_rule_config_factory.py`
- `backend/app/services/hiring_risk_analyzer.py`
- `backend/app/services/scoring_engine.py`
- `backend/tests/test_hiring_risk_analyzer.py`
