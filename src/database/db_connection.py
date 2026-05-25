import logging
from contextlib import contextmanager
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from config.settings import DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME

logger = logging.getLogger(__name__)

# Construct connection URI
# Support secure transaction poolers like Neon PgBouncer or AWS RDS out of the box
connection_args = {}
if "neon.tech" in DB_HOST or "amazonaws.com" in DB_HOST:
    # Ensure SSL is enforced for serverless cloud hosts
    DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}?sslmode=require"
    # Ensure pool parameters don't overlap PgBouncer transactions limit bounds
    connection_args = {
        "connect_timeout": 10,
        "application_name": "coindcx_intel_platform"
    }
else:
    DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# Setup engine with connection pool configurations
engine = create_engine(
    DATABASE_URL,
    connect_args=connection_args,
    pool_size=5,            # Lower pool limits to avoid overwhelming PgBouncer transaction bounds
    max_overflow=10,
    pool_recycle=1800,
    pool_pre_ping=True      # Proactively verifies connections before running queries
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

@contextmanager
def get_db_session():
    """
    Context manager providing a transactional scope for database sessions.
    Automatically handles commit on success and rollback on exceptions.
    """
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"Database transaction error. Rolled back: {e}")
        raise
    finally:
        session.close()

def init_db():
    """
    Initializes database tables according to SQLAlchemy structures.
    """
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Successfully initialized database tables.")
    except Exception as e:
        logger.critical(f"Critical failure initializing PostgreSQL database: {e}")
        raise
