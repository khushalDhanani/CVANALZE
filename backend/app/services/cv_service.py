import asyncio
import hashlib
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from redis import Redis
from rq import Queue

from app.core.cache import CacheInvalidator
from app.core.config import settings
from app.core.logging import logger
from app.repositories.result import ResultRepository
from app.services.document_parser import (
    MarkdownGenerator,
    MarkdownResult,
    QualityMetricsCalculator,
    ResumeJsonExtractor,
)
from app.services.embedding_service import EmbeddingService

from contextlib import asynccontextmanager

_cv_locks: dict[str, asyncio.Lock] = {}
_MAX_CV_LOCKS = 1000


def _get_local_cv_lock(cv_key: str) -> asyncio.Lock:
    if cv_key not in _cv_locks:
        if len(_cv_locks) >= _MAX_CV_LOCKS:
            first_key = next(iter(_cv_locks))
            _cv_locks.pop(first_key, None)
        _cv_locks[cv_key] = asyncio.Lock()
    return _cv_locks[cv_key]


@asynccontextmanager
async def get_cv_lock(cv_key: str):
    from app.core.cache import _REDIS_CLIENT
    redis_lock = None
    if _REDIS_CLIENT:
        try:
            lock_key = f"lock:cv:{cv_key}"
            redis_lock = _REDIS_CLIENT.lock(lock_key, timeout=120, blocking_timeout=10)
            acquired = redis_lock.acquire(blocking=True)
            if not acquired:
                redis_lock = None
        except Exception as err:
            logger.warning(f"Redis distributed lock acquire failed ({err}), using local lock fallback.")
            redis_lock = None

    local_lock = _get_local_cv_lock(cv_key)
    async with local_lock:
        try:
            yield
        finally:
            if redis_lock:
                try:
                    redis_lock.release()
                except Exception as rel_err:
                    logger.warning(f"Redis lock release warning for '{cv_key}': {rel_err}")


def get_stable_cv_key(
    filename: str,
    candidate_id: str | int | None = None,
    cv_id: str | int | None = None,
) -> str:
    """
    Returns a single deterministic, canonical cv_key for a given CV filename.
    Standardizes on cv_{safe_stem} across all upload routes (/cv/upload, /match/upload)
    and processing lifecycle stages (interim status, final save, status polling).
    """
    raw_stem = Path(filename).stem
    safe_stem = re.sub(r"[^a-zA-Z0-9_-]", "_", raw_stem)
    if safe_stem.lower().startswith("cv_"):
        safe_stem = safe_stem[3:]
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

    async with get_cv_lock(cv_key):
        current_stage = "initialization"
        t_pipeline_start = asyncio.get_event_loop().time()
        stage_durations_ms: dict[str, float] = {}

        try:
            existing_data = await asyncio.to_thread(ResultRepository.read_result_by_filename, result_filename)

            if existing_data and not force_reprocess and existing_data.get("status") != "FAILED":
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
                    existing_data["status"] = "COMPLETED"
                    existing_data["original_status"] = "CACHE_HIT"
                    existing_data["progress"] = 100
                    existing_data["stage"] = "complete"
                    existing_data["is_complete"] = True
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

            current_stage = "validation"
            t_stage_start = asyncio.get_event_loop().time()
            
            # Helper to save interim status
            async def _save_interim_status(progress: int, stage: str):
                interim_data = {
                    "id": cv_key,
                    "scan_id": cv_key,
                    "status": "processing",
                    "progress": progress,
                    "stage": stage,
                    "filename": filename,
                }
                try:
                    await asyncio.to_thread(ResultRepository.atomic_save_result, result_filename, interim_data)
                except Exception as e:
                    logger.warning(f"Failed to save interim status for '{cv_key}': {e}")

            await _save_interim_status(15, current_stage)
            stage_durations_ms["validation_ms"] = round((asyncio.get_event_loop().time() - t_stage_start) * 1000.0, 2)

            current_stage = "parsing"
            await _save_interim_status(30, current_stage)

            # Markdown Generation & Persistence stage
            t_doc_start = asyncio.get_event_loop().time()
            md_filename = f"{cv_key}.md"
            md_path = settings.RESULTS_DIR / md_filename
            
            if md_path.exists() and not force_reprocess:
                logger.info(f"[MD_CACHE_HIT] Reading existing markdown from '{md_filename}'.")
                markdown_text = await asyncio.to_thread(md_path.read_text, encoding="utf-8")
                
                stage_metrics = existing_data.get("stage_metrics", {}) if existing_data else {}
                page_count = existing_data.get("page_count", 1) if existing_data else 1
                is_scanned = existing_data.get("is_scanned", False) if existing_data else False
                ocr_applied = existing_data.get("ocr_applied", False) if existing_data else False
                pdf_type = existing_data.get("pdf_type", "NON_PDF") if existing_data else "NON_PDF"
                parser_used = existing_data.get("parser_used", "cached") if existing_data else "cached"
                ocr_decision = existing_data.get("ocr_decision", "cached") if existing_data else "cached"
                
                extraction = MarkdownResult(
                    markdown=markdown_text,
                    page_count=page_count,
                    is_scanned=is_scanned,
                    ocr_applied=ocr_applied,
                    pdf_type=pdf_type,
                    parser_used=parser_used,
                    ocr_decision=ocr_decision,
                    stage_metrics=stage_metrics,
                )
            else:
                extraction = await asyncio.to_thread(
                    MarkdownGenerator.generate_with_timeout,
                    filename=filename,
                    content=content,
                    timeout_seconds=timeout_seconds,
                )
                markdown_text = extraction.markdown
                settings.RESULTS_DIR.mkdir(parents=True, exist_ok=True)
                await asyncio.to_thread(md_path.write_text, markdown_text, encoding="utf-8")
                logger.info(f"[MD_SAVED] Saved generated markdown to '{md_filename}'.")
                
            docling_duration_ms = round((asyncio.get_event_loop().time() - t_doc_start) * 1000.0, 2)
            stage_durations_ms["docling_parsing_ms"] = docling_duration_ms
            
            current_stage = "extraction"
            await _save_interim_status(45, current_stage)

            t_ext_start = asyncio.get_event_loop().time()
            quality_metrics = QualityMetricsCalculator.compute(
                text=markdown_text,
                page_count=extraction.page_count,
                pdf_type=extraction.pdf_type,
                parser_used=extraction.parser_used,
                ocr_applied=extraction.ocr_applied,
            )
            resume_json = ResumeJsonExtractor.extract(
                markdown_text, quality_metrics, filename=filename
            )
            stage_durations_ms["resume_extraction_ms"] = round((asyncio.get_event_loop().time() - t_ext_start) * 1000.0, 2)

            from app.services.embedding_service import save_candidate_embedding
            from app.services.match_service import MatchService

            def _generate_and_store_embedding():
                emb = EmbeddingService.generate_embedding(
                    extraction.markdown,
                    model_version=None,
                    identifier=cv_key,
                )
                if emb:
                    save_candidate_embedding(cv_key, emb, cv_hash)
                return emb

            current_stage = "ai_analysis"
            await _save_interim_status(60, current_stage)

            t_emb_start = asyncio.get_event_loop().time()
            cv_embedding = await asyncio.to_thread(_generate_and_store_embedding)
            stage_durations_ms["embedding_ms"] = round((asyncio.get_event_loop().time() - t_emb_start) * 1000.0, 2)

            current_stage = "matching"
            await _save_interim_status(75, current_stage)

            t_match_start = asyncio.get_event_loop().time()
            match_analysis = await MatchService.analyze_single_cv(
                extraction.markdown,
                document_hash=cv_hash,
                candidate_id=str(candidate_id) if candidate_id is not None else "",
                docling_extraction_ms=docling_duration_ms,
                cv_embedding=cv_embedding,
            )
            stage_durations_ms["matching_ms"] = round((asyncio.get_event_loop().time() - t_match_start) * 1000.0, 2)

            contact_info = (resume_json or {}).get("contact_info") or {}
            extracted_name = contact_info.get("name") or contact_info.get("full_name") or "Unknown Candidate"
            email = contact_info.get("email")
            phone = contact_info.get("phone")
            name_confidence = contact_info.get("name_confidence")
            name_extraction_source = contact_info.get("extraction_source")

            location_val = contact_info.get("location")
            work_exp = (resume_json or {}).get("work_experience") or []
            top_exp = work_exp[0] if work_exp else {}
            job_title_val = contact_info.get("job_title") or top_exp.get("job_title")
            company_val = contact_info.get("company_name") or contact_info.get("company") or top_exp.get("company")

            raw_fc = contact_info.get("field_confidence") or {}
            raw_fct = contact_info.get("field_confidence_tiers") or {}

            from app.core.rule_config_manager import RuleConfigManager
            name_tier = contact_info.get("name_confidence_level") or contact_info.get("name_confidence_tier") or raw_fct.get("name") or RuleConfigManager.get_confidence_tier("name", name_confidence)
            loc_tier = contact_info.get("location_confidence_tier") or raw_fct.get("location") or RuleConfigManager.get_confidence_tier("location", raw_fc.get("location"))
            title_tier = contact_info.get("job_title_confidence_tier") or raw_fct.get("job_title") or RuleConfigManager.get_confidence_tier("job_title", raw_fc.get("job_title"))
            comp_tier = contact_info.get("company_name_confidence_tier") or raw_fct.get("company_name") or RuleConfigManager.get_confidence_tier("company_name", raw_fc.get("company_name"))

            field_confidence_tiers = {
                "name": name_tier if extracted_name and extracted_name.lower() != "unknown candidate" else "LOW",
                "location": loc_tier if location_val else "LOW",
                "job_title": title_tier if job_title_val else "LOW",
                "company_name": comp_tier if company_val else "LOW",
            }

            match_analysis.full_name = extracted_name
            match_analysis.candidate_name = extracted_name

            current_stage = "complete"
            await _save_interim_status(90, current_stage)

            now_iso = datetime.now(UTC).isoformat()
            created_at = (
                existing_data.get("created_at")
                if existing_data and existing_data.get("created_at")
                else now_iso
            )
            updated_at = now_iso

            status = "REPROCESSED" if existing_data else "NEW_CV"
            stage_durations_ms["total_ms"] = round((asyncio.get_event_loop().time() - t_pipeline_start) * 1000.0, 2)
            logger.info(f"[{status}] Extraction complete for '{cv_key}' in {stage_durations_ms['total_ms']}ms. Candidate: '{extracted_name}'")

            from app.services.similar_candidate_service import SimilarCandidateService

            similar_candidates = []
            if cv_embedding:
                try:
                    similar_candidates = await asyncio.to_thread(
                        SimilarCandidateService.detect_similar_candidates,
                        cv_key=cv_key,
                        cv_embedding=cv_embedding,
                    )
                except Exception as sim_exc:
                    logger.warning(f"Similar candidate detection failed for '{cv_key}': {sim_exc}")

            result_data = {
                "id": cv_key,
                "scan_id": cv_key,
                "parsed_at": now_iso,
                "candidate_id": str(candidate_id) if candidate_id is not None else None,
                "cv_id": str(cv_id) if cv_id is not None else None,
                "filename": filename,
                "content_type": content_type,
                "cv_hash": cv_hash,
                "full_name": extracted_name if extracted_name != "Unknown Candidate" else None,
                "candidate_name": extracted_name if extracted_name != "Unknown Candidate" else None,
                "email": email,
                "phone": phone,
                "location": location_val,
                "job_title": job_title_val,
                "company_name": company_val,
                "name_confidence": name_confidence,
                "name_confidence_tier": field_confidence_tiers["name"],
                "location_confidence_tier": field_confidence_tiers["location"],
                "job_title_confidence_tier": field_confidence_tiers["job_title"],
                "company_name_confidence_tier": field_confidence_tiers["company_name"],
                "field_confidence": raw_fc,
                "field_confidence_tiers": field_confidence_tiers,
                "name_extraction_source": name_extraction_source,
                "parser_version": settings.EXTRACTION_PARSER_VERSION,
                "schema_version": settings.EXTRACTION_SCHEMA_VERSION,
                "created_at": created_at,
                "updated_at": updated_at,
                "scanned_at": now_iso,
                "status": "COMPLETED",
                "original_status": status,
                "progress": 100,
                "stage": "complete",
                "is_complete": True,
                "message": "100% - CV parsing & job matching complete!",
                "similar_candidates": similar_candidates,
                "pdf_type": getattr(extraction, "pdf_type", "NON_PDF"),
                "parser_used": getattr(extraction, "parser_used", "docling_fast"),
                "ocr_decision": getattr(extraction, "ocr_decision", "SKIPPED_TEXT_PRESENT"),
                "stage_metrics": getattr(extraction, "stage_metrics", {}),
                "docling_duration_ms": docling_duration_ms,
                "stage_durations_ms": stage_durations_ms,
                "quality_metrics": quality_metrics,
                "resume_json": resume_json,
                "characters": len(extraction.markdown),
                "page_count": extraction.page_count,
                "is_scanned": extraction.is_scanned,
                "ocr_applied": extraction.ocr_applied,
                "text": extraction.markdown,
                "markdown": extraction.markdown,
                "structured_doc": None,
                "dynamic_profile": None,
                "match_analysis": match_analysis.model_dump(),
            }

            saved_path = await asyncio.to_thread(ResultRepository.atomic_save_result, result_filename, result_data)
            result_data["result_file_path"] = str(saved_path)

            # Signal Ollama to unload model and become idle immediately after matching completes
            try:
                from app.services.llm_service import OllamaLLMService
                await asyncio.to_thread(OllamaLLMService.unload_model)
            except Exception as unload_err:
                logger.warning(f"Ollama unload signal failed for '{cv_key}': {unload_err}")

            return result_data

        except Exception as exc:
            import traceback
            error_details = traceback.format_exc()
            logger.exception(f"CV processing failed for '{cv_key}' at stage '{current_stage}': {exc}")
            now_iso = datetime.now(UTC).isoformat()
            err_msg = str(exc)
            
            stage_to_step = {
                "parsing": "Docling Parsing",
                "extraction": "Resume Extraction",
                "ai_analysis": "AI Analysis",
                "matching": "Job Matching",
                "complete": "Finalizing"
            }
            failed_step = stage_to_step.get(current_stage, current_stage)

            failure_data = {
                "id": cv_key,
                "scan_id": cv_key,
                "filename": filename,
                "content_type": content_type,
                "candidate_id": str(candidate_id) if candidate_id is not None else None,
                "cv_id": str(cv_id) if cv_id is not None else None,
                "parsed_at": now_iso,
                "created_at": now_iso,
                "updated_at": now_iso,
                "scanned_at": now_iso,
                "status": "FAILED",
                "progress": 100,
                "is_complete": False,
                "error": err_msg,
                "message": f"CV processing failed at {failed_step}: {err_msg}",
                "stage": current_stage,
                "failed_step": failed_step,
                "error_details": error_details,
                "characters": 0,
                "page_count": 0,
                "is_scanned": False,
                "ocr_applied": False,
                "text": "",
                "markdown": "",
                "structured_doc": {},
                "dynamic_profile": None,
                "match_analysis": None,
            }
            try:
                await asyncio.to_thread(ResultRepository.atomic_save_result, result_filename, failure_data)
            except Exception as save_exc:
                logger.error(f"Failed to persist failure status result for '{cv_key}': {save_exc}")
            raise


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
            "best_match": result.get("match_analysis", {}).get("best_match", {}) if result.get("match_analysis") else {},
            "llm_skipped": result.get("match_analysis", {}).get("llm_skipped", False) if result.get("match_analysis") else False,
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
        try:
            conn.publish("cv_processing_progress", json.dumps(payload))
        except Exception:
            pass
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

    import json

    import redis.asyncio as aioredis
    
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
        try:
            await pubsub.unsubscribe("cv_processing_progress")
        except Exception:
            pass
        try:
            if hasattr(pubsub, "close"):
                res = pubsub.close()
                if asyncio.iscoroutine(res):
                    await res
        except Exception:
            pass
        try:
            if hasattr(async_redis, "aclose"):
                await async_redis.aclose()
        except Exception:
            pass


    print()
    return results

