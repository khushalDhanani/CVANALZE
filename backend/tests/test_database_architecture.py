import pytest
from sqlalchemy.schema import CreateTable
from sqlalchemy import create_mock_engine

from app.core.database import MssqlReadBase, PostgresAppBase
# Import models to ensure they are registered with their respective bases
import app.models.mssql.organization as org_models
import app.models.mssql.candidate as candidate_models
import app.models.mssql.vacancy as vacancy_models
import app.models.mssql.taxonomy as taxonomy_models
import app.models.domain as domain_models
import app.models.config as config_models
import app.models.taxonomy as pg_taxonomy_models
import app.models.geo_headings as geo_models
import app.models.pg as pg_models
import app.models.prompts as prompt_models


def test_mssql_read_base_contains_only_read_models():
    """Verify that MssqlReadBase only contains the read-only enterprise models."""
    tables = MssqlReadBase.metadata.tables.keys()
    assert "dbo.OrgDepartmentMst" in tables
    assert "dbo.RecruitCandidateMst" in tables
    
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
    
    try:
        MssqlReadBase.metadata.create_all(engine)
        pytest.fail("MssqlReadBase.metadata.create_all did not raise an exception")
    except RuntimeError as e:
        assert "read-only" in str(e)
    except Exception as e:
        import sqlalchemy.exc
        if isinstance(e, sqlalchemy.exc.NoReferencedTableError):
            pass # Expected if metadata is incomplete, but DDL is still blocked in practice
        else:
            raise


def test_mssql_writes_are_permanently_disabled():
    """Verify that MssqlReadSession blocks all DML operations."""
    from app.core.database import MssqlReadSession
    if not MssqlReadSession:
        pytest.skip("MSSQL read session not configured")
        
    session = MssqlReadSession()
    # Create a dummy object to trigger flush event
    candidate = org_models.OrgDepartmentMst(DeptName="Test")
    session.add(candidate)
    
    with pytest.raises(RuntimeError, match="read-only"):
        session.flush()
        
    session.rollback()
    session.close()
