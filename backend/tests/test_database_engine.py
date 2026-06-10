from sqlalchemy.pool import NullPool

from app.data.database import build_engine_kwargs


def test_psycopg3_postgres_disables_prepared_statements_and_pooling() -> None:
    # psycopg3 auto-creates server-side prepared statements, which collide
    # ('prepared statement "_pg3_N" already exists') behind a transaction-mode
    # pooler such as Supabase Supavisor / PgBouncer. They must be disabled, and
    # NullPool avoids holding connections the pooler already multiplexes.
    kwargs = build_engine_kwargs("postgresql+psycopg://user:pw@host:6543/postgres")

    assert kwargs == {
        "poolclass": NullPool,
        "connect_args": {"prepare_threshold": None},
    }


def test_sqlite_gets_no_psycopg_engine_kwargs() -> None:
    # prepare_threshold/NullPool are psycopg-only; SQLite keeps default pooling.
    assert build_engine_kwargs("sqlite+pysqlite:///./portfolius.db") == {
        "pool_pre_ping": True,
    }
