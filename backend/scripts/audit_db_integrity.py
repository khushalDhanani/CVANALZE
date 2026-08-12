"""
DB Integrity Audit & Cleanup Script.

Deletes duplicate/orphan records:
  - cv_1760363690_0b75... (duplicate of cv_1760363690)
  - cv_gptsuifgr321345678o9p_c369... (duplicate of cv_gptsuifgr321345678o9p)
  - cv_document_cv_ut1765894215 (orphan with null data)
  - cv_we4567i876u5ye4twr (garbage: name="job.", no data)
"""
from __future__ import annotations

from app.core.database import PostgresAppSession
from app.core.logging import logger
from app.models.result import CVResult

DUPLICATE_KEYS = [
    "cv_1760363690_0b75586de3a3c2c86d821c115ddc0875e9e7bef3c20987be301e13b961259a25",
    "cv_gptsuifgr321345678o9p_c369770edae6dbd27123d2ea68cc20cf6329535022a48c74850c0e20df910fd6",
    "cv_document_cv_ut1765894215",
    "cv_we4567i876u5ye4twr",
]


def cleanup_duplicates() -> None:
    with PostgresAppSession() as session:
        for cv_key in DUPLICATE_KEYS:
            row = session.query(CVResult).filter(CVResult.cv_key == cv_key).first()
            if row:
                session.delete(row)
                logger.info(f"[DB_CLEANUP] Deleted duplicate/orphan record: {cv_key}")
            else:
                logger.info(f"[DB_CLEANUP] Record not found (already cleaned): {cv_key}")
        session.commit()

    # Verify
    with PostgresAppSession() as session:
        remaining = session.query(CVResult.cv_key).all()
        print(f"\n✅ Cleanup complete. {len(remaining)} records remaining:")
        for r in remaining:
            print(f"   {r.cv_key}")


if __name__ == "__main__":
    cleanup_duplicates()
