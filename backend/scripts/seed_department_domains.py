"""Seed DepartmentDomainMaster table from department_domains_seed.json."""
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.database import PostgresAppSession, init_db
from app.models.domain import DepartmentDomainMaster

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("seed_department_domains")


def seed():
    logger.info("Initializing DB tables if not existing...")
    init_db()

    if PostgresAppSession is None:
        logger.error("PostgresAppSession is None. Cannot seed database.")
        return

    seed_path = Path(__file__).resolve().parent.parent / "app" / "data" / "department_domains_seed.json"
    if not seed_path.exists():
        logger.error(f"Cannot find {seed_path}")
        return

    with open(seed_path) as f:
        data = json.load(f)

    domains = data.get("domains", [])
    logger.info(f"Found {len(domains)} domain entries to seed.")

    db = PostgresAppSession()
    try:
        created = 0
        updated = 0
        for d in domains:
            dept_id = d.get("department_id")
            dept_name = d.get("department_name")
            domain_name = d.get("domain_name")
            keywords_json = d.get("keywords", [])
            default_roles_json = d.get("default_roles", [])
            priority = d.get("priority", 0)
            is_active = d.get("is_active", True)

            existing = db.query(DepartmentDomainMaster).filter_by(DepartmentId=dept_id).first()
            if existing:
                record = existing
                updated += 1
            else:
                record = DepartmentDomainMaster(DepartmentId=dept_id)
                db.add(record)
                created += 1

            record.DepartmentNameSnapshot = dept_name
            record.DomainName = domain_name
            record.Keywords = keywords_json
            record.DefaultRoles = default_roles_json
            record.Priority = priority
            record.IsActive = is_active

        db.commit()
        logger.info(f"DepartmentDomainMaster seeded: {created} created, {updated} updated, {created + updated} total.")

        # Verify
        count = db.query(DepartmentDomainMaster).filter_by(IsActive=True).count()
        logger.info(f"Verification: {count} active rows in DepartmentDomainMaster.")

    except Exception as e:
        db.rollback()
        logger.error(f"Error during seeding: {e}", exc_info=True)
    finally:
        db.close()


if __name__ == "__main__":
    seed()
