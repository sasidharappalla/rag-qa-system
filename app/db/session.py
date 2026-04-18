"""Engine + session factory for the metadata DB.

Held behind lazy accessors so tests can swap `DATABASE_URL` (to SQLite) before
anything touches Postgres. Production path uses Postgres via docker-compose.
"""

from __future__ import annotations

from collections.abc import Generator
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from app.db.models import Base


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    """Create (once) the SQLAlchemy engine. SQLite URLs get the required check_same_thread tweak."""
    url = get_settings().database_url
    connect_args: dict[str, object] = {}
    if url.startswith("sqlite"):
        # Allow the test client's thread + the FastAPI request thread to share a connection.
        connect_args["check_same_thread"] = False
    return create_engine(url, connect_args=connect_args, future=True, pool_pre_ping=True)


SessionLocal = sessionmaker(autocommit=False, autoflush=False, future=True)


def init_db() -> None:
    """Create all tables. Safe to call on every startup; it's a no-op if they exist."""
    engine = get_engine()
    SessionLocal.configure(bind=engine)
    Base.metadata.create_all(bind=engine)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a request-scoped session."""
    if SessionLocal.kw.get("bind") is None:
        # First-use safety net: tests that import get_db without calling init_db.
        SessionLocal.configure(bind=get_engine())
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def reset_engine_cache() -> None:
    """Test helper — drop the cached engine so a new DATABASE_URL takes effect."""
    get_engine.cache_clear()
    SessionLocal.configure(bind=None)  # type: ignore[arg-type]
