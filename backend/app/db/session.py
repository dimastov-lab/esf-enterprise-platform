"""The single SQLAlchemy engine and session factory (PostgreSQL only)."""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings

# A server-side statement timeout caps any single runaway query (defence against
# a pathological filter/sort locking up a connection). Tunable via env.
engine = create_engine(
    settings.DATABASE_URL,
    future=True,
    pool_pre_ping=True,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    connect_args={"options": f"-c statement_timeout={settings.DB_STATEMENT_TIMEOUT_MS}"},
)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, future=True)


def get_db():
    """FastAPI dependency: yields a session and always closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
