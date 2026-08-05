import json
import logging
import os
import sys
from datetime import datetime

from sqlalchemy import text

backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.core.database import PostgresAppSession

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("backfill_cvai_cache")

UPLOADS_RESULTS_DIR = os.path.join(backend_dir, "uploads", "results")


def backfill():
    if not PostgresAppSession:
        logger.error("Database connection not configured.")
        return

    if not os.path.exists(UPLOADS_RESULTS_DIR):
        logger.error(f"Directory not found: {UPLOADS_RESULTS_DIR}")
        return

    json_files = [f for f in os.listdir(UPLOADS_RESULTS_DIR) if f.endswith(".json")]
    logger.info(f"Found {len(json_files)} JSON files to process.")

    db = PostgresAppSession()
    try:
        # cv_documents
        upsert_cv_sql = text("""
            MERGE INTO cvai.cv_documents AS target
            USING (SELECT :id AS id, :tenant_id AS tenant_id, :cv_hash AS cv_hash, :filename AS filename, :content_type AS content_type,
                          :page_count AS page_count, :is_scanned AS is_scanned, :ocr_applied AS ocr_applied,
                          :parser_used AS parser_used, :parser_version AS parser_version, :schema_version AS schema_version,
                          :parsed_at AS parsed_at, :created_at AS created_at, :updated_at AS updated_at,
                          :text AS text, :markdown AS markdown, :structured_doc AS structured_doc,
                          :quality_metrics AS quality_metrics, :stage_metrics AS stage_metrics) AS source
            ON target.id = source.id
            WHEN MATCHED THEN
                UPDATE SET
                    tenant_id = source.tenant_id, cv_hash = source.cv_hash, filename = source.filename, content_type = source.content_type,
                    page_count = source.page_count, is_scanned = source.is_scanned, ocr_applied = source.ocr_applied,
                    parser_used = source.parser_used, parser_version = source.parser_version, schema_version = source.schema_version,
                    parsed_at = source.parsed_at, updated_at = source.updated_at, text = source.text,
                    markdown = source.markdown, structured_doc = source.structured_doc, quality_metrics = source.quality_metrics,
                    stage_metrics = source.stage_metrics
            WHEN NOT MATCHED THEN
                INSERT (id, tenant_id, cv_hash, filename, content_type, page_count, is_scanned, ocr_applied, parser_used,
                        parser_version, schema_version, parsed_at, created_at, updated_at, text, markdown,
                        structured_doc, quality_metrics, stage_metrics)
                VALUES (source.id, source.tenant_id, source.cv_hash, source.filename, source.content_type, source.page_count, source.is_scanned, source.ocr_applied, source.parser_used,
                        source.parser_version, source.schema_version, source.parsed_at, source.created_at, source.updated_at, source.text, source.markdown,
                        source.structured_doc, source.quality_metrics, source.stage_metrics);
        """)

        # candidates
        upsert_candidate_sql = text("""
            MERGE INTO cvai.candidates AS target
            USING (SELECT :id AS id, :tenant_id AS tenant_id, :cv_document_id AS cv_document_id, :raw_skills_json AS raw_skills_json,
                          :raw_education_json AS raw_education_json, :raw_experience_json AS raw_experience_json, :raw_profile_json AS raw_profile_json,
                          :schema_version AS schema_version, :created_at AS created_at, :updated_at AS updated_at) AS source
            ON target.id = source.id
            WHEN MATCHED THEN
                UPDATE SET
                    tenant_id = source.tenant_id, cv_document_id = source.cv_document_id, raw_skills_json = source.raw_skills_json,
                    raw_education_json = source.raw_education_json, raw_experience_json = source.raw_experience_json, raw_profile_json = source.raw_profile_json,
                    schema_version = source.schema_version, updated_at = source.updated_at
            WHEN NOT MATCHED THEN
                INSERT (id, tenant_id, cv_document_id, raw_skills_json, raw_education_json, raw_experience_json, raw_profile_json, schema_version, created_at, updated_at)
                VALUES (source.id, source.tenant_id, source.cv_document_id, source.raw_skills_json, source.raw_education_json, source.raw_experience_json, source.raw_profile_json, source.schema_version, source.created_at, source.updated_at);
        """)

        # match_results
        upsert_match_sql = text("""
            MERGE INTO cvai.match_results AS target
            USING (SELECT :id AS id, :tenant_id AS tenant_id, :candidate_id AS candidate_id, :vacancy_id AS vacancy_id,
                          :vacancy_title AS vacancy_title, :department_name AS department_name, :scoring_engine_version AS scoring_engine_version,
                          :rule_config_version AS rule_config_version, :overall_score AS overall_score, :component_scores_json AS component_scores_json,
                          :created_at AS created_at, :updated_at AS updated_at) AS source
            ON target.id = source.id
            WHEN MATCHED THEN
                UPDATE SET
                    tenant_id = source.tenant_id, candidate_id = source.candidate_id, vacancy_id = source.vacancy_id,
                    vacancy_title = source.vacancy_title, department_name = source.department_name, scoring_engine_version = source.scoring_engine_version,
                    rule_config_version = source.rule_config_version, overall_score = source.overall_score, component_scores_json = source.component_scores_json,
                    updated_at = source.updated_at
            WHEN NOT MATCHED THEN
                INSERT (id, tenant_id, candidate_id, vacancy_id, vacancy_title, department_name, scoring_engine_version, rule_config_version, overall_score, component_scores_json, created_at, updated_at)
                VALUES (source.id, source.tenant_id, source.candidate_id, source.vacancy_id, source.vacancy_title, source.department_name, source.scoring_engine_version, source.rule_config_version, source.overall_score, source.component_scores_json, source.created_at, source.updated_at);
        """)

        processed_count = 0
        for filename in json_files:
            file_path = os.path.join(UPLOADS_RESULTS_DIR, filename)
            try:
                with open(file_path, encoding="utf-8") as f:
                    data = json.load(f)

                def parse_date(date_str):
                    if not date_str:
                        return datetime.utcnow()
                    try:
                        return datetime.fromisoformat(date_str).replace(tzinfo=None)
                    except Exception:
                        return datetime.utcnow()

                parsed_at = parse_date(data.get("parsed_at"))
                created_at = parse_date(data.get("created_at"))
                updated_at = parse_date(data.get("updated_at"))
                tenant_id = data.get("tenant_id")  # Nullable

                cv_doc_params = {
                    "id": data.get("cv_id") or data.get("id") or filename.replace(".json", ""),
                    "tenant_id": tenant_id,
                    "cv_hash": data.get("cv_hash") or filename.replace(".json", "").replace("cv_", ""),
                    "filename": data.get("filename"),
                    "content_type": data.get("content_type"),
                    "page_count": int(data.get("page_count") or 1),
                    "is_scanned": bool(data.get("is_scanned", False)),
                    "ocr_applied": bool(data.get("ocr_applied", False)),
                    "parser_used": data.get("parser_used") or data.get("parser_version"),
                    "parser_version": data.get("parser_version"),
                    "schema_version": data.get("schema_version"),
                    "parsed_at": parsed_at,
                    "created_at": created_at,
                    "updated_at": updated_at,
                    "text": data.get("text"),
                    "markdown": data.get("markdown"),
                    "structured_doc": json.dumps(data.get("structured_doc")) if data.get("structured_doc") else None,
                    "quality_metrics": json.dumps(data.get("quality_metrics")) if data.get("quality_metrics") else None,
                    "stage_metrics": json.dumps(data.get("stage_metrics")) if data.get("stage_metrics") else None,
                }

                # Extract profile data (which contains skills, experience, etc.)
                dyn_profile = data.get("dynamic_profile") or data.get("resume_json") or {}

                candidate_id = data.get("candidate_id") or f"cand_{cv_doc_params['id']}"
                candidate_params = {
                    "id": candidate_id,
                    "tenant_id": tenant_id,
                    "cv_document_id": cv_doc_params["id"],
                    "raw_skills_json": json.dumps(dyn_profile.get("skills")) if dyn_profile.get("skills") else None,
                    "raw_education_json": json.dumps(dyn_profile.get("education")) if dyn_profile.get("education") else None,
                    "raw_experience_json": json.dumps(dyn_profile.get("experience")) if dyn_profile.get("experience") else None,
                    "raw_profile_json": json.dumps(dyn_profile) if dyn_profile else None,
                    "schema_version": cv_doc_params["schema_version"],
                    "created_at": created_at,
                    "updated_at": updated_at,
                }

                db.execute(upsert_cv_sql, cv_doc_params)
                db.execute(upsert_candidate_sql, candidate_params)

                # Process match analysis if available
                match_analysis = data.get("match_analysis")
                if match_analysis:
                    match_id = match_analysis.get("id") or f"match_{candidate_id}"

                    match_params = {
                        "id": match_id,
                        "tenant_id": tenant_id,
                        "candidate_id": candidate_id,
                        "vacancy_id": str(match_analysis.get("vacancy_id", "")),
                        "vacancy_title": match_analysis.get("vacancy_title"),
                        "department_name": match_analysis.get("department_name"),
                        "scoring_engine_version": match_analysis.get("scoring_engine_version"),
                        "rule_config_version": match_analysis.get("rule_config_version"),
                        "overall_score": float(match_analysis.get("overall_score", 0.0)),
                        "component_scores_json": json.dumps(match_analysis.get("component_scores")) if match_analysis.get("component_scores") else None,
                        "created_at": created_at,
                        "updated_at": updated_at,
                    }
                    db.execute(upsert_match_sql, match_params)

                processed_count += 1

            except Exception as e:
                logger.error(f"Error processing file {filename}: {e}", exc_info=True)

        db.commit()
        logger.info(f"Successfully backfilled {processed_count} files.")

    except Exception as e:
        db.rollback()
        logger.error(f"Database error during backfill: {e}", exc_info=True)
    finally:
        db.close()


if __name__ == "__main__":
    backfill()
