from __future__ import annotations

import asyncio
import hashlib
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.analysis_context import async_analysis_run_context, new_analysis_run_id
from app.core.cache import CacheIndex, CacheInvalidator, CacheKey, doc_cache_manager
from app.core.config import settings
from app.core.cv_identity import CVIdentityCollisionError, normalize_source_candidate_id, resolve_cv_identity
from app.core.logging import logger
from app.core.rule_config_manager import RuleConfigManager
from app.repositories.processing_job import ProcessingJobRepository
from app.repositories.result import ResultRepository
from app.schemas.contracts import JobState
from app.schemas.normalized_resume import NormalizedResume
from app.services.document_parser import (
    MarkdownGenerator,
    MarkdownResult,
    QualityMetricsCalculator,
    ResumeJsonExtractor,
)
from app.services.embedding_service import EmbeddingService
from app.services.hiring_risk_analyzer import HiringRiskAnalyzer
from app.services.prompt_service import PromptService
from app.services.upload_service import UploadService

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
            redis_lock = _REDIS_CLIENT.lock(
                lock_key, 
                timeout=settings.REDIS_LOCK_TIMEOUT_SECONDS, 
                blocking_timeout=settings.REDIS_LOCK_BLOCKING_TIMEOUT_SECONDS
            )
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
                    is_owned = True
                    if hasattr(redis_lock, "owned") and callable(redis_lock.owned):
                        is_owned = redis_lock.owned()
                    if is_owned:
                        redis_lock.release()
                except Exception as rel_err:
                    logger.debug(f"Redis lock release debug for '{cv_key}': {rel_err}")



def get_stable_cv_key(
    filename: str,
    candidate_id: str | int | None = None,
    cv_id: str | int | None = None,
) -> str:
    """Return the canonical ID-based key, falling back to the legacy filename key."""
    return resolve_cv_identity(filename, candidate_id, cv_id).canonical_key


async def process_cv_file(
    filename: str,
    content: bytes,
    content_type: str | None = None,
    timeout_seconds: float | None = None,
    candidate_id: str | int | None = None,
    source_candidate_id: str | int | None = None,
    cv_id: str | int | None = None,
    force_reprocess: bool = False,
    storage_filename: str | None = None,
    original_filename: str | None = None,
    display_filename: str | None = None,
    analysis_run_id: str | None = None,
    job_id: str | None = None,
) -> dict[str, Any]:
    identity = resolve_cv_identity(filename, candidate_id, cv_id)
    cv_key = identity.canonical_key
    analysis_run_id = str(analysis_run_id or new_analysis_run_id())
    source_candidate_id = normalize_source_candidate_id(source_candidate_id if source_candidate_id is not None else identity.candidate_id)
    cv_hash = hashlib.sha256(content).hexdigest()
    result_filename = f"{cv_key}.json"
    identity_metadata = identity.to_metadata()
    legacy_cv_keys = [identity.legacy_key]
    run_now_ts = int(datetime.now(timezone.utc).timestamp() * 1000)
    result_generation_id = f"gen_{run_now_ts}_{cv_hash[:8]}"
    generation_sequence = ResultRepository.fetch_next_generation_sequence()
    current_rule_config = RuleConfigManager.get_config()
    current_rule_config_version = current_rule_config.version
    current_hiring_risk_policy_version = HiringRiskAnalyzer.get_policy_version(current_rule_config)
    current_hiring_risk_prompt_version = PromptService.get_active_prompt_version(HiringRiskAnalyzer.PROMPT_NAME) or "missing"
    current_hiring_risk_prompt_identity = PromptService.get_active_prompt_identity(HiringRiskAnalyzer.PROMPT_NAME) or "missing"
    current_optimized_prompt_version = settings.OPTIMIZED_PROMPT_VERSION
    current_llm_model_version = settings.OLLAMA_MODEL

    async with async_analysis_run_context(analysis_run_id, cv_key), get_cv_lock(cv_key):


        current_stage = "initialization"
        t_pipeline_start = asyncio.get_event_loop().time()
        stage_durations_ms: dict[str, float] = {}

        try:
            await asyncio.to_thread(
                ResultRepository.assert_identity_available,
                identity,
                cv_hash,
                allow_legacy_content_change=force_reprocess,
            )
            existing_data = await asyncio.to_thread(ResultRepository.read_result_by_filename, result_filename)

            if existing_data and not force_reprocess and existing_data.get("status") != "FAILED":
                existing_hash = existing_data.get("cv_hash")
                existing_parser_version = existing_data.get("parser_version")
                existing_schema_version = existing_data.get("schema_version")
                existing_rule_config_version = existing_data.get("rule_config_version")
                existing_hiring_risk_policy_version = existing_data.get("hiring_risk_policy_version")
                existing_hiring_risk_prompt_version = existing_data.get("hiring_risk_prompt_version")
                existing_hiring_risk_prompt_identity = existing_data.get("hiring_risk_prompt_identity")
                existing_optimized_prompt_version = existing_data.get("optimized_prompt_version")
                existing_llm_model_version = existing_data.get("llm_model_version")
                existing_matching_version = existing_data.get("matching_version")

                hash_matches = existing_hash == cv_hash
                parser_matches = existing_parser_version == settings.EXTRACTION_PARSER_VERSION
                schema_matches = existing_schema_version == settings.EXTRACTION_SCHEMA_VERSION
                rule_config_matches = existing_rule_config_version == current_rule_config_version
                hiring_policy_matches = existing_hiring_risk_policy_version == current_hiring_risk_policy_version
                hiring_prompt_matches = existing_hiring_risk_prompt_version == current_hiring_risk_prompt_version
                hiring_prompt_identity_matches = existing_hiring_risk_prompt_identity == current_hiring_risk_prompt_identity
                optimized_prompt_matches = existing_optimized_prompt_version == current_optimized_prompt_version
                llm_model_matches = existing_llm_model_version == current_llm_model_version
                matching_version_matches = existing_matching_version == settings.MATCHING_VERSION

                if all(
                    (
                        hash_matches,
                        parser_matches,
                        schema_matches,
                        rule_config_matches,
                        hiring_policy_matches,
                        hiring_prompt_matches,
                        hiring_prompt_identity_matches,
                        optimized_prompt_matches,
                        llm_model_matches,
                        matching_version_matches,
                    )
                ):
                    logger.info(f"[CACHE_HIT] Reusing existing JSON for '{cv_key}' ({result_filename}).")
                    existing_data["status"] = "COMPLETED"
                    existing_data["original_status"] = "CACHE_HIT"
                    existing_data["progress"] = 100
                    existing_data["stage"] = "complete"
                    existing_data["is_complete"] = True
                    existing_data["storage_filename"] = storage_filename or existing_data.get("storage_filename")
                    existing_data["original_filename"] = original_filename or existing_data.get("original_filename") or existing_data.get("filename")
                    existing_data["display_filename"] = display_filename or existing_data.get("display_filename") or existing_data.get("filename")
                    existing_data["identity"] = identity_metadata
                    existing_data["source_candidate_id"] = source_candidate_id
                    existing_data["legacy_cv_keys"] = legacy_cv_keys
                    existing_data["analysis_run_id"] = analysis_run_id
                    existing_data["analysis_version"] = analysis_run_id

                    # 1. Disk/Cache Persistence Parity
                    saved_path = await asyncio.to_thread(
                        ResultRepository.atomic_save_result,
                        result_filename,
                        existing_data,
                    )
                    existing_data["result_file_path"] = str(saved_path)

                    # 2. Vector DB Synchronization Parity
                    from app.services.embedding_service import (
                        get_candidate_embedding,
                        save_candidate_embedding,
                    )

                    cand_emb = await asyncio.to_thread(get_candidate_embedding, cv_key)
                    if cand_emb is None:
                        logger.info(f"[CACHE_HIT] Missing vector embedding for '{cv_key}'. Syncing to pgvector...")
                        markdown_text = str(existing_data.get("markdown") or existing_data.get("text") or "")
                        if markdown_text:
                            new_emb = await asyncio.to_thread(
                                EmbeddingService.generate_embedding,
                                markdown_text,
                                model_version=None,
                                identifier=cv_key,
                            )
                            if new_emb:
                                await asyncio.to_thread(save_candidate_embedding, cv_key, new_emb, cv_hash)
                                logger.info(f"[CACHE_HIT] Successfully synchronized embedding for '{cv_key}'.")

                    # 3. Raw-upload cleanup parity. Ollama lifecycle is controlled by keep-alive policy.
                    await asyncio.to_thread(
                        UploadService.cleanup_after_processing,
                        storage_filename,
                        succeeded=existing_data.get("persistence_status") == ResultRepository.PERSISTENCE_DURABLE,
                    )
                    return existing_data

                if not hash_matches:
                    logger.info(f"[CV_CHANGED] CV source content changed for '{cv_key}'. Reprocessing...")
                    if existing_hash:
                        CacheInvalidator.invalidate_cv(existing_hash)
                else:
                    logger.info(f"[SCHEMA_CHANGED] Parser or schema version changed for '{cv_key}'. Reprocessing...")
            elif existing_data and force_reprocess:
                logger.info(f"[REPROCESSED] Force reprocessing requested for '{cv_key}'.")
            else:
                logger.info(f"[NEW_CV] Initial processing for '{cv_key}'.")

            current_stage = "validation"
            t_stage_start = asyncio.get_event_loop().time()

            # Helper to save interim status
            async def _save_interim_status(progress: int, stage: str):
                now_iso = datetime.now(timezone.utc).isoformat()
                interim_data = {
                    "id": cv_key,
                    "scan_id": cv_key,
                    "result_generation_id": result_generation_id,
                    "analysis_run_id": analysis_run_id,
                    "analysis_version": analysis_run_id,
                    "generation_sequence": generation_sequence,
                    "status": "processing",

                    "progress": progress,
                    "stage": stage,
                    "filename": filename,
                    "storage_filename": storage_filename,
                    "candidate_id": identity.candidate_id,
                    "source_candidate_id": source_candidate_id,
                    "cv_id": identity.cv_id,
                    "cv_hash": cv_hash,
                    "identity": identity_metadata,
                    "legacy_cv_keys": legacy_cv_keys,
                    "created_at": existing_data.get("created_at") if existing_data and existing_data.get("created_at") else now_iso,
                    "updated_at": now_iso,
                }


                try:
                    await asyncio.to_thread(
                        ResultRepository.atomic_save_result,
                        result_filename,
                        interim_data,
                    )
                except Exception as e:
                    logger.warning(f"Failed to save interim status for '{cv_key}': {e}")

                if job_id:
                    try:
                        await asyncio.to_thread(
                            ProcessingJobRepository.transition,
                            job_id,
                            JobState.PROCESSING,
                            progress=progress,
                            stage=stage,
                            message=f"{progress}% - CV processing at stage {stage}.",
                        )
                    except Exception as e:
                        logger.debug(f"Failed to update processing job progress for '{job_id}': {e}")

            await _save_interim_status(15, current_stage)
            stage_durations_ms["validation_ms"] = round((asyncio.get_event_loop().time() - t_stage_start) * 1000.0, 2)

            current_stage = "parsing"
            await _save_interim_status(30, current_stage)

            # Markdown Generation & Persistence stage
            t_doc_start = asyncio.get_event_loop().time()
            document_cache_key = CacheKey.for_document_extraction(
                document_hash=cv_hash,
                parser_version=settings.EXTRACTION_PARSER_VERSION,
                schema_version=settings.EXTRACTION_SCHEMA_VERSION,
            ).to_key()
            cached_extraction = None
            if not force_reprocess:
                cached_extraction = await asyncio.to_thread(doc_cache_manager.get, document_cache_key)

            if isinstance(cached_extraction, dict):
                try:
                    extraction = MarkdownResult.from_dict(cached_extraction)
                    logger.info(f"[MD_CACHE_HIT] Reusing versioned extraction for doc={cv_hash[:12]}...")
                except Exception as cache_exc:
                    logger.warning(f"Invalid cached extraction for doc={cv_hash[:12]}: {cache_exc}")
                    cached_extraction = None

            if not isinstance(cached_extraction, dict):
                extraction = await asyncio.to_thread(
                    MarkdownGenerator.generate_with_timeout,
                    filename=filename,
                    content=content,
                    timeout_seconds=timeout_seconds,
                )
                await asyncio.to_thread(doc_cache_manager.set, document_cache_key, extraction.to_dict())
                logger.info(f"[MD_CACHE_SET] Cached versioned extraction for doc={cv_hash[:12]}...")

            CacheIndex.add("doc_by_hash", cv_hash, document_cache_key)
            markdown_text = extraction.markdown
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
            resume_json = ResumeJsonExtractor.extract(markdown_text, quality_metrics, filename=filename)
            normalized_resume = NormalizedResume.model_validate(resume_json["normalized"])

            from app.services.experience_calculator import ExperienceCalculator

            canonical_exp = ExperienceCalculator.calculate_canonical_experience(resume_json, markdown_text, candidate_id=cv_key)
            calculated_exp = canonical_exp["experience_years"]
            experience_state = canonical_exp["experience_state"]
            gross_display = canonical_exp["gross_display"]
            total_experience_months = canonical_exp["total_experience_months"]
            quality_metrics["experience_years"] = calculated_exp

            stage_durations_ms["resume_extraction_ms"] = round((asyncio.get_event_loop().time() - t_ext_start) * 1000.0, 2)

            from app.services.embedding_service import (
                generate_candidate_multi_vector_embeddings,
                save_candidate_embedding,
            )
            from app.services.match_service import MatchService

            def _generate_and_store_embedding():
                multi_vecs = generate_candidate_multi_vector_embeddings(
                    cv_key,
                    extraction.markdown,
                    resume_json=resume_json,
                )
                overall_emb = multi_vecs.get("overall") or EmbeddingService.generate_embedding(
                    extraction.markdown,
                    model_version=None,
                    identifier=cv_key,
                )
                if overall_emb:
                    save_candidate_embedding(
                        cv_key,
                        overall_emb,
                        cv_hash,
                        profile_embedding=multi_vecs.get("profile"),
                        skills_embedding=multi_vecs.get("skills"),
                        experience_embedding=multi_vecs.get("experience"),
                        projects_embedding=multi_vecs.get("projects"),
                        domain_embedding=multi_vecs.get("domain"),
                    )
                return overall_emb

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
                cv_key=cv_key,
                source_candidate_id=source_candidate_id,
                docling_extraction_ms=docling_duration_ms,
                cv_embedding=cv_embedding,
                resume_json=resume_json,
                normalized_resume=normalized_resume,
                deterministic_experience=normalized_resume.experience.authoritative_years,
            )
            stage_durations_ms["matching_ms"] = round((asyncio.get_event_loop().time() - t_match_start) * 1000.0, 2)

            contact_info = (resume_json or {}).get("contact_info") or {}
            extracted_name = contact_info.get("name") or contact_info.get("full_name") or "Unknown Candidate"
            email = contact_info.get("email")
            phone = contact_info.get("phone")
            name_confidence = contact_info.get("name_confidence")
            name_extraction_source = contact_info.get("extraction_source")

            location_val = contact_info.get("location")
            from app.services.resume_field_extractor import ResumeFieldExtractor

            work_exp = (resume_json or {}).get("work_experience") or []
            latest_exp = ResumeFieldExtractor.resolve_latest_employment(work_exp)
            job_title_val = contact_info.get("job_title") or latest_exp.get("job_title")
            company_val = contact_info.get("company_name") or contact_info.get("company") or latest_exp.get("company")

            raw_fc = contact_info.get("field_confidence") or {}
            raw_fct = contact_info.get("field_confidence_tiers") or {}

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

            now_iso = datetime.now(timezone.utc).isoformat()
            created_at = existing_data.get("created_at") if existing_data and existing_data.get("created_at") else now_iso
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
                "result_generation_id": result_generation_id,
                "analysis_run_id": analysis_run_id,
                "analysis_version": analysis_run_id,
                "generation_sequence": generation_sequence,
                "document_hash": cv_hash,


                "parsed_at": now_iso,
                "candidate_id": identity.candidate_id,
                "source_candidate_id": source_candidate_id,
                "cv_id": identity.cv_id,
                "filename": filename,
                "original_filename": original_filename or filename,
                "display_filename": display_filename or filename,
                "storage_filename": storage_filename,
                "content_type": content_type,
                "cv_hash": cv_hash,
                "identity": identity_metadata,
                "legacy_cv_keys": legacy_cv_keys,
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
                "experience_version": getattr(settings, "EXPERIENCE_CALCULATOR_VERSION", "2.0.0"),
                "taxonomy_version": getattr(settings, "TAXONOMY_VERSION", "1.5.0"),
                "matching_version": getattr(settings, "MATCHING_VERSION", "2.1.0"),
                "rule_config_version": current_rule_config_version,
                "hiring_risk_policy_version": current_hiring_risk_policy_version,
                "hiring_risk_prompt_version": current_hiring_risk_prompt_version,
                "hiring_risk_prompt_identity": current_hiring_risk_prompt_identity,
                "optimized_prompt_version": current_optimized_prompt_version,
                "llm_model_version": current_llm_model_version,
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
                "experience_state": experience_state,
                "gross_display": gross_display,
                "experience_years": calculated_exp,
                "total_experience_years": calculated_exp,
                "total_experience_months": total_experience_months,
                "seniority": canonical_exp["seniority"],
                "experience_summary": canonical_exp,
                "work_experience": canonical_exp["normalized_employment"],
                "experience_gap_analysis": canonical_exp.get("gap_analysis"),
                "quality_metrics": quality_metrics,
                "resume_json": resume_json,
                "normalized_resume": normalized_resume.model_dump(mode="json"),
                "extraction_integrity": resume_json.get("extraction_integrity"),
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
            await asyncio.to_thread(
                UploadService.cleanup_after_processing,
                storage_filename,
                succeeded=result_data.get("persistence_status") == ResultRepository.PERSISTENCE_DURABLE,
            )

            return result_data

        except CVIdentityCollisionError:
            UploadService.remove_stored_upload(storage_filename)
            logger.warning(f"Rejected colliding CV identity '{cv_key}' without altering its existing result.")
            raise
        except Exception as exc:
            logger.exception(f"CV processing failed for '{cv_key}' at stage '{current_stage}': {exc}")
            now_iso = datetime.now(timezone.utc).isoformat()

            stage_to_step = {
                "parsing": "Docling Parsing",
                "extraction": "Resume Extraction",
                "ai_analysis": "AI Analysis",
                "matching": "Job Matching",
                "complete": "Finalizing",
            }
            failed_step = stage_to_step.get(current_stage, current_stage)

            failure_data = {
                "id": cv_key,
                "scan_id": cv_key,
                "analysis_run_id": analysis_run_id,
                "analysis_version": analysis_run_id,
                "filename": filename,
                "storage_filename": storage_filename,
                "content_type": content_type,
                "cv_hash": cv_hash,
                "identity": identity_metadata,
                "legacy_cv_keys": legacy_cv_keys,
                "candidate_id": identity.candidate_id,
                "source_candidate_id": source_candidate_id,
                "cv_id": identity.cv_id,
                "parsed_at": now_iso,
                "created_at": now_iso,
                "updated_at": now_iso,
                "scanned_at": now_iso,
                "status": "FAILED",
                "progress": 100,
                "is_complete": False,
                "error": "CV processing failed.",
                "message": f"CV processing failed at {failed_step}.",
                "stage": current_stage,
                "failed_step": failed_step,
                "error_details": None,
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
            await asyncio.to_thread(
                UploadService.cleanup_after_processing,
                storage_filename,
                succeeded=False,
            )
            raise


async def scan_uploads_directory(
    uploads_dir: str | Path = settings.UPLOADS_DIR,
    batch_size: int | None = None,
    max_workers: int | None = None,
    throttle_delay: float | None = None,
) -> list[dict[str, Any]]:
    path = Path(uploads_dir)
    submissions: list[dict[str, Any]] = []

    if not path.exists():
        logger.warning(f"Directory '{uploads_dir}' does not exist.")
        return submissions

    supported = {f".{ext}" for ext in settings.ALLOWED_EXTENSIONS}
    files = sorted((f for f in path.iterdir() if f.is_file() and f.suffix.lower() in supported), key=lambda item: item.name.casefold())

    if not files:
        logger.info(f"No supported CV files found in '{uploads_dir}'.")
        return submissions

    logger.info(f"Found {len(files)} CV file(s) in '{uploads_dir}'. Enqueueing to RQ...")

    from app.services.processing_queue import ProcessingQueueService

    for file_obj in files:
        content = file_obj.read_bytes()
        identity = resolve_cv_identity(file_obj.name)
        retained = UploadService.persist_bytes(
            filename=file_obj.name,
            content=content,
            storage_key=identity.canonical_key,
        )
        ResultRepository.assert_identity_available(identity, retained.content_hash)
        submission = ProcessingQueueService.submit_upload(
            cv_key=identity.canonical_key,
            content_hash=retained.content_hash,
            filename=retained.safe_filename,
            storage_filename=retained.storage_filename,
            content_type=retained.detected_content_type,
        )
        submissions.append(
            {
                "filename": retained.safe_filename,
                "job_id": submission.record.job_id,
                "job_state": submission.record.state,
                "cv_key": submission.record.cv_key,
                "reused_existing_job": submission.reused_existing_job,
            }
        )

    logger.info("Queued %s CV file(s) for FIFO processing.", len(submissions))
    return submissions
