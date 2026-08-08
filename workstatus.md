# Work Status

## Last Completed Task
**CV Extraction Content Protection & Integrity Audit**

### Key Protections & Integrity Enforcements

1. **Extraction Text Integrity**:
   - `raw_extracted_text` and `clean_text` (stored in JSON DB and cache) remain 100% complete and un-truncated regardless of CV length (>15,000+ chars).
   - `LLM_CV_MAX_CHARS` (4,000) & `LLM_PROFILE_MAX_CHARS` (7,500) apply ONLY to LLM prompt construction, never to parsing, storage, skills, education, dates, or experience calculation.

2. **Upstream Truncation Fixes**:
   - Replaced hardcoded `cv_text[:4000]` in `ExperienceCalculator._extract_explicit_experience` with `settings.EXPERIENCE_KEYWORD_SEARCH_CHARS` (20,000), guaranteeing explicit experience declarations past char 4000 in long multi-page CVs are detected.
   - Replaced hardcoded `cv_text[:7500]` in `build_profile_extraction_prompt` with `settings.LLM_PROFILE_MAX_CHARS`.

3. **Content Loss Detection & Telemetry**:
   - Added content-loss check in `DocumentConversionService`: flags a warning if `final_chars` < 50% of `native_char_count` (detects dropped content in hybrid/scanned PDFs).
   - Added `[EXTRACTION_TELEMETRY]` logging: `native_chars`, `docling_chars`, `ocr_chars`, `final_chars`, `content_loss_detected`.
   - Added `[LLM_INPUT]` logging: `full_cv_chars`, `llm_chars`, `vacancies_sent_to_llm`, `prompt_chars`, `estimated_tokens`.

4. **Deterministic Ranking for LLM Top-N**:
   - `MatchService` selects Top-N vacancies for LLM enrichment based on full `pre_llm_matches` deterministic scores (already sorted desc), ensuring the best rule-based matches are sent to Qwen.

5. **Reverted Context Window**:
   - Reverted `OLLAMA_GENERATION_NUM_CTX` back to 4096 (prompt fits comfortably within ~2,250 tokens).

### Files Changed

| File | Changes |
|------|---------|
| `app/core/config.py` | Reverted `OLLAMA_GENERATION_NUM_CTX=4096`. Added `LLM_PROFILE_MAX_CHARS=7500`, `EMBEDDING_CV_MAX_CHARS=8000`, `EXPERIENCE_KEYWORD_SEARCH_CHARS=20000`. |
| `app/services/experience_calculator.py` | Used `settings.EXPERIENCE_KEYWORD_SEARCH_CHARS` (20,000) for explicit experience statement regex search instead of 4,000. |
| `app/prompts/profile_extraction.py` | Used `settings.LLM_PROFILE_MAX_CHARS` for prompt formatting. |
| `app/services/vacancy_prefilter.py` | Used `settings.EMBEDDING_CV_MAX_CHARS` (8,000) for vector embedding generation. |
| `app/services/document_conversion.py` | Added content-loss detection logic & `[EXTRACTION_TELEMETRY]` logging (`native_chars`, `docling_chars`, `ocr_chars`, `final_chars`, `content_loss_detected`). |
| `app/services/match_service.py` | Selected `LLM_TOP_N=12` based on `pre_llm_matches` deterministic scores; added `full_cv_chars` vs `llm_chars` to `[LLM_INPUT]` log. |
| `tests/test_cv_extraction_integrity.py` | Added 25 unit tests verifying truncation is LLM-only, long CVs (>15k chars) are preserved, experience search works past 4k chars, and content-loss triggers correctly. |

### Verification Status
- **Automated Tests**: 25/25 passed in `tests/test_cv_extraction_integrity.py`.
