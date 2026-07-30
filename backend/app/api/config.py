from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.logging import logger
from app.repositories.config import ConfigRepository
from app.schemas.config import MatchEngineConfigResponse, MatchEngineConfigUpdate

router = APIRouter(prefix="/config", tags=["Configuration"])


@router.get("/match", response_model=MatchEngineConfigResponse)
async def get_match_config(db: Session = Depends(get_db)):
    """Retrieve the current matching engine configuration weights and thresholds."""
    try:
        return MatchEngineConfigResponse(
            MATCH_HIGH_THRESHOLD=float(
                ConfigRepository.get_setting(
                    "MATCH_HIGH_THRESHOLD", settings.MATCH_HIGH_THRESHOLD, db
                )
            ),
            MATCH_MEDIUM_THRESHOLD=float(
                ConfigRepository.get_setting(
                    "MATCH_MEDIUM_THRESHOLD", settings.MATCH_MEDIUM_THRESHOLD, db
                )
            ),
            MANDATORY_FAILURE_PENALTY_PER_ITEM=float(
                ConfigRepository.get_setting(
                    "MANDATORY_FAILURE_PENALTY_PER_ITEM",
                    settings.MANDATORY_FAILURE_PENALTY_PER_ITEM,
                    db,
                )
            ),
            MAX_SCORE_ON_MANDATORY_FAILURE=float(
                ConfigRepository.get_setting(
                    "MAX_SCORE_ON_MANDATORY_FAILURE",
                    settings.MAX_SCORE_ON_MANDATORY_FAILURE,
                    db,
                )
            ),
            LLM_SEMANTIC_WEIGHT=float(
                ConfigRepository.get_setting(
                    "LLM_SEMANTIC_WEIGHT", settings.LLM_SEMANTIC_WEIGHT, db
                )
            ),
            MAX_LLM_BOOST=float(
                ConfigRepository.get_setting("MAX_LLM_BOOST", settings.MAX_LLM_BOOST, db)
            ),
            LLM_SKIP_MARGIN_THRESHOLD=float(
                ConfigRepository.get_setting("LLM_SKIP_MARGIN_THRESHOLD", settings.LLM_SKIP_MARGIN_THRESHOLD, db)
            ),
            LLM_SKIP_COVERAGE_THRESHOLD=float(
                ConfigRepository.get_setting("LLM_SKIP_COVERAGE_THRESHOLD", settings.LLM_SKIP_COVERAGE_THRESHOLD, db)
            ),
            MATCH_COMPONENT_WEIGHTS=ConfigRepository.get_setting(
                "MATCH_COMPONENT_WEIGHTS",
                {
                    "role": 0.15,
                    "skills": 0.25,
                    "experience": 0.15,
                    "education": 0.10,
                    "domain": 0.15,
                    "technology": 0.10,
                    "certification": 0.05,
                    "responsibilities": 0.05,
                },
                db,
            ),
        )
    except Exception as exc:
        logger.exception(f"Failed to retrieve match config: {exc}")
        raise HTTPException(status_code=500, detail="Failed to retrieve configuration.") from exc


@router.put("/match", response_model=MatchEngineConfigResponse)
async def update_match_config(
    payload: MatchEngineConfigUpdate, db: Session = Depends(get_db)
):
    """Update the matching engine configuration. Values are merged with existing settings."""
    try:
        update_data = payload.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            ConfigRepository.update_setting(key, value, db)

        return await get_match_config(db)
    except Exception as exc:
        logger.exception(f"Failed to update match config: {exc}")
        raise HTTPException(status_code=500, detail="Failed to update configuration.") from exc
