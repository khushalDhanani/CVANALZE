"""
Bulk CV Reprocessing & Data Integrity Validation Script.
Reprocesses all local candidate CVs from disk/PostgreSQL, validates the pipeline outputs,
and generates a per-candidate audit report.
"""
from __future__ import annotations
import asyncio
import hashlib
import sys
from pathlib import Path
from typing import Any

# Ensure backend app module is in python path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.core.database import PostgresAppSession
from app.models.result import CVResult
from app.repositories.processing_job import ProcessingJobRepository
from app.repositories.result import ResultRepository
from app.schemas.contracts import JobState
from app.services.processing_queue import ProcessingQueueService
from app.services.recommendation_service import RecommendationService
from app.services.upload_service import UploadService


async def reprocess_all_candidates() -> list[dict[str, Any]]:
    # Get all active records from Postgres
    with PostgresAppSession() as session:
        records = session.query(CVResult).order_by(CVResult.parsed_at.desc()).all()
        cv_keys = [r.cv_key for r in records]

    print(f"🔄 Starting bulk reprocessing for {len(cv_keys)} active candidates...")
    queued_jobs: list[tuple[str, str]] = []

    for idx, cv_key in enumerate(cv_keys, 1):
        print(f"\n[{idx}/{len(cv_keys)}] Reprocessing candidate '{cv_key}'...")
        existing = ResultRepository.resolve_result(cv_key)
        if not existing:
            print(f"  ⚠️ Could not resolve existing result for '{cv_key}'. Skipping.")
            continue

        filename = existing.get("filename") or f"{cv_key}.pdf"
        storage_filename = existing.get("storage_filename")

        # Load file bytes from uploads or storage
        uploads_dir = Path("uploads")
        possible_files = list(uploads_dir.glob(f"{cv_key}*"))
        if not possible_files and storage_filename:
            possible_files = [uploads_dir / storage_filename]

        if not possible_files or not possible_files[0].exists():
            # Search by filename
            possible_files = [f for f in uploads_dir.iterdir() if f.name == filename or f.name.startswith(cv_key)]

        if not possible_files or not possible_files[0].exists():
            print(f"  ⚠️ Source file not found for '{cv_key}'. Using existing result data for validation.")
            continue
        else:
            file_path = possible_files[0]
            content = file_path.read_bytes()
            try:
                retained = UploadService.persist_bytes(
                    filename=filename,
                    content=content,
                    storage_key=cv_key,
                )
                submission = ProcessingQueueService.submit_upload(
                    cv_key=cv_key,
                    content_hash=hashlib.sha256(content).hexdigest(),
                    filename=retained.safe_filename,
                    content_type=retained.detected_content_type,
                    candidate_id=existing.get("candidate_id"),
                    source_candidate_id=existing.get("source_candidate_id") or existing.get("candidate_id"),
                    cv_id=existing.get("cv_id"),
                    force_reprocess=True,
                    storage_filename=retained.storage_filename,
                )
                queued_jobs.append((cv_key, submission.record.job_id))
                print(f"  📦 Queued '{cv_key}' as job '{submission.record.job_id}'.")
            except Exception as exc:
                print(f"  ❌ Could not queue '{cv_key}': {exc}")

    print(f"\nWaiting for {len(queued_jobs)} queued CV job(s) to complete...")
    pending = dict(queued_jobs)
    results = []
    while pending:
        for cv_key, job_id in list(pending.items()):
            record = ProcessingJobRepository.get(job_id)
            if record is not None:
                record = ProcessingQueueService.reconcile_job(record)
            if record is None or record.state not in (JobState.COMPLETED, JobState.COMPLETED_DEGRADED, JobState.FAILED, JobState.CANCELLED):
                continue
            result = ResultRepository.resolve_result(cv_key) or {
                "id": cv_key,
                "status": record.state,
                "message": record.message,
            }

            try:
                recs = RecommendationService.get_candidate_recommendations(cv_key)
            except Exception as rec_exc:
                print(f"  ⚠️ Recommendation generation failed for '{cv_key}': {rec_exc}")
                recs = {}

            results.append({"cv_key": cv_key, "result": result, "recommendations": recs})
            pending.pop(cv_key)
            print(f"  ✅ Job '{job_id}' reached {record.state}.")
        if pending:
            await asyncio.sleep(1)

    return results


def run_integrity_audit(reprocessed_data: list[dict[str, Any]]) -> None:
    print("\n" + "=" * 110)
    print("                      CV PIPELINE END-TO-END DATA INTEGRITY AUDIT TABLE                      ")
    print("=" * 110)
    header = f"| {'Candidate ID':<25} | {'Extracted Name':<25} | {'Exp (Yrs)':<10} | {'Seniority':<12} | {'Top Match':<20} | {'Status':<8} |"
    print(header)
    print("|" + "-" * 27 + "|" + "-" * 27 + "|" + "-" * 12 + "|" + "-" * 14 + "|" + "-" * 22 + "|" + "-" * 10 + "|")

    pass_count = 0
    warn_count = 0
    fail_count = 0

    for item in reprocessed_data:
        cv_key = item["cv_key"]
        r = item["result"]
        recs = item["recommendations"]

        name = r.get("full_name") or r.get("candidate_name") or "Unknown"
        exp_years = r.get("experience_years")
        exp_str = f"{exp_years:.1f}" if exp_years is not None else "N/A"
        seniority = r.get("seniority") or "N/A"

        ma = r.get("match_analysis") or {}
        bm = ma.get("best_match") or {}
        top_match = bm.get("job_title") or "No Vacancy Match"
        if len(top_match) > 18:
            top_match = top_match[:15] + "..."

        # Validate audit rules
        issues = []
        # Check 1: Name should not look like a job title or heading
        if any(kw in name.lower() for kw in ["developer", "engineer", "planning", "executive", "control", "job."]):
            issues.append("Name is job title / heading")
        # Check 2: Experience years should be non-null for candidates with work experience
        work_exp = (r.get("resume_json") or {}).get("work_experience", [])
        if len(work_exp) > 0 and (exp_years is None or exp_years == 0):
            issues.append("Zero experience despite work history")
        # Check 3: Check for empty skills
        skills = (r.get("resume_json") or {}).get("skills")
        all_skills = skills.get("all_skills", []) if isinstance(skills, dict) else (skills or [])
        if len(all_skills) == 0 and len(work_exp) > 0:
            issues.append("Zero skills extracted")

        if not issues:
            status = "PASS"
            pass_count += 1
        elif len(issues) == 1 and "Zero skills" in issues[0]:
            status = "WARNING"
            warn_count += 1
        else:
            status = "FAIL"
            fail_count += 1

        row = f"| {cv_key:<25} | {name:<25} | {exp_str:<10} | {seniority:<12} | {top_match:<20} | {status:<8} |"
        print(row)
        if issues:
            print(f"  └─ Issues: {', '.join(issues)}")

    print("=" * 110)
    print(f"Audit Summary: TOTAL={len(reprocessed_data)} | PASS={pass_count} | WARNING={warn_count} | FAIL={fail_count}")
    print("=" * 110)


if __name__ == "__main__":
    reprocessed = asyncio.run(reprocess_all_candidates())
    run_integrity_audit(reprocessed)
