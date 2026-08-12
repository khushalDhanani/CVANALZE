import pytest
from sqlalchemy import create_engine, Column, Integer, String, text
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.database import MssqlReadBase
from scripts.run_migrations import run_migrations, get_migration_files, run_status, run_rollback, ensure_migrations_table
from app.core.database import block_mssql_create, block_mssql_drop, block_mssql_flush, block_mssql_raw_writes
from sqlalchemy import event

@pytest.fixture
def mssql_mock_engine():
    engine = create_engine("sqlite:///:memory:")
    
    event.listen(engine, "before_cursor_execute", block_mssql_raw_writes)
    
    TestBase = declarative_base()
    event.listen(TestBase.metadata, "before_create", block_mssql_create)
    event.listen(TestBase.metadata, "before_drop", block_mssql_drop)
    
    Session = sessionmaker(bind=engine)
    event.listen(Session, "before_flush", block_mssql_flush)
    
    class MockModel(TestBase):
        __tablename__ = "mock_table"
        id = Column(Integer, primary_key=True)
        name = Column(String)
        
    return engine, Session, TestBase, MockModel


def test_orm_insert_blocked(mssql_mock_engine):
    engine, Session, TestBase, MockModel = mssql_mock_engine
    
    session = Session()
    new_record = MockModel(id=1, name="test")
    session.add(new_record)
    
    with pytest.raises(RuntimeError, match="MSSQL database is read-only. Writes are permanently disabled."):
        session.commit()


def test_orm_update_blocked(mssql_mock_engine):
    engine, Session, TestBase, MockModel = mssql_mock_engine
    
    # We must insert data bypassing the session/ORM blocks, and without triggering the raw writes block
    # Since we added the raw writes block to `engine`, we should temporarily un-listen to insert
    event.remove(engine, "before_cursor_execute", block_mssql_raw_writes)
    with engine.connect() as conn:
        conn.execute(text("CREATE TABLE mock_table (id INTEGER PRIMARY KEY, name VARCHAR)"))
        conn.execute(text("INSERT INTO mock_table (id, name) VALUES (1, 'initial')"))
        conn.commit()
    event.listen(engine, "before_cursor_execute", block_mssql_raw_writes)

    session = Session()
    record = session.query(MockModel).filter_by(id=1).first()
    record.name = "updated"
    
    with pytest.raises(RuntimeError, match="MSSQL database is read-only. Writes are permanently disabled."):
        session.commit()


def test_orm_delete_blocked(mssql_mock_engine):
    engine, Session, TestBase, MockModel = mssql_mock_engine
    
    event.remove(engine, "before_cursor_execute", block_mssql_raw_writes)
    with engine.connect() as conn:
        conn.execute(text("CREATE TABLE mock_table (id INTEGER PRIMARY KEY, name VARCHAR)"))
        conn.execute(text("INSERT INTO mock_table (id, name) VALUES (1, 'initial')"))
        conn.commit()
    event.listen(engine, "before_cursor_execute", block_mssql_raw_writes)

    session = Session()
    record = session.query(MockModel).filter_by(id=1).first()
    session.delete(record)
    
    with pytest.raises(RuntimeError, match="MSSQL database is read-only. Writes are permanently disabled."):
        session.commit()


def test_raw_update_blocked(mssql_mock_engine):
    engine, _, _, _ = mssql_mock_engine
    with pytest.raises(RuntimeError, match="Raw DML/DDL statements are permanently disabled."):
        with engine.connect() as conn:
            conn.execute(text("UPDATE mock_table SET name='test'"))


def test_raw_delete_blocked(mssql_mock_engine):
    engine, _, _, _ = mssql_mock_engine
    with pytest.raises(RuntimeError, match="Raw DML/DDL statements are permanently disabled."):
        with engine.connect() as conn:
            conn.execute(text("   DeLetE FROM mock_table"))


def test_raw_create_table_blocked(mssql_mock_engine):
    engine, _, _, _ = mssql_mock_engine
    with pytest.raises(RuntimeError, match="Raw DML/DDL statements are permanently disabled."):
        with engine.connect() as conn:
            conn.execute(text("CREATE TABLE test (id int)"))


def test_raw_insert_blocked(mssql_mock_engine):
    engine, _, _, _ = mssql_mock_engine
    with pytest.raises(RuntimeError, match="Raw DML/DDL statements are permanently disabled."):
        with engine.connect() as conn:
            conn.execute(text("INSERT INTO mock_table VALUES(1)"))
            
            
def test_direct_migration_runner_mssql_rejected():
    with pytest.raises(ValueError, match="MSSQL dialect is permanently disabled."):
        run_migrations(db_url="dummy", dialect="mssql")
        
    with pytest.raises(ValueError, match="MSSQL dialect is permanently disabled."):
        get_migration_files(dialect="mssql")
        
    with pytest.raises(ValueError, match="MSSQL dialect is permanently disabled."):
        run_status(db_url="dummy", dialect="mssql")
        
    with pytest.raises(ValueError, match="MSSQL dialect is permanently disabled."):
        run_rollback(db_url="dummy", dialect="mssql")
        
    with pytest.raises(ValueError, match="MSSQL dialect is permanently disabled."):
        ensure_migrations_table(conn=None, dialect="mssql")
