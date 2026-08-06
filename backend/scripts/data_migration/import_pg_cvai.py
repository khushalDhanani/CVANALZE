import os
import json
import glob
import logging
from datetime import datetime
from app.core.database import PostgresAppSession
from app.models.cv import CVResult

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("import_pg_cvai")

EXPORT_DIR = os.path.join(os.path.dirname(__file__), "migration_exports")

def import_legacy_cv_results():
    """
    Imports legacy cvai.cv_results from a local JSON lines file into PostgreSQL.
    """
    export_files = glob.glob(os.path.join(EXPORT_DIR, "mssql_cv_results_*.jsonl"))
    if not export_files:
        logger.error("No export files found in migration_exports directory.")
        return

    # Pick the most recent export
    export_file = sorted(export_files)[-1]
    logger.info(f"Using export file: {export_file}")

    total_inserted = 0
    total_skipped = 0

    with PostgresAppSession() as db:
        with open(export_file, "r", encoding="utf-8") as f:
            for line in f:
                record = json.loads(line)
                candidate_id = record["candidate_id"]
                
                # Check if already exists in PG
                existing = db.query(CVResult).filter(CVResult.candidate_id == candidate_id).first()
                if existing:
                    total_skipped += 1
                    continue
                
                # Parse the payload which might be a JSON string from MSSQL
                payload = record["analysis_payload"]
                if isinstance(payload, str):
                    try:
                        payload = json.loads(payload)
                    except:
                        payload = {}

                new_cv = CVResult(
                    candidate_id=candidate_id,
                    payload=payload,
                    document_hash=f"legacy_migrated_{record['id']}", # Placeholder hash since MSSQL didn't have document_hash
                    created_at=datetime.fromisoformat(record["created_at"]) if record["created_at"] else datetime.utcnow(),
                    updated_at=datetime.fromisoformat(record["updated_at"]) if record["updated_at"] else datetime.utcnow()
                )
                
                db.add(new_cv)
                total_inserted += 1
                
                # Commit in batches of 100
                if total_inserted % 100 == 0:
                    db.commit()

        # Final commit
        db.commit()
        
    logger.info(f"Import complete. Inserted: {total_inserted}, Skipped (already exists): {total_skipped}")
    
    # Reconciliation Check
    with PostgresAppSession() as db:
        pg_count = db.query(CVResult).count()
        logger.info(f"Reconciliation: Total records in PostgreSQL CVResult table = {pg_count}")

if __name__ == "__main__":
    logger.info("Starting PostgreSQL cvai data import...")
    import_legacy_cv_results()
