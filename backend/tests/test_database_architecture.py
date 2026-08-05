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


def test_mssql_no_create_table_emitted():
    """Verify that MssqlReadBase cannot emit DDL that creates CV Analyzer tables."""
    # We use a mock engine to capture DDL strings
    def dump_sql(sql, *multiparams, **params):
        query = str(sql.compile(dialect=engine.dialect))
        # Ensure we are not creating CV Analyzer tables in MSSQL
        assert "DepartmentDomainMaster" not in query
        assert "system_config" not in query
        assert "cvai.rule_config_profiles" not in query

    engine = create_mock_engine('mssql+pyodbc://', executor=dump_sql)
    
    # This should not emit CREATE TABLE for PostgresAppBase tables
    MssqlReadBase.metadata.create_all(engine, checkfirst=False)
