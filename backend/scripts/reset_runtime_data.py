#!/usr/bin/env python3
"""
CV Analyzer - Safe Fresh Reset Script

Audits and clears generated/temporary runtime data while preserving:
- Database schema & migrations
- Master taxonomy (domains, job families, designations, synonyms, abbreviations, skills)
- Department domain mappings & domain embeddings
- Vacancy embeddings & master vacancy data
- System configuration & rule profiles
- Prompt templates
- Historical validation benchmarks
"""

from __future__ import annotations
import glob
import os
import shutil
import sys
from pathlib import Path

from sqlalchemy import inspect, text

# Ensure backend root is on sys.path when executed directly
backend_root = Path(__file__).resolve().parent.parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

from app.core.config import settings
from app.core.database import postgres_app_engine
from app.core.logging import logger

TABLES_TO_TRUNCATE = [
    # Public schema generated state
    "public.cv_results",
    "public.candidate_embeddings",
    "public.department_alias_mappings",
    # CVAI schema generated state
    "cvai.candidates",
    "cvai.cv_documents",
    "cvai.cv_results",
    "cvai.match_results",
    "cvai.match_results_history",
    # Integration schema generated sync state
    "integration.sync_runs",
    "integration.sync_errors",
    "integration.sync_watermarks",
    "integration.candidate_snapshots",
    # Validation schema generated test run state
    "validation.shadow_validation_runs",
    "validation.shadow_validation_results",
    "validation.validation_metrics_snapshots",
    "validation.hr_disagreement_reviews",
]

PRESERVED_TABLES = [
    "public.DepartmentDomainMaster",
    "public.domain_embeddings",
    "public.vacancy_embeddings",
    "public.system_config",
    "cvai.domains",
    "cvai.job_families",
    "cvai.designations",
    "cvai.designation_synonyms",
    "cvai.designation_abbreviations",
    "cvai.skills",
    "cvai.designation_skills",
    "cvai.family_compatibilities",
    "cvai.geo_locations",
    "cvai.section_headings",
    "cvai.stop_words",
    "cvai.name_denylists",
    "cvai.prompt_templates",
    "cvai.rule_*",
    "cvai.schema_migrations",
    "integration.department_snapshots",
    "integration.designation_snapshots",
    "integration.job_profile_snapshots",
    "integration.vacancy_snapshots",
    "validation.airis_historical_benchmarks",
]


def clear_postgres_generated_data() -> dict[str, int]:
    """Truncate generated runtime tables while preserving schema and master data."""
    cleared_summary: dict[str, int] = {}
    print("--- Clearing PostgreSQL Generated Data ---")
    with postgres_app_engine.connect() as conn:
        for full_tablename in TABLES_TO_TRUNCATE:
            try:
                # Check if table exists before truncating
                schema, table = full_tablename.split(".", 1)
                check_sql = text(
                    "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = :s AND table_name = :t"
                )
                exists = conn.execute(check_sql, {"s": schema, "t": table}).scalar()
                if exists:
                    count_before = conn.execute(text(f'SELECT COUNT(*) FROM "{schema}"."{table}"')).scalar()
                    conn.execute(text(f'TRUNCATE TABLE "{schema}"."{table}" CASCADE;'))
                    cleared_summary[full_tablename] = count_before
                    print(f"  [CLEARED] {full_tablename} ({count_before} rows removed)")
                else:
                    print(f"  [SKIP] {full_tablename} (table does not exist)")
            except Exception as exc:
                print(f"  [ERROR] {full_tablename}: {exc}")
        conn.commit()
    return cleared_summary


def clear_redis_state() -> bool:
    """Clear all Redis keys (queues, failed jobs, cache indexes, L2 response caches)."""
    print("\n--- Clearing Redis & RQ Queues ---")
    if not settings.REDIS_URL:
        print("  [SKIP] REDIS_URL not configured.")
        return False
    try:
        import redis

        r = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
        r.flushdb()
        print("  [OK] Redis DB flushed successfully (cleared queues, failed jobs & candidate caches).")
        return True
    except Exception as exc:
        print(f"  [ERROR] Failed to flush Redis: {exc}")
        return False


def clear_local_disk_caches() -> list[str]:
    """Purge local disk cache directories, SQLite LLM cache DB, and uploaded candidate CV files."""
    print("\n--- Clearing Local Disk Caches & Upload Artifacts ---")
    removed_items: list[str] = []

    # 1. SQLite LLM Cache DB
    db_file = Path("llm_cache.db")
    if db_file.exists():
        try:
            db_file.unlink()
            removed_items.append(str(db_file))
            print(f"  [REMOVED] File: {db_file}")
        except Exception as exc:
            print(f"  [ERROR] Removing {db_file}: {exc}")

    # 2. Upload and Cache Directories to clean
    cache_dir_names = [".doc_cache", ".embed_cache", ".llm_cache", ".processing_jobs", ".locks", "results"]
    upload_roots = [Path("uploads"), Path("backend/uploads"), Path("../uploads")]

    for root in upload_roots:
        if not root.exists():
            continue

        # Remove sub-cache directories
        for cdir in cache_dir_names:
            target_dir = root / cdir
            if target_dir.exists():
                for f in target_dir.glob("*"):
                    if f.is_file() or f.is_symlink():
                        f.unlink()
                    elif f.is_dir():
                        shutil.rmtree(f)
                removed_items.append(str(target_dir))
                print(f"  [CLEARED] Cache Directory: {target_dir}")

        # Remove uploaded CV files (*.pdf, *.docx, *.doc)
        for ext in ["*.pdf", "*.docx", "*.doc", "*.json", "*.txt"]:
            for cv_file in root.glob(ext):
                if cv_file.is_file():
                    cv_file.unlink()
                    removed_items.append(str(cv_file))
                    print(f"  [REMOVED] Candidate File: {cv_file}")

    # 3. Pytest / Python Cache directories
    for pcache in [Path(".pytest_cache"), Path(".ruff_cache"), Path("backend/.pytest_cache")]:
        if pcache.exists():
            shutil.rmtree(pcache, ignore_errors=True)
            print(f"  [REMOVED] Python Cache: {pcache}")

    return removed_items


def verify_clean_state() -> None:
    """Verify that all generated state is empty and master data is intact."""
    print("\n--- Verification Check ---")
    with postgres_app_engine.connect() as conn:
        inspector = inspect(postgres_app_engine)

        print("\n1. Generated Tables Verification (Should all be 0):")
        all_clean = True
        for full_tablename in TABLES_TO_TRUNCATE:
            schema, table = full_tablename.split(".", 1)
            try:
                check_sql = text(
                    "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = :s AND table_name = :t"
                )
                exists = conn.execute(check_sql, {"s": schema, "t": table}).scalar()
                if exists:
                    count = conn.execute(text(f'SELECT COUNT(*) FROM "{schema}"."{table}"')).scalar()
                    status = "CLEAN (0 rows)" if count == 0 else f"DIRTY ({count} rows remaining!)"
                    print(f"  - {full_tablename}: {status}")
                    if count != 0:
                        all_clean = False
            except Exception as exc:
                print(f"  - {full_tablename}: Verification Error {exc}")

        print("\n2. Master Data & Taxonomy Verification (Must be intact):")
        check_masters = [
            "public.DepartmentDomainMaster",
            "public.domain_embeddings",
            "public.vacancy_embeddings",
            "cvai.designation_synonyms",
            "cvai.designations",
            "cvai.domains",
            "cvai.job_families",
            "cvai.prompt_templates",
            "validation.airis_historical_benchmarks",
        ]
        for full_tablename in check_masters:
            schema, table = full_tablename.split(".", 1)
            try:
                count = conn.execute(text(f'SELECT COUNT(*) FROM "{schema}"."{table}"')).scalar()
                print(f"  - {full_tablename}: INTACT ({count} rows preserved)")
            except Exception as exc:
                print(f"  - {full_tablename}: Check Error {exc}")

        if all_clean:
            print("\n✅ SYSTEM FRESH RESET SUCCESSFUL: Database and cache are 100% clean and ready for fresh testing.")
        else:
            print("\n⚠️ SYSTEM RESET COMPLETED WITH WARNINGS: Some generated tables still contain data.")


def main() -> None:
    print("==================================================")
    print("    CV ANALYZER FRESH RESET / CLEAN START    ")
    print("==================================================")
    clear_postgres_generated_data()
    clear_redis_state()
    clear_local_disk_caches()
    verify_clean_state()


if __name__ == "__main__":
    main()
