from collections.abc import Generator
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.auth import AuthenticatedUser
from app.data.models import Base


@pytest.fixture
def db_session(tmp_path: Path) -> Generator[Session]:
    engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine)

    with session_factory() as session:
        yield session


@pytest.fixture
def authenticated_user() -> AuthenticatedUser:
    return AuthenticatedUser(
        user_id="user-123",
        email="investor@example.com",
        claims={"sub": "user-123"},
    )


@pytest.fixture
def second_user() -> AuthenticatedUser:
    return AuthenticatedUser(
        user_id="user-456",
        email="other@example.com",
        claims={"sub": "user-456"},
    )
