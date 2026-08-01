from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import settings

# Create the SQLAlchemy engine if DB_URL is configured
if settings.DB_URL:
    # mssql+pyodbc connection string might require some additional arguments depending on the driver
    engine = create_engine(
        settings.DB_URL,
        pool_pre_ping=True,  # Enable connection health checks
        pool_size=10,
        max_overflow=20,
        fast_executemany=True # Optimization for pyodbc
    )
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
else:
    engine = None
    SessionLocal = None

# Create the PG engine
if settings.PG_DB_URL:
    pg_engine = create_engine(
        settings.PG_DB_URL,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20
    )
    pg_SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=pg_engine)
else:
    pg_engine = None
    pg_SessionLocal = None

Base = declarative_base()
pg_Base = declarative_base()

def get_db():
    """
    Dependency to yield a database session for FastAPI endpoints. (MSSQL)
    """
    if SessionLocal is None:
        raise RuntimeError("Database connection is not configured. Please check your .env settings.")
    
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_pg_db():
    """
    Dependency to yield a database session for Postgres.
    """
    if pg_SessionLocal is None:
        raise RuntimeError("PG Database connection is not configured.")
    
    db = pg_SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    if engine is not None:
        try:
            from app.models.config import SystemConfig
            SystemConfig.__table__.create(engine, checkfirst=True)
        except Exception as exc:
            import logging
            logging.getLogger(__name__).warning(f"Could not initialize DB tables: {exc}")
    
    if pg_engine is not None:
        try:
            # We need to run CREATE EXTENSION IF NOT EXISTS vector
            with pg_engine.connect() as conn:
                conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
                conn.commit()
            
            pg_Base.metadata.create_all(bind=pg_engine)
        except Exception as exc:
            import logging
            logging.getLogger(__name__).warning(f"Could not initialize PG tables: {exc}")
