from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.v1.db_ping import db_ping
from app.data.models import Base
from app.main import app


def test_db_ping_route_is_registered() -> None:
    db_ping_routes = [
        route
        for route in app.routes
        if getattr(route, "path", None) == "/api/v1/db-ping"
        and "GET" in getattr(route, "methods", set())
    ]

    assert len(db_ping_routes) == 1


def test_db_ping_returns_ok_when_database_session_works(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(bind=engine)
    test_session_factory = sessionmaker(bind=engine)

    with test_session_factory() as session:
        assert db_ping(session) == {"status": "ok"}
