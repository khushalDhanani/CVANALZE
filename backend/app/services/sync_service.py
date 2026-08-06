import logging
from sqlalchemy import select
from app.core.database import MssqlReadSession, PostgresAppSession
from app.models.org import OrgDepartmentMst, OrgDesignationMst
from app.models.taxonomy import JobFamilyMaster, DesignationMaster, DomainMaster

logger = logging.getLogger("cv_analyzer")

class SyncService:
    @classmethod
    def sync_reference_data(cls) -> dict:
        """
        Synchronizes reference data (departments, designations) from MSSQL
        into the PostgreSQL taxonomy tables.
        """
        metrics = {"departments_synced": 0, "designations_synced": 0}
        
        if MssqlReadSession is None or PostgresAppSession is None:
            logger.warning("Database sessions not available for sync.")
            return metrics

        try:
            with MssqlReadSession() as mssql_db, PostgresAppSession() as pg_db:
                # 1. Ensure a default domain exists to attach families
                default_domain = pg_db.query(DomainMaster).filter(DomainMaster.domain_name == "Default System Domain").first()
                if not default_domain:
                    default_domain = DomainMaster(domain_code="DOM_DEFAULT", domain_name="Default System Domain", description="Default domain for synced families", is_active=True)
                    pg_db.add(default_domain)
                    pg_db.commit()
                    pg_db.refresh(default_domain)

                # 2. Sync Departments -> Job Families
                mssql_depts = mssql_db.query(OrgDepartmentMst).all()
                for dept in mssql_depts:
                    fam = pg_db.query(JobFamilyMaster).filter(
                        (JobFamilyMaster.mssql_department_id == dept.DeptID) |
                        (JobFamilyMaster.family_name == dept.DeptName)
                    ).first()
                    
                    if not fam:
                        fam = JobFamilyMaster(
                            domain_id=default_domain.domain_id,
                            family_code=f"FAM_SYNC_{dept.DeptID}",
                            family_name=dept.DeptName,
                            mssql_department_id=dept.DeptID,
                            is_active=dept.DeptIsActive
                        )
                        pg_db.add(fam)
                        metrics["departments_synced"] += 1
                    else:
                        fam.mssql_department_id = dept.DeptID
                        fam.family_name = dept.DeptName
                        fam.is_active = dept.DeptIsActive
                
                pg_db.commit()

                # 3. Sync Designations -> DesignationMaster
                mssql_desigs = mssql_db.query(OrgDesignationMst).all()
                for desig in mssql_desigs:
                    # Find corresponding family
                    fam = pg_db.query(JobFamilyMaster).filter(JobFamilyMaster.mssql_department_id == desig.DeptID).first()
                    if not fam:
                        continue
                        
                    desig_pg = pg_db.query(DesignationMaster).filter(
                        (DesignationMaster.mssql_designation_id == desig.DesigID) |
                        (DesignationMaster.designation_name == desig.DesigName)
                    ).first()
                    
                    if not desig_pg:
                        desig_pg = DesignationMaster(
                            family_id=fam.family_id,
                            designation_code=f"DESIG_SYNC_{desig.DesigID}",
                            designation_name=desig.DesigName,
                            mssql_designation_id=desig.DesigID,
                            is_active=desig.DesigIsActive
                        )
                        pg_db.add(desig_pg)
                        metrics["designations_synced"] += 1
                    else:
                        desig_pg.mssql_designation_id = desig.DesigID
                        desig_pg.designation_name = desig.DesigName
                        desig_pg.is_active = desig.DesigIsActive
                        desig_pg.family_id = fam.family_id
                
                pg_db.commit()
                
        except Exception as e:
            logger.error(f"Sync failed: {e}")
            
        return metrics
