import pytest
from sqlalchemy.schema import CreateTable
from sqlalchemy import create_mock_engine

from app.core.database import MssqlReadBase, PostgresAppBase
# Import models to ensure they are registered with their respective bases
import app.models.org as org_models
import app.models.recruit as recruit_models
import app.models.domain as domain_models
import app.models.config as config_models
import app.models.taxonomy as taxonomy_models
import app.models.rules as rules_models


def test_mssql_read_base_contains_only_read_models():
    """Verify that MssqlReadBase only contains the read-only enterprise models."""
    tables = MssqlReadBase.metadata.tables.keys()
    assert "OrgDepartmentMst" in tables
    assert "RecruitCandidateMst" in tables
    
    # Ensure CV Analyzer owned tables are NOT in MssqlReadBase
    assert "DepartmentDomainMaster" not in tables
    assert "system_config" not in tables
    assert "cvai.rule_config_profiles" not in tables


def test_postgres_app_base_contains_only_app_models():
    """Verify that PostgresAppBase contains the CV Analyzer application data models."""
    tables = PostgresAppBase.metadata.tables.keys()
    
    # Ensure CV Analyzer owned tables ARE in PostgresAppBase
    assert "DepartmentDomainMaster" in tables
    assert "system_config" in tables
    assert "cvai.rule_config_profiles" in tables
    
    # Ensure enterprise tables are NOT in PostgresAppBase
    assert "OrgDepartmentMst" not in tables
    assert "RecruitCandidateMst" not in tables


def test_mssql_ddl_is_permanently_disabled():
    """Verify that MssqlReadBase blocks all DDL operations."""
    def dump_sql(sql, *multiparams, **params):
        pass

    engine = create_mock_engine('mssql+pyodbc://', executor=dump_sql)
    
    with pytest.raises(RuntimeError, match="read-only"):
        MssqlReadBase.metadata.create_all(engine)
        
    with pytest.raises(RuntimeError, match="read-only"):
        MssqlReadBase.metadata.drop_all(engine)


def test_mssql_writes_are_permanently_disabled():
    """Verify that MssqlReadSession blocks all DML operations."""
    from app.core.database import MssqlReadSession
    if not MssqlReadSession:
        pytest.skip("MSSQL read session not configured")
        
    session = MssqlReadSession()
    # Create a dummy object to trigger flush event
    candidate = org_models.OrgDepartmentMst(DepartmentName="Test")
    session.add(candidate)
    
    with pytest.raises(RuntimeError, match="read-only"):
        session.flush()
        
    session.rollback()
    session.close()
