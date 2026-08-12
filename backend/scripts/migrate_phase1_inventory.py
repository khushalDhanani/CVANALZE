import json
import logging
import sys
from pathlib import Path

# Add backend directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.database import PostgresAppSession, init_db
from app.models.rules import RuleConfigProfile
from app.models.domain import DepartmentDomainMaster

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("migrate_phase1_inventory")

def migrate():
    logger.info("Initializing DB tables if not existing...")
    init_db()

    if PostgresAppSession is None:
        logger.error("PostgresAppSession is None. Cannot seed database.")
        return
    
    db = PostgresAppSession()
    try:
        # 1. Process rule_config.json
        rule_config_path = Path(__file__).resolve().parent.parent / "app" / "core" / "rule_config.json"
        if not rule_config_path.exists():
            logger.error(f"Cannot find {rule_config_path}")
            return
            
        with open(rule_config_path) as f:
            rule_data = json.load(f)
            
        version_tag = rule_data.get("version", "1.1.0")
        description = rule_data.get("description", "Migrated from static JSON file")
        
        # Check if this draft already exists
        existing_profile = db.query(RuleConfigProfile).filter_by(version_tag=version_tag).first()
        if existing_profile:
            logger.info(f"RuleConfigProfile with version {version_tag} already exists. Updating...")
            profile = existing_profile
        else:
            profile = RuleConfigProfile(version_tag=version_tag)
            db.add(profile)
            
        profile.description = description
        profile.global_confidence_tiers_json = json.dumps(rule_data.get("global_confidence_tiers", {}))
        profile.fields_config_json = json.dumps(rule_data.get("fields", {}))
        profile.scoring_rules_json = json.dumps(rule_data.get("scoring", {}))
        profile.status = "DRAFT"
        profile.is_active = False
        profile.created_by = "system_migration"
        
        logger.info(f"Draft RuleConfigProfile created/updated for version {version_tag}")

        # 2. Process department_domains_seed.json
        dept_seed_path = Path(__file__).resolve().parent.parent / "app" / "data" / "department_domains_seed.json"
        if not dept_seed_path.exists():
            logger.error(f"Cannot find {dept_seed_path}")
            return
            
        with open(dept_seed_path) as f:
            dept_data = json.load(f)
            
        domains = dept_data.get("domains", [])
        
        for d in domains:
            dept_id = d.get("department_id")
            dept_name = d.get("department_name")
            
            # Resolve the Healthcare record without a department ID
            if dept_name == "Healthcare & Clinical" and dept_id is None:
                dept_id = 24
                logger.info("Assigned department_id 24 to 'Healthcare & Clinical'")
                
            # Remove personal names from department taxonomy
            if "Ramesh Maurya" in str(dept_name):
                dept_name = "Maintenance Team - 1"
                logger.info("Cleaned department name to 'Maintenance Team - 1'")
                
            domain_name = d.get("domain_name")
            # Note: industry_label is inherently dropped because we only use domain_name
            
            keywords_json = json.dumps(d.get("keywords", []))
            default_roles_json = json.dumps(d.get("default_roles", []))
            priority = d.get("priority", 0)
            is_active = d.get("is_active", True)
            
            existing_dept = db.query(DepartmentDomainMaster).filter_by(DepartmentId=dept_id).first()
            if existing_dept:
                logger.info(f"Updating DepartmentDomainMaster for dept_id {dept_id}")
                dept_record = existing_dept
            else:
                dept_record = DepartmentDomainMaster(DepartmentId=dept_id)
                db.add(dept_record)
                
            dept_record.DepartmentNameSnapshot = dept_name
            dept_record.DomainName = domain_name
            dept_record.Keywords = keywords_json
            dept_record.DefaultRoles = default_roles_json
            dept_record.Priority = priority
            dept_record.IsActive = is_active
            
        db.commit()
        logger.info("Migration completed successfully!")
        
        # 3. Generate versioned SQL draft
        sql_path = Path(__file__).resolve().parent / "migrations" / "mssql" / "008_phase1_inventory_seed.sql"
        sql_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(sql_path, "w") as f:
            f.write("-- Migration Script: Phase 1 Inventory Seed\n")
            f.write("-- Generated automatically by migrate_phase1_inventory.py\n\n")
            
            # RuleConfigProfile
            desc_sql = profile.description.replace("'", "''")
            gct_sql = profile.global_confidence_tiers_json.replace("'", "''")
            fc_sql = profile.fields_config_json.replace("'", "''")
            sr_sql = profile.scoring_rules_json.replace("'", "''")
            
            f.write("INSERT INTO cvai.rule_config_profiles (version_tag, description, global_confidence_tiers_json, fields_config_json, scoring_rules_json, status, is_active, created_by, created_at)\n")
            f.write(f"VALUES ('{profile.version_tag}', '{desc_sql}', '{gct_sql}', '{fc_sql}', '{sr_sql}', 'DRAFT', 0, 'system_migration', GETUTCDATE());\n\n")
            
            # DepartmentDomainMaster
            for d in domains:
                dept_id = d.get("department_id")
                dept_name = d.get("department_name")
                if dept_name == "Healthcare & Clinical" and dept_id is None:
                    dept_id = 24
                
                domain_name = d.get("domain_name").replace("'", "''")
                kw_sql = json.dumps(d.get("keywords", [])).replace("'", "''")
                dr_sql = json.dumps(d.get("default_roles", [])).replace("'", "''")
                pri = d.get("priority", 0)
                active = 1 if d.get("is_active", True) else 0
                
                f.write("IF NOT EXISTS (SELECT 1 FROM cvai.DepartmentDomainMaster WHERE DepartmentId = {})\n".format(dept_id))
                f.write("BEGIN\n")
                f.write("    INSERT INTO cvai.DepartmentDomainMaster (DepartmentId, DomainName, Keywords, DefaultRoles, Priority, IsActive, CreatedOn, ModifiedOn)\n")
                f.write(f"    VALUES ({dept_id}, '{domain_name}', '{kw_sql}', '{dr_sql}', {pri}, {active}, GETUTCDATE(), GETUTCDATE());\n")
                f.write("END\n")
                f.write("ELSE\n")
                f.write("BEGIN\n")
                f.write(f"    UPDATE cvai.DepartmentDomainMaster SET DomainName = '{domain_name}', Keywords = '{kw_sql}', DefaultRoles = '{dr_sql}', Priority = {pri}, IsActive = {active}, ModifiedOn = GETUTCDATE() WHERE DepartmentId = {dept_id};\n")
                f.write("END\n\n")
                
        logger.info(f"Versioned database draft SQL generated at {sql_path}")
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error during migration: {e}", exc_info=True)
    finally:
        db.close()

if __name__ == "__main__":
    migrate()
