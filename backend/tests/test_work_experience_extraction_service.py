import pytest
from unittest.mock import patch, AsyncMock
from app.services.work_experience_extraction_service import WorkExperienceExtractionEngine
from app.schemas.work_experience_extraction import WorkExperienceExtractionRequest, WorkExperienceConfig
from app.schemas.work_experience_llm import LLMWorkExperienceExtraction, LLMWorkExperienceRecord
from app.prompts.work_experience_extraction_v1 import WORK_EXPERIENCE_PROMPT_VERSION

@pytest.mark.asyncio
@patch("app.services.work_experience_extraction_service.OllamaLLMService.extract_work_experience", new_callable=AsyncMock)
async def test_extraction_engine_orchestration(mock_extract):
    mock_llm_result = LLMWorkExperienceExtraction(
        detected_date_pattern="DD/MM/YYYY",
        overall_confidence=0.9,
        employment_records=[
            LLMWorkExperienceRecord(
                original_text="Mock Text",
                company_name_normalized="Mock Corp",
                job_title_normalized="Mock Eng",
                start_date_original="2020-01-01",
                end_date_original="Present",
                is_current=True,
                employment_type="full_time",
                confidence=0.9
            )
        ]
    )
    mock_extract.return_value = mock_llm_result

    request = WorkExperienceExtractionRequest(
        candidate_id="C123",
        ocr_text="Mock Text",
        reference_date="2026-08-05",
        config=WorkExperienceConfig()
    )

    response = await WorkExperienceExtractionEngine.process(request)

    assert response.candidate_id == "C123"
    assert response.extraction_status == "success"
    assert len(response.employment_records) == 1
    assert response.employment_records[0].is_current is True
    assert response.employment_records[0].calculation_end_date == "2026-08-05"
    assert response.metadata.prompt_version == WORK_EXPERIENCE_PROMPT_VERSION
