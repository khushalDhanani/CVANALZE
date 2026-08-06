from __future__ import annotations
from fastapi import APIRouter, HTTPException, status
from pydantic import ValidationError

from app.schemas.work_experience_extraction import (
    WorkExperienceExtractionRequest,
    WorkExperienceExtractionResponse,
)
from app.services.work_experience_extraction_service import WorkExperienceExtractionEngine
from app.services.ollama_transport import OllamaError

router = APIRouter(
    prefix="/cv",
    tags=["CV Experience"],
)

@router.post(
    "/extract-experience",
    response_model=WorkExperienceExtractionResponse,
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Successful extraction (complete or partial)"},
        422: {"description": "Invalid input format"},
        503: {"description": "Ollama service unavailable"},
        504: {"description": "Ollama service timeout"},
        500: {"description": "Internal server error"},
    },
)
async def extract_experience(request: WorkExperienceExtractionRequest):
    try:
        response = await WorkExperienceExtractionEngine.process(request)
        return response
    except OllamaError as exc:
        if "timeout" in str(exc).lower():
            raise HTTPException(status_code=504, detail="LLM generation timed out")
        raise HTTPException(status_code=503, detail="LLM service unavailable")
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors())
    except Exception as exc:
        raise HTTPException(status_code=500, detail="An unexpected error occurred during extraction")
