import hashlib
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from redis import Redis
from rq import Queue

from app.core.cache import CacheInvalidator, doc_cache_manager
from app.core.config import settings
from app.core.logging import logger
from app.repositories.result import ResultRepository
from app.services.document_parser import DocumentParser, ExtractionResult
from app.services.embedding_service import EmbeddingService

import asyncio

_cv_locks: dict[str, asyncio.Lock] = {}
_MAX_CV_LOCKS = 1000


def _get_cv_lock(cv_key: str) -> asyncio.Lock:
    if cv_key not in _cv_locks:
        if len(_cv_locks) >= _MAX_CV_LOCKS:
            # Simple LRU/first-key eviction for inactive locks
            first_key = next(iter(_cv_locks))
            _cv_locks.pop(first_key, None)
        _cv_locks[cv_key] = asyncio.Lock()
    return _cv_locks[cv_key]


def get_stable_cv_key(
    filename: str,
    candidate_id: str | int | None = None,
    cv_id: str | int | None = None,
) -> str:
    raw_stem = Path(filename).stem
    safe_stem = re.sub(r"[^a-zA-Z0-9_-]", "_", raw_stem)
    if candidate_id is not None and cv_id is not None:
        return f"cand_{candidate_id}_cv_{cv_id}"
    if candidate_id is not None:
        return f"cand_{candidate_id}_{safe_stem}"
    if cv_id is not None:
        return f"cv_{cv_id}_{safe_stem}"
    return f"cv_{safe_stem}"


async def process_cv_file(
    filename: str,
    content: bytes,
    content_type: str | None = None,
    timeout_seconds: float | None = None,
    candidate_id: str | int | None = None,
    cv_id: str | int | None = None,
    force_reprocess: bool = False,
) -> dict[str, Any]:
    cv_key = get_stable_cv_key(filename, candidate_id, cv_id)
    cv_hash = hashlib.sha256(content).hexdigest()
    result_filename = f"{cv_key}.json"
    result_path = settings.RESULTS_DIR / result_filename

    lock = _get_cv_lock(cv_key)

    async with lock:
        existing_data = ResultRepository.read_result_by_filename(result_filename)

        if existing_data and not force_reprocess:
            existing_hash = existing_data.get("cv_hash")
            existing_parser_version = existing_data.get("parser_version")
            existing_schema_version = existing_data.get("schema_version")

            hash_matches = existing_hash == cv_hash
            parser_matches = (
                existing_parser_version == settings.EXTRACTION_PARSER_VERSION
            )
            schema_matches = (
                existing_schema_version == settings.EXTRACTION_SCHEMA_VERSION
            )

            if hash_matches and parser_matches and schema_matches:
                logger.info(
                    f"[CACHE_HIT] Reusing existing JSON for '{cv_key}' ({result_filename})."
                )
                existing_data["status"] = "CACHE_HIT"
                existing_data["result_file_path"] = str(result_path)
                return existing_data

            if not hash_matches:
                logger.info(
                    f"[CV_CHANGED] CV source content changed for '{cv_key}'. Reprocessing..."
                )
                if existing_hash:
                    CacheInvalidator.invalidate_cv(existing_hash)
            else:
                logger.info(
                    f"[SCHEMA_CHANGED] Parser or schema version changed for '{cv_key}'. Reprocessing..."
                )
        elif existing_data and force_reprocess:
            logger.info(f"[REPROCESSED] Force reprocessing requested for '{cv_key}'.")
        else:
            logger.info(f"[NEW_CV] Initial processing for '{cv_key}'.")

        # Try document cache first (keyed by content hash)
        cached_doc = doc_cache_manager.get(cv_hash)
        if cached_doc is not None:
            extraction = ExtractionResult.from_dict(cached_doc)
            logger.info(f"[DOC_CACHE_HIT] Reusing Docling output for hash '{cv_hash[:12]}...'.")
        else:
            extraction = await asyncio.to_thread(
                DocumentParser.parse_with_timeout,
                filename=filename,
                content=content,
                timeout_seconds=timeout_seconds,
            )
            doc_cache_manager.set(cv_hash, extraction.to_dict())
            logger.info(f"[DOC_CACHE_SET] Cached Docling output for hash '{cv_hash[:12]}...'.")

        # Generate and cache CV embedding (async to avoid blocking)
        cv_embedding = await asyncio.to_thread(
            EmbeddingService.generate_embedding,
            extraction.markdown[:8000],
            settings.EMBEDDING_MODEL,
        )
        if cv_embedding is not None:
            logger.info(f"[EMBED] CV embedding generated for hash '{cv_hash[:12]}...'.")

        # Run optimized LLM pipeline & matching
        from app.services.match_service import MatchService
        
        match_analysis = await MatchService.analyze_single_cv(
            extraction.markdown,
            document_hash=cv_hash,
            candidate_id=str(candidate_id) if candidate_id is not None else "",
        )

        now_iso = datetime.now(UTC).isoformat()
        created_at = (
            existing_data.get("created_at")
            if existing_data and existing_data.get("created_at")
            else now_iso
        )
        updated_at = now_iso

        status = "REPROCESSED" if existing_data else "NEW_CV"
        logger.info(f"[{status}] Extraction complete for '{cv_key}'.")

        result_data = {
            "id": cv_key,
            "scan_id": cv_key,
            "parsed_at": now_iso,
            "candidate_id": str(candidate_id) if candidate_id is not None else None,
            "cv_id": str(cv_id) if cv_id is not None else None,
            "filename": filename,
            "content_type": content_type,
            "cv_hash": cv_hash,
            "parser_version": settings.EXTRACTION_PARSER_VERSION,
            "schema_version": settings.EXTRACTION_SCHEMA_VERSION,
            "created_at": created_at,
            "updated_at": updated_at,
            "scanned_at": now_iso,
            "status": status,
            "characters": len(extraction.markdown),
            "page_count": extraction.page_count,
            "is_scanned": extraction.is_scanned,
            "ocr_applied": extraction.ocr_applied,
            "text": extraction.markdown,
            "markdown": extraction.markdown,
            "structured_doc": extraction.structured_doc,
            "dynamic_profile": None,
            "match_analysis": match_analysis.model_dump(),
        }

        saved_path = ResultRepository.atomic_save_result(result_filename, result_data)
        result_data["result_file_path"] = str(saved_path)
        return result_data


def process_cv_task_sync(file_path: str) -> dict[str, Any]:
    import asyncio
    import json
    path = Path(file_path)
    filename = path.name
    content = path.read_bytes()
    
    redis_url = settings.REDIS_URL or "redis://localhost:6379/0"
    conn = Redis.from_url(redis_url)
    
    try:
        # Run the existing async processor inside a synchronous event loop for RQ
        result = asyncio.run(process_cv_file(filename=filename, content=content))
        
        payload = {
            "filename": filename,
            "status": result.get("status", "OK"),
            "best_match": result.get("match_analysis", {}).get("best_match", {}),
            "llm_skipped": result.get("match_analysis", {}).get("llm_skipped", False),
            "result_file_path": result.get("result_file_path")
        }
        conn.publish("cv_processing_progress", json.dumps(payload))
        return result
    except Exception as e:
        payload = {
            "filename": filename,
            "status": "FAILED",
            "error": str(e)
        }
        conn.publish("cv_processing_progress", json.dumps(payload))
        raise


async def scan_uploads_directory(
    uploads_dir: str | Path = settings.UPLOADS_DIR,
    batch_size: int | None = None,
    max_workers: int | None = None,
    throttle_delay: float | None = None,
) -> list[dict[str, Any]]:
    path = Path(uploads_dir)
    results = []

    if not path.exists():
        logger.warning(f"Directory '{uploads_dir}' does not exist.")
        return results

    supported = {f".{ext}" for ext in settings.ALLOWED_EXTENSIONS}
    files = [f for f in path.iterdir() if f.is_file() and f.suffix.lower() in supported]

    if not files:
        logger.info(f"No supported CV files found in '{uploads_dir}'.")
        return results

    logger.info(f"Found {len(files)} CV file(s) in '{uploads_dir}'. Enqueueing to RQ...")

    redis_url = settings.REDIS_URL or "redis://localhost:6379/0"
    conn = Redis.from_url(redis_url)
    q = Queue(connection=conn)

    import redis.asyncio as aioredis
    import json
    
    async_redis = aioredis.from_url(redis_url, decode_responses=True)
    pubsub = async_redis.pubsub()
    await pubsub.subscribe("cv_processing_progress")

    jobs = []
    for file_obj in files:
        job = q.enqueue(
            process_cv_task_sync, 
            str(file_obj.absolute()), 
            job_timeout=settings.EXTRACTION_TIMEOUT_SECONDS,
            result_ttl=600
        )
        jobs.append((file_obj, job))

    print(f"📦 Enqueued {len(jobs)} file(s). Waiting for RQ workers to process...")
    
    try:
        processed_count = 0
        completed_ids = set()
        
        while processed_count < len(jobs):
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if message:
                payload = json.loads(message["data"])
                filename = payload.get("filename")
                
                # Check if we already processed this (to prevent double counting if fallback also caught it)
                if filename not in completed_ids:
                    completed_ids.add(filename)
                    processed_count += 1
                    status = payload.get("status", "OK")
                    best = payload.get("best_match", {})
                    llm_skipped = payload.get("llm_skipped", False)
                    fast_track_msg = " [⚡️Fast Track] " if llm_skipped else " "
                    
                    if status != "FAILED":
                        results.append(payload)
                        score = best.get("score", 0)
                        job_title = best.get("job_title", "Unknown")
                        classification = best.get("classification", "UNKNOWN")
                        print(
                            f"   [{processed_count}/{len(files)}] ✅ [{status}]: {filename} | "
                            f"Top Role: {job_title} ({score}% [{classification}]) |{fast_track_msg}"
                            f"Saved: {payload.get('result_file_path')}"
                        )
                    else:
                        print(f"   [{processed_count}/{len(files)}] ❌ Error: {filename} failed. {payload.get('error')}")

            # Fallback for hard worker crashes (segfault/OOM) where PubSub message is never sent
            for file_obj, job in jobs:
                if file_obj.name not in completed_ids:
                    try:
                        job.refresh()
                        if job.is_failed:
                            completed_ids.add(file_obj.name)
                            processed_count += 1
                            error_msg = job.exc_info or "Worker crashed unexpectedly (e.g. Segfault/OOM)"
                            print(f"   [{processed_count}/{len(files)}] ❌ Error: {file_obj.name} failed silently in RQ. {error_msg}")
                    except Exception:
                        pass
                        
            await asyncio.sleep(0.1)
    finally:
        await pubsub.unsubscribe("cv_processing_progress")
        await pubsub.close()
        await async_redis.aclose()

    print()
    return results

