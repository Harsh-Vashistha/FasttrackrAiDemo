"""
Database configuration — PostgreSQL via SQLAlchemy.

Design decisions:
- PostgreSQL over SQLite: production-grade RDBMS with full ACID compliance,
  concurrent write support, proper FK enforcement, and unlimited scale.
- psycopg2-binary: standard synchronous PostgreSQL driver for SQLAlchemy.
- Connection pooling (QueuePool): reuses TCP connections across requests,
  avoiding the handshake overhead on every API call.
  pool_size=10 + max_overflow=20 handles bursts up to 30 concurrent users.
  pool_pre_ping=True silently drops stale connections (e.g. after DB restart).
- 12-factor config: all credentials come from env vars — never hard-coded —
  so the same codebase runs in dev/staging/prod by swapping .env files.
"""

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# ---------------------------------------------------------------------------
# Build connection URL from env vars (sane local defaults provided)
# ---------------------------------------------------------------------------

DB_HOST     = os.getenv("DB_HOST",     "localhost")
DB_PORT     = os.getenv("DB_PORT",     "5432")
DB_NAME     = os.getenv("DB_NAME",     "fasttrackr")
DB_USER     = os.getenv("DB_USER",     "fasttrackr_user")
DB_PASSWORD = os.getenv("DB_PASSWORD", "fasttrackr_pass")

DATABASE_URL = (
    f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}"
    f"@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)

# ---------------------------------------------------------------------------
# Engine — connection pool tuned for a small financial-advisor web API
# ---------------------------------------------------------------------------

engine = create_engine(
    DATABASE_URL,
    pool_size=10,        # keep 10 connections open
    max_overflow=20,     # allow 20 extra under burst load
    pool_pre_ping=True,  # health-check connections before use
    pool_recycle=1800,   # recycle connections every 30 min (avoids timeouts)
    echo=False,          # flip to True to log all SQL during debugging
)

# ---------------------------------------------------------------------------
# Session factory & declarative base
# ---------------------------------------------------------------------------

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """
    FastAPI dependency — yields a scoped DB session, guaranteed to close
    after each request (even on exceptions). This prevents connection leaks.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
