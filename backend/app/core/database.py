from __future__ import annotations
from sqlalchemy import create_engine, text, event
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import settings

# Create the SQLAlchemy engine for MSSQL Read-Only
if settings.MSSQL_READ_ONLY_URL:
    mssql_read_engine = create_engine(
        settings.MSSQL_READ_ONLY_URL,
        pool_pre_ping=True,  # Enable connection health checks
        pool_size=10,
        max_overflow=20,
        fast_executemany=True,  # Optimization for pyodbc
    )
    MssqlReadSession = sessionmaker(autocommit=False, autoflush=False, bind=mssql_read_engine)
else:
    mssql_read_engine = None
    MssqlReadSession = None

# Create the PG engine for App Data
if settings.POSTGRES_APP_URL:
    postgres_app_engine = create_engine(settings.POSTGRES_APP_URL, pool_pre_ping=True, pool_size=10, max_overflow=20)
    PostgresAppSession = sessionmaker(autocommit=False, autoflush=False, bind=postgres_app_engine)
else:
    postgres_app_engine = None
    PostgresAppSession = None

MssqlReadBase = declarative_base()
PostgresAppBase = declarative_base()

@event.listens_for(MssqlReadBase.metadata, "before_create")
def block_mssql_create(target, connection, **kw):
    raise RuntimeError("MSSQL database is read-only. DDL operations are permanently disabled.")

@event.listens_for(MssqlReadBase.metadata, "before_drop")
def block_mssql_drop(target, connection, **kw):
    raise RuntimeError("MSSQL database is read-only. DDL operations are permanently disabled.")

if MssqlReadSession:
    @event.listens_for(MssqlReadSession, "before_flush")
    def block_mssql_flush(session, flush_context, instances):
        if session.new or session.dirty or session.deleted:
            raise RuntimeError("MSSQL database is read-only. Writes are permanently disabled.")


def get_mssql_read_db():
    """
    Dependency to yield a read-only database session for enterprise source data.
    """
    if MssqlReadSession is None:
        raise RuntimeError("MSSQL Read-Only connection is not configured. Please check your .env settings.")

    db = MssqlReadSession()
    try:
        yield db
    finally:
        db.close()


def get_postgres_app_db():
    """
    Dependency to yield a read/write database session for CV Analyzer-owned data.
    """
    if PostgresAppSession is None:
        raise RuntimeError("Postgres App Data connection is not configured.")

    db = PostgresAppSession()
    try:
        yield db
    finally:
        db.close()


def init_db():
    if postgres_app_engine is not None:
        try:
            # We need to run CREATE EXTENSION IF NOT EXISTS vector
            with postgres_app_engine.connect() as conn:
                conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
                conn.commit()

            PostgresAppBase.metadata.create_all(bind=postgres_app_engine)
        except Exception as exc:
            import logging

            logging.getLogger(__name__).warning(f"Could not initialize PG tables: {exc}")


def run_auto_migrations():
    """
    Executes pending database migrations in explicitly enabled non-production environments.
    """
    if not settings.AUTO_MIGRATE:
        return

    import logging

    logger = logging.getLogger(__name__)
    if settings.IS_PRODUCTION:
        logger.warning("[AUTO_MIGRATE] Ignored in production; use scripts/run_migrations.py explicitly.")
        return

    try:
        from scripts.run_migrations import run_migrations

        if settings.POSTGRES_APP_URL:
            try:
                logger.info("[AUTO_MIGRATE] Checking pending PostgreSQL schema migrations...")
                run_migrations("postgres", settings.POSTGRES_APP_URL, dry_run=False)
            except Exception as exc:
                logger.warning(f"[AUTO_MIGRATE] PostgreSQL auto-migration warning: {exc}")
    except Exception as exc:
        logger.warning(f"[AUTO_MIGRATE] Could not execute auto-migrations: {exc}")
