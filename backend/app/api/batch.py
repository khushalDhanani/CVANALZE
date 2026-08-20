from __future__ import annotations

import asyncio

import redis.asyncio as aioredis
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, status

from app.core.config import settings
from app.core.logging import logger
from app.services.batch_processing_service import BatchProcessingService
from app.services.processing_queue import ProcessingQueueUnavailableError

router = APIRouter(prefix="/batch", tags=["Batch Processing"])


@router.post("/match-candidates", status_code=status.HTTP_202_ACCEPTED)
async def match_candidates_against_vacancies(limit: int | None = None):
    """Create an asynchronous RQ batch coordinator without parsing CVs in the request."""
    limit = limit or settings.DEFAULT_BATCH_CANDIDATE_LIMIT
    if limit <= 0 or limit > settings.MAX_BATCH_LIMIT:
        raise HTTPException(
            status_code=400,
            detail=f"Limit must be between 1 and {settings.MAX_BATCH_LIMIT}.",
        )
    try:
        return BatchProcessingService.submit(limit).to_response()
    except ProcessingQueueUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/jobs/{batch_job_id}")
async def get_batch_job(batch_job_id: str):
    record = BatchProcessingService.get_status(batch_job_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Batch job '{batch_job_id}' was not found.")
    return record.to_response()


@router.websocket("/ws/progress")
async def websocket_progress_endpoint(websocket: WebSocket):
    await websocket.accept()
    redis_url = settings.REDIS_URL

    redis_client = aioredis.from_url(redis_url, decode_responses=True)
    pubsub = redis_client.pubsub()
    try:
        await pubsub.subscribe("cv_processing_progress")

        while True:
            # Poll for new messages (we use get_message with timeout instead of listen() to check for disconnects)
            message = await pubsub.get_message(
                ignore_subscribe_messages=True,
                timeout=settings.API_STREAM_POLL_TIMEOUT_SECONDS,
            )
            if message:
                await websocket.send_text(message["data"])

            # This small sleep allows checking if client disconnected
            await asyncio.sleep(settings.API_STREAM_IDLE_SLEEP_SECONDS)
    except WebSocketDisconnect:
        logger.info("Client disconnected from /api/batch/ws/progress")
    except Exception as exc:
        logger.exception(f"WebSocket progress stream failed: {type(exc).__name__}")
    finally:
        await pubsub.unsubscribe("cv_processing_progress")
        await pubsub.close()
        await redis_client.aclose()
