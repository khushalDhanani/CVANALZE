import os
import sys
import json
import logging
from datetime import datetime
from sqlalchemy import text

# Ensure backend path is in sys.path so we can import from app
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.core.database import SessionLocal

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("backfill_cvai_cache")

UPLOADS_RESULTS_DIR = os.path.join(backend_dir, "uploads", "results")

def backfill():
    if not SessionLocal:
        logger.error("Database connection not configured.")
        return

    if not os.path.exists(UPLOADS_RESULTS_DIR):
        logger.error(f"Directory not found: {UPLOADS_RESULTS_DIR}")
        return

    json_files = [f for f in os.listdir(UPLOADS_RESULTS_DIR) if f.endswith(".json")]
    logger.info(f"Found {len(json_files)} JSON files to process.")

    db = SessionLocal()
    try:
        upsert_cv_sql = text("""
            MERGE INTO cvai.cv_documents AS target
            USING (SELECT :id AS id, :cv_hash AS cv_hash, :filename AS filename, :content_type AS content_type,
                          :page_count AS page_count, :is_scanned AS is_scanned, :ocr_applied AS ocr_applied,
                          :parser_used AS parser_used, :parser_version AS parser_version, :schema_version AS schema_version,
                          :parsed_at AS parsed_at, :created_at AS created_at, :updated_at AS updated_at,
                          :text AS text, :markdown AS markdown, :structured_doc AS structured_doc,
                          :quality_metrics AS quality_metrics, :stage_metrics AS stage_metrics) AS source
            ON target.id = source.id
            WHEN MATCHED THEN
                UPDATE SET
                    cv_hash = source.cv_hash, filename = source.filename, content_type = source.content_type,
                    page_count = source.page_count, is_scanned = source.is_scanned, ocr_applied = source.ocr_applied,
                    parser_used = source.parser_used, parser_version = source.parser_version, schema_version = source.schema_version,
                    parsed_at = source.parsed_at, updated_at = source.updated_at, text = source.text,
                    markdown = source.markdown, structured_doc = source.structured_doc, quality_metrics = source.quality_metrics,
                    stage_metrics = source.stage_metrics
            WHEN NOT MATCHED THEN
                INSERT (id, cv_hash, filename, content_type, page_count, is_scanned, ocr_applied, parser_used,
                        parser_version, schema_version, parsed_at, created_at, updated_at, text, markdown,
                        structured_doc, quality_metrics, stage_metrics)
                VALUES (source.id, source.cv_hash, source.filename, source.content_type, source.page_count, source.is_scanned, source.ocr_applied, source.parser_used,
                        source.parser_version, source.schema_version, source.parsed_at, source.created_at, source.updated_at, source.text, source.markdown,
                        source.structured_doc, source.quality_metrics, source.stage_metrics);
        """)

        upsert_candidate_sql = text("""
            MERGE INTO cvai.candidates AS target
            USING (SELECT :id AS id, :cv_document_id AS cv_document_id, :dynamic_profile AS dynamic_profile,
                          :resume_json AS resume_json, :match_analysis AS match_analysis, :created_at AS created_at) AS source
            ON target.id = source.id
            WHEN MATCHED THEN
                UPDATE SET
                    cv_document_id = source.cv_document_id, dynamic_profile = source.dynamic_profile,
                    resume_json = source.resume_json, match_analysis = source.match_analysis
            WHEN NOT MATCHED THEN
                INSERT (id, cv_document_id, dynamic_profile, resume_json, match_analysis, created_at)
                VALUES (source.id, source.cv_document_id, source.dynamic_profile, source.resume_json, source.match_analysis, source.created_at);
        """)

        processed_count = 0
        for filename in json_files:
            file_path = os.path.join(UPLOADS_RESULTS_DIR, filename)
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)

                # Parse dates (fallback to current time if missing/invalid)
                def parse_date(date_str):
                    if not date_str:
                        return datetime.utcnow()
                    try:
                        return datetime.fromisoformat(date_str.replace("Z", "+00:00")).replace(tzinfo=None)
                    except Exception:
                        return datetime.utcnow()

                parsed_at = parse_date(data.get("parsed_at"))
                created_at = parse_date(data.get("created_at"))
                updated_at = parse_date(data.get("updated_at"))

                # Ensure defaults for boolean/numeric
                is_scanned = bool(data.get("is_scanned", False))
                ocr_applied = bool(data.get("ocr_applied", False))
                page_count = int(data.get("page_count") or 1)

                cv_doc_params = {
                    "id": data.get("cv_id") or data.get("id") or filename.replace(".json", ""),
                    "cv_hash": data.get("cv_hash") or filename.replace(".json", "").replace("cv_", ""),
                    "filename": data.get("filename"),
                    "content_type": data.get("content_type"),
                    "page_count": page_count,
                    "is_scanned": is_scanned,
                    "ocr_applied": ocr_applied,
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
                    "stage_metrics": json.dumps(data.get("stage_metrics")) if data.get("stage_metrics") else None
                }

                # Candidates table backfill if dynamic_profile/resume_json present
                candidate_id = data.get("candidate_id") or f"cand_{cv_doc_params['id']}"
                candidate_params = {
                    "id": candidate_id,
                    "cv_document_id": cv_doc_params["id"],
                    "dynamic_profile": json.dumps(data.get("dynamic_profile")) if data.get("dynamic_profile") else None,
                    "resume_json": json.dumps(data.get("resume_json")) if data.get("resume_json") else None,
                    "match_analysis": json.dumps(data.get("match_analysis")) if data.get("match_analysis") else None,
                    "created_at": created_at
                }

                db.execute(upsert_cv_sql, cv_doc_params)
                if any([candidate_params["dynamic_profile"], candidate_params["resume_json"], candidate_params["match_analysis"]]):
                    db.execute(upsert_candidate_sql, candidate_params)

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
