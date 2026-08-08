from __future__ import annotations
import json
import time
from typing import Any
import pytest

from app.core.cache import _REDIS_CLIENT, cv_result_cache_manager, match_result_cache_manager, CacheInvalidator
from app.core.config import settings
from app.core.database import PostgresAppSession
from app.models.result import CVResult
from app.repositories.result import ResultRepository
from app.services.candidate_search_service import CandidateSearchService
from app.schemas.candidate_search import CandidateSearchRequest


def create_sample_result_data(
    cv_key: str = "cv_test_gen_1001",
    gen_id: str = "gen_1000000000000_abc12345",
    exp_years: float = 7.5,
    full_name: str = "Test Candidate",
    email: str = "test@example.com",
    cv_hash: str = "abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
) -> dict[str, Any]:
    return {
        "id": cv_key,
        "scan_id": cv_key,
        "result_generation_id": gen_id,
        "cv_hash": cv_hash,
        "document_hash": cv_hash,
        "parsed_at": "2026-08-08T12:00:00+00:00",
        "created_at": "2026-08-08T12:00:00+00:00",
        "updated_at": "2026-08-08T12:00:00+00:00",
        "candidate_id": "1001",
        "cv_id": "2001",
        "filename": f"{cv_key}.pdf",
        "full_name": full_name,
        "candidate_name": full_name,
        "email": email,
        "phone": "+1234567890",
        "location": "New York, NY",
        "job_title": "Senior Software Engineer",
        "company_name": "Acme Corp",
        "status": "COMPLETED",
        "progress": 100,
        "stage": "complete",
        "is_complete": True,
        "experience_state": "CALCULATED",
        "gross_display": "7 years 6 months",
        "experience_years": exp_years,
        "total_experience_years": exp_years,
        "total_experience_months": int(exp_years * 12),
        "seniority": "Senior",
        "parser_version": settings.EXTRACTION_PARSER_VERSION,
        "schema_version": settings.EXTRACTION_SCHEMA_VERSION,
        "experience_version": getattr(settings, "EXPERIENCE_CALCULATOR_VERSION", "2.0.0"),
        "taxonomy_version": getattr(settings, "TAXONOMY_VERSION", "1.5.0"),
        "matching_version": getattr(settings, "MATCHING_VERSION", "2.1.0"),
        "characters": 120,
        "page_count": 1,
        "text": f"{full_name} - Senior Software Engineer\n{email}\nNew York, NY",
        "markdown": f"# {full_name}\n\nSenior Software Engineer\nEmail: {email}",
        "quality_metrics": {"experience_years": exp_years},

        "resume_json": {
            "contact_info": {"name": full_name, "email": email},
            "work_experience": [
                {
                    "job_title": "Senior Software Engineer",
                    "company": "Acme Corp",
                    "dates": "2018 - 2024",
                }
            ],
        },
        "match_analysis": {
            "primary_department": "Engineering",
            "recommended_department": "Engineering",
            "best_match": {
                "job_title": "Senior Software Engineer",
                "department": "Engineering",
                "department_name": "Engineering",
                "vacancy_fit_score": 92.5,
                "overall_score": 92.5,
                "classification": "HIGH",
            },
        },
    }


def test_canonical_metadata_enrichment():
    raw_data = {"full_name": "Jane Doe", "cv_hash": "hash_123", "status": "COMPLETED"}
    enriched = ResultRepository.ensure_canonical_metadata(raw_data)
    
    assert "result_generation_id" in enriched
    assert enriched["result_generation_id"].startswith("gen_")
    assert enriched["schema_version"] == settings.EXTRACTION_SCHEMA_VERSION
    assert enriched["document_hash"] == "hash_123"
    assert "payload_checksum" in enriched
    assert len(enriched["payload_checksum"]) == 64


def test_ensure_canonical_metadata_does_not_assign_generation_sequence_by_default():
    raw_data = {"full_name": "Jane Doe", "cv_hash": "hash_456", "status": "COMPLETED"}
    enriched = ResultRepository.ensure_canonical_metadata(raw_data)

    assert "generation_sequence" not in enriched or enriched["generation_sequence"] is None


def test_atomic_save_result_uses_db_sequence_for_new_rows():
    cv_key = "cv_test_db_seq_1"
    fn = f"{cv_key}.json"
    source_data = create_sample_result_data(cv_key=cv_key, gen_id="gen_db_seq_1")
    source_data.pop("generation_sequence", None)

    ResultRepository.atomic_save_result(fn, source_data)
    result = ResultRepository.read_result_by_filename(fn)

    assert result is not None
    assert result["generation_sequence"] is not None
    assert isinstance(result["generation_sequence"], int)
    assert result["generation_sequence"] > 0
    assert result["result_generation_id"] == "gen_db_seq_1"

    try:
        with PostgresAppSession() as session:
            session.query(CVResult).filter(CVResult.cv_key == cv_key).delete()
            session.commit()
    except Exception:
        pass
    cv_result_cache_manager.delete(fn)


def test_redis_rehydrate_on_generation_mismatch():
    cv_key = "cv_test_mismatch_gen_1"
    fn = f"{cv_key}.json"

    data_v1 = create_sample_result_data(cv_key, gen_id="gen_v1", exp_years=5.0)
    ResultRepository.atomic_save_result(fn, data_v1)

    # Manually overwrite Redis with an old generation ID
    stale_data = data_v1.copy()
    stale_data["result_generation_id"] = "gen_v0_stale"
    stale_data["experience_years"] = 2.0
    stale_data["payload_checksum"] = "invalid_checksum_123"
    cv_result_cache_manager.set(fn, stale_data)

    # Perform read_result_by_filename: should detect generation/checksum mismatch and rehydrate from DB
    res = ResultRepository.read_result_by_filename(fn)
    assert res is not None
    assert res["result_generation_id"] == "gen_v1"
    assert res["experience_years"] == 5.0
    assert res["payload_checksum"] == ResultRepository.compute_payload_checksum(data_v1)


def test_out_of_order_worker_write_rejection():
    cv_key = "cv_test_out_of_order_1"
    fn = f"{cv_key}.json"

    newer_data = create_sample_result_data(cv_key, gen_id="gen_2000", exp_years=10.0)
    newer_data["generation_sequence"] = 2000
    ResultRepository.atomic_save_result(fn, newer_data)

    stale_worker_data = create_sample_result_data(cv_key, gen_id="gen_1000_stale", exp_years=3.0)
    stale_worker_data["generation_sequence"] = 1000
    
    ResultRepository.atomic_save_result(fn, stale_worker_data)

    # Verify repository still holds newer_data
    res = ResultRepository.read_result_by_filename(fn)
    assert res is not None
    assert res["result_generation_id"] == "gen_2000"
    assert res["generation_sequence"] == 2000
    assert res["experience_years"] == 10.0




def test_reprocess_purges_legacy_aliases():
    cv_key = "test_candidate_key_99"
    fn = f"{cv_key}.json"
    doc_hash = "doc_hash_99999"

    data = create_sample_result_data(cv_key, gen_id="gen_99", cv_hash=doc_hash)
    ResultRepository.atomic_save_result(fn, data)

    # Add legacy alias entries
    cv_result_cache_manager.set(f"cv_{cv_key}.json", data)
    cv_result_cache_manager.set(f"cv_document_{cv_key}.json", data)

    # Perform invalidation
    cv_result_cache_manager.delete(fn)
    cv_result_cache_manager.delete_by_pattern(f"*{cv_key}*")
    cv_result_cache_manager.delete_by_pattern(f"*cv_{cv_key}*")
    cv_result_cache_manager.delete_by_pattern(f"*cv_document_{cv_key}*")
    CacheInvalidator.invalidate_cv(doc_hash)

    # Verify all are deleted
    assert cv_result_cache_manager.get(fn) is None
    assert cv_result_cache_manager.get(f"cv_{cv_key}.json") is None
    assert cv_result_cache_manager.get(f"cv_document_{cv_key}.json") is None


def test_field_by_field_pipeline_consistency():
    cv_key = "cv_test_e2e_parity_1"
    fn = f"{cv_key}.json"
    gen_id = "gen_e2e_8888"

    source_data = create_sample_result_data(
        cv_key=cv_key,
        gen_id=gen_id,
        exp_years=7.0,
        full_name="Alice Smith",
        email="alice@smith.org",
    )


    # Save to PostgreSQL and Redis
    ResultRepository.atomic_save_result(fn, source_data)

    # 1. Read back via Repository (Postgres / Redis parity check)
    db_res = ResultRepository.read_result_by_filename(fn)
    assert db_res is not None
    assert db_res["result_generation_id"] == gen_id
    assert db_res["full_name"] == "Alice Smith"
    assert db_res["email"] == "alice@smith.org"
    assert db_res["experience_years"] == 7.0
    assert db_res["total_experience_months"] == 84
    assert db_res["payload_checksum"] == ResultRepository.compute_payload_checksum(source_data)

    # 2. Query via CandidateSearchService (List API parity check)
    req = CandidateSearchRequest(query="Alice Smith", limit=10)
    search_res = CandidateSearchService.search_candidates(req)
    matched = [c for c in search_res.candidates if c.id == cv_key or c.filename == f"{cv_key}.pdf"]
    assert len(matched) == 1
    cand_item = matched[0]
    
    assert cand_item.full_name == "Alice Smith"
    assert cand_item.email == "alice@smith.org"
    assert cand_item.experience_years == 7.0
    # 3. Simulate Candidate Detail API (get_candidate_detail)
    from app.api.candidates import get_candidate_detail
    detail_res = get_candidate_detail(cv_key)
    assert detail_res["result_generation_id"] == gen_id
    assert detail_res["full_name"] == "Alice Smith"
    assert detail_res["experience_years"] == 7.0
    assert detail_res["experience_state"] == "CALCULATED"

    assert detail_res["schema_version"] == settings.EXTRACTION_SCHEMA_VERSION
    assert detail_res["payload_checksum"] == ResultRepository.compute_payload_checksum(source_data)

    # 4. Frontend Component Contract Verification
    typeof_title = type(detail_res["work_experience"][0]["role"]).__name__
    assert typeof_title == "str"
    assert detail_res.get("experience_gap_analysis") is not None or detail_res.get("experience_summary") is not None

    # Cleanup DB test row
    try:
        with PostgresAppSession() as session:
            session.query(CVResult).filter(CVResult.cv_key == cv_key).delete()
            session.commit()
    except Exception:
        pass
    cv_result_cache_manager.delete(fn)


def test_checksum_sensitivity_to_business_fields():
    base_data = create_sample_result_data("cv_test_checksum_sens_1", gen_id="gen_sens_1")
    base_checksum = ResultRepository.compute_payload_checksum(base_data)

    # 1. Modify domain
    d_domain = base_data.copy()
    d_domain["domain"] = "Finance & Banking"
    assert ResultRepository.compute_payload_checksum(d_domain) != base_checksum

    # 2. Modify gap analysis
    d_gaps = base_data.copy()
    d_gaps["experience_gap_analysis"] = {"total_gap_months": 14, "has_concerning_gaps": True}
    assert ResultRepository.compute_payload_checksum(d_gaps) != base_checksum

    # 3. Modify work experience
    d_work = base_data.copy()
    d_work["work_experience"] = [{"job_title": "CTO", "company": "Global Corp", "dates": "2015 - 2024"}]
    assert ResultRepository.compute_payload_checksum(d_work) != base_checksum

    # 4. Modify designation
    d_desig = base_data.copy()
    d_desig["designation"] = "Lead Architect"
    assert ResultRepository.compute_payload_checksum(d_desig) != base_checksum

    # 5. Modify vacancy matches
    d_vac = base_data.copy()
    d_vac["vacancy_matches"] = {"job_title": "Principal Architect", "score": 99.0}
    assert ResultRepository.compute_payload_checksum(d_vac) != base_checksum


def test_stale_worker_rejection_across_derived_caches():
    cv_key = "cv_test_stale_worker_derived_1"
    fn = f"{cv_key}.json"

    # Worker B completes first with generation sequence 2000
    worker_b_data = create_sample_result_data(cv_key, gen_id="gen_2000_workerB", exp_years=10.0)
    worker_b_data["generation_sequence"] = 2000
    ResultRepository.atomic_save_result(fn, worker_b_data)

    # Worker A completes later with older generation sequence 1000
    worker_a_data = create_sample_result_data(cv_key, gen_id="gen_1000_workerA", exp_years=2.0)
    worker_a_data["generation_sequence"] = 1000
    ResultRepository.atomic_save_result(fn, worker_a_data)

    # Verify PostgreSQL + Redis still hold Worker B's sequence 2000 result
    current_res = ResultRepository.read_result_by_filename(fn)
    assert current_res is not None
    assert current_res["result_generation_id"] == "gen_2000_workerB"
    assert current_res["generation_sequence"] == 2000
    assert current_res["experience_years"] == 10.0

    # Verify is_generation_current returns False for Worker A's sequence 1000
    is_curr = ResultRepository.is_generation_current(cv_key, incoming_generation="gen_1000_workerA", incoming_sequence=1000, resource="match_result")
    assert is_curr is False

    # Cleanup DB test row
    try:
        with PostgresAppSession() as session:
            session.query(CVResult).filter(CVResult.cv_key == cv_key).delete()
            session.commit()
    except Exception:
        pass
    cv_result_cache_manager.delete(fn)


def test_same_millisecond_starts_and_db_monotonic_ordering():
    cv_key = "cv_test_same_ms_concurrency"
    fn = f"{cv_key}.json"

    # 1. Fetch sequence values from PostgreSQL DB
    seq1 = ResultRepository.fetch_next_generation_sequence()
    seq2 = ResultRepository.fetch_next_generation_sequence()
    assert seq2 > seq1, "PostgreSQL sequence must strictly increment"

    # Both workers start in the same millisecond timestamp
    ms_timestamp = "1786173000000"
    worker_1_gen = f"gen_{ms_timestamp}_worker1"
    worker_2_gen = f"gen_{ms_timestamp}_worker2"

    w1_data = create_sample_result_data(cv_key, gen_id=worker_1_gen, exp_years=5.0)
    w1_data["generation_sequence"] = seq1

    w2_data = create_sample_result_data(cv_key, gen_id=worker_2_gen, exp_years=12.0)
    w2_data["generation_sequence"] = seq2

    # Worker 2 finishes first and commits higher sequence seq2
    ResultRepository.atomic_save_result(fn, w2_data)

    # Worker 1 finishes later with lower sequence seq1 (even though timestamp string is identical)
    ResultRepository.atomic_save_result(fn, w1_data)

    # Assert PostgreSQL + Redis retain Worker 2's result
    final_res = ResultRepository.read_result_by_filename(fn)
    assert final_res is not None
    assert final_res["result_generation_id"] == worker_2_gen
    assert final_res["generation_sequence"] == seq2
    assert final_res["experience_years"] == 12.0

    # Cleanup DB test row
    try:
        with PostgresAppSession() as session:
            session.query(CVResult).filter(CVResult.cv_key == cv_key).delete()
            session.commit()
    except Exception:
        pass
    cv_result_cache_manager.delete(fn)



