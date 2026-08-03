#!/usr/bin/env python3
"""
Schema Integrity & Drift Detection Utility for CV Analyzer backend.
Audits live database tables, columns, and migration checksums against expected schema definitions.
"""

import sys
from pathlib import Path

from sqlalchemy import create_engine, text

# Add backend directory to sys.path if invoked from root
script_dir = Path(__file__).resolve().parent
backend_dir = script_dir.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from scripts.run_migrations import (
    compute_checksum,
    detect_dialect,
    get_applied_migrations,
    get_migration_files,
)

EXPECTED_CATALOG: dict[str, dict[str, list[str]]] = {
    "cvai": {
        "cv_documents": [
            "id",
            "cv_hash",
            "filename",
            "content_type",
            "page_count",
            "is_scanned",
            "ocr_applied",
            "text",
            "structured_doc",
        ],
        "candidates": [
            "id",
            "cv_document_id",
            "raw_skills_json",
            "raw_education_json",
            "raw_experience_json",
            "raw_profile_json",
        ],
        "match_results": [
            "id",
            "candidate_id",
            "vacancy_id",
            "overall_score",
            "component_scores_json",
        ],
        "match_results_history": [
            "id",
            "match_result_id",
            "previous_score",
            "new_score",
        ],
        "domains": ["domain_id", "domain_code", "domain_name", "is_active"],
        "job_families": ["family_id", "domain_id", "family_code", "family_name"],
        "designations": [
            "designation_id",
            "family_id",
            "designation_code",
            "designation_name",
        ],
        "designation_synonyms": ["synonym_id", "designation_id", "synonym_text"],
        "skills": ["skill_id", "skill_name"],
        "designation_skills": ["designation_id", "skill_id"],
        "family_compatibilities": [
            "source_family_id",
            "target_family_id",
            "compatibility_score",
        ],
        "geo_locations": ["location_id", "city_name"],
        "section_headings": ["heading_id", "heading_text"],
        "name_denylists": ["denylist_id", "word"],
        "stop_words": ["stopword_id", "word"],
        "scoring_profiles": ["profile_id", "profile_code", "profile_name"],
        "schema_migrations": ["migration_name"],
    },
    "default": {
        "DepartmentDomainMaster": [
            "Id",
            "DomainName",
            "Keywords",
            "DefaultRoles",
            "Priority",
            "IsActive",
        ],
    },
}


def audit_schema_drift(dialect: str | None = None) -> bool:
    """
    Audits the database schema for drift, missing tables, missing columns, and checksum tampering.
    Returns True if schema is healthy, False if drift detected.
    """
    try:
        detected_dialect, db_url = detect_dialect(dialect)
    except Exception as err:
        print(f"❌ Error detecting database: {err}")
        return False

    print("\n" + "=" * 80)
    print(f"DATABASE SCHEMA INTEGRITY & DRIFT AUDIT ({detected_dialect.upper()})")
    print("=" * 80)

    engine = create_engine(db_url)
    drift_issues: list[str] = []

    with engine.connect() as conn:
        # 1. Fetch all tables from DB
        if detected_dialect == "mssql":
            query_tables = text("""
                SELECT TABLE_SCHEMA, TABLE_NAME 
                FROM INFORMATION_SCHEMA.TABLES 
                WHERE TABLE_TYPE = 'BASE TABLE'
            """)
        else:
            query_tables = text("""
                SELECT table_schema, table_name 
                FROM information_schema.tables 
                WHERE table_type = 'BASE TABLE'
            """)

        db_tables_rows = conn.execute(query_tables).fetchall()
        db_tables_by_schema: dict[str, set[str]] = {}
        for schema_name, table_name in db_tables_rows:
            schema_key = schema_name.lower()
            if schema_key not in db_tables_by_schema:
                db_tables_by_schema[schema_key] = set()
            db_tables_by_schema[schema_key].add(table_name)
            # Also store case-insensitive for lookup
            db_tables_by_schema[schema_key].add(table_name.lower())

        # 2. Audit Expected Tables & Columns
        print("\n🔍 Phase 1: Checking Table & Column Structure...")
        for exp_schema, expected_tables in EXPECTED_CATALOG.items():
            for table_name, expected_cols in expected_tables.items():
                table_found = False
                if exp_schema == "default":
                    # Check in dbo or public or root
                    for candidate_schema in ["dbo", "public", "cvai"]:
                        if candidate_schema in db_tables_by_schema:
                            if table_name in db_tables_by_schema[candidate_schema] or table_name.lower() in db_tables_by_schema[candidate_schema]:
                                table_found = True
                                break
                else:
                    if exp_schema in db_tables_by_schema:
                        if table_name in db_tables_by_schema[exp_schema] or table_name.lower() in db_tables_by_schema[exp_schema]:
                            table_found = True

                if not table_found:
                    issue = f"MISSING TABLE: Table '{exp_schema}.{table_name}' was not found in database."
                    drift_issues.append(issue)
                    print(f"   ❌ {issue}")
                    continue

                # Fetch columns for existing table
                query_cols = text("""
                    SELECT COLUMN_NAME 
                    FROM INFORMATION_SCHEMA.COLUMNS 
                    WHERE TABLE_NAME = :table_name
                """)
                cols_rows = conn.execute(query_cols, {"table_name": table_name}).fetchall()
                actual_cols = {c[0].lower() for c in cols_rows}

                missing_cols = [c for c in expected_cols if c.lower() not in actual_cols]
                if missing_cols:
                    issue = f"MISSING COLUMNS in '{exp_schema}.{table_name}': {', '.join(missing_cols)}"
                    drift_issues.append(issue)
                    print(f"   ⚠️  {issue}")
                else:
                    print(f"   ✅ Table '{exp_schema}.{table_name}' verified ({len(cols_rows)} columns).")

        # 3. Checksum & Tampering Audit
        print("\n🔍 Phase 2: Auditing Migration Script Checksums...")
        try:
            applied = get_applied_migrations(conn)
            local_files = get_migration_files(detected_dialect, mode="up")

            for file_path in local_files:
                version = file_path.name.split("_")[0]
                content = file_path.read_text(encoding="utf-8")
                checksum = compute_checksum(content)

                if version in applied:
                    recorded_checksum = applied[version]["checksum"]
                    if recorded_checksum and recorded_checksum != checksum:
                        issue = f"CHECKSUM DRIFT in [{version}] {file_path.name}: local SHA-256 differs from recorded history."
                        drift_issues.append(issue)
                        print(f"   🚨 {issue}")
                    else:
                        print(f"   ✅ Migration [{version}] {file_path.name} checksum verified.")
                else:
                    print(f"   ℹ️  Migration [{version}] {file_path.name} is pending execution.")
        except Exception as exc:
            issue = f"Migration tracking table not initialized or query failed ({exc})"
            drift_issues.append(issue)
            print(f"   ⚠️  {issue}")

    # Summary Output
    print("\n" + "=" * 80)
    if not drift_issues:
        print("🎉 SCHEMA DRIFT AUDIT PASSED: Database schema is 100% healthy and consistent!")
        print("=" * 80 + "\n")
        return True
    else:
        print(f"⚠️  SCHEMA DRIFT DETECTED: Found {len(drift_issues)} discrepancy issue(s):")
        for i, issue in enumerate(drift_issues, 1):
            print(f"  {i}. {issue}")
        print("=" * 80 + "\n")
        return False


def main():
    dialect_arg = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("-") else None
    healthy = audit_schema_drift(dialect_arg)
    sys.exit(0 if healthy else 1)


if __name__ == "__main__":
    main()
