"""Database setup (SQLAlchemy 2.0).

Falls back to SQLite when the configured PostgreSQL is unreachable, so the app
still serves (health + USSD + booking) out of the box in local dev where only
Postgres on 5432 is available. Production (with a reachable Postgres) uses
Postgres as configured.
"""

import time
import logging
from urllib.parse import ParseResult, urlparse

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import settings

logger = logging.getLogger(__name__)

_SQLITE_FALLBACK_URL = "sqlite:///./afyasmart.db"


def _parse_url(url: str) -> ParseResult:
    return urlparse(url)


def _is_postgres_unreachable(url: str, retries: int = 3, delay: float = 1.0) -> bool:
    """Return True when Postgres cannot be reached within a few attempts."""
    parsed = _parse_url(url)
    if parsed.scheme not in ("postgresql", "postgres", "postgresql+psycopg2"):
        return False
    for attempt in range(retries):
        try:
            engine = create_engine(
                url,
                pool_pre_ping=True,
                connect_args={"connect_timeout": 2},
            )
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return False
        except Exception:
            if attempt == retries - 1:
                return True
            time.sleep(delay)
    return True


def build_engine() -> tuple:
    """Build the SQLAlchemy engine, falling back to SQLite when Postgres is down."""
    database_url = settings.database_url
    if _is_postgres_unreachable(database_url):
        logger.warning(
            "PostgreSQL unreachable (host=%s port=%s) — falling back to SQLite.",
            _parse_url(database_url).hostname,
            _parse_url(database_url).port,
        )
        database_url = _SQLITE_FALLBACK_URL

    connect_args: dict = {}
    if database_url.startswith("sqlite"):
        connect_args = {}  # sqlite has no connect_timeout
    else:
        connect_args = {"connect_timeout": 2}  # postgres only

    engine = create_engine(
        database_url,
        pool_pre_ping=True,
        connect_args=connect_args,
    )
    return engine, database_url


engine, resolved_database_url = build_engine()

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


class Base(DeclarativeBase):
    pass


def get_db():
    """FastAPI dependency — yields a DB session per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
