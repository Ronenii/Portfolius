from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

from app.core.config import get_settings


def build_engine_kwargs(database_url: str) -> dict:
    """Engine kwargs tuned per driver.

    For psycopg3 behind a transaction-mode pooler (Supabase Supavisor :6543 /
    PgBouncer):

    - ``prepare_threshold=None`` disables psycopg3's server-side prepared
      statements. They are auto-named ``_pg3_N``; because the pooler multiplexes
      physical backends across logical sessions, psycopg's per-connection
      bookkeeping desyncs and raises ``prepared statement "_pg3_0" already
      exists``. Disabling them is Supabase's documented fix.
    - ``NullPool`` stops SQLAlchemy from holding connections the pooler is
      already multiplexing; each checkout gets a fresh pooled connection, so
      ``pool_pre_ping`` is unnecessary.

    Both are psycopg-only, so they must not leak to the local SQLite engine.
    """
    if make_url(database_url).get_driver_name() == "psycopg":
        return {
            "poolclass": NullPool,
            "connect_args": {"prepare_threshold": None},
        }
    return {"pool_pre_ping": True}


_database_url = get_settings().database_url
engine = create_engine(_database_url, **build_engine_kwargs(_database_url))
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
