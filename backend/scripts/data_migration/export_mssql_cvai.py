import os
import json
import logging
from datetime import datetime
from sqlalchemy import text
from app.core.database import MssqlReadSession

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("export_mssql_cvai")

EXPORT_DIR = os.path.join(os.path.dirname(__file__), "migration_exports")

def export_legacy_cv_results():
    """
    Exports legacy cvai.cv_results from MSSQL to a local JSON lines file.
    This is a READ-ONLY operation against the MSSQL cvai schema.
    """
    os.makedirs(EXPORT_DIR, exist_ok=True)
    export_file = os.path.join(EXPORT_DIR, f"mssql_cv_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl")
    
    query = """
    SELECT 
        id,
        candidate_id,
        cv_text,
        analysis_payload,
        created_at,
        updated_at
    FROM cvai.cv_results
    """
    
    total_records = 0
    with MssqlReadSession() as db:
        try:
            # We use text() to execute raw sql on the legacy schema
            results = db.execute(text(query)).fetchall()
            
            with open(export_file, "w", encoding="utf-8") as f:
                for row in results:
                    record = {
                        "id": row.id,
                        "candidate_id": row.candidate_id,
                        "cv_text": row.cv_text,
                        "analysis_payload": row.analysis_payload, # Assume this is a JSON string in MSSQL
                        "created_at": row.created_at.isoformat() if row.created_at else None,
                        "updated_at": row.updated_at.isoformat() if row.updated_at else None
                    }
                    f.write(json.dumps(record) + "\n")
                    total_records += 1
                    
            logger.info(f"Successfully exported {total_records} records to {export_file}")
            
        except Exception as e:
            logger.error(f"Failed to export data from MSSQL: {e}")
            
if __name__ == "__main__":
    logger.info("Starting MSSQL cvai data export...")
    export_legacy_cv_results()
