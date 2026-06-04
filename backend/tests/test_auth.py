from datetime import UTC, datetime, timedelta

import jwt
import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.core.auth import AuthenticatedUser, get_current_user
from app.core.config import Settings

JWT_SECRET = "test-supabase-jwt-secret-with-32-bytes"


@pytest.fixture
def auth_settings() -> Settings:
    return Settings(
        supabase_url="https://example.supabase.co",
        supabase_jwt_secret=JWT_SECRET,
        auth_audience="authenticated",
    )


def create_token(**claims: object) -> str:
    payload: dict[str, object] = {
        "sub": "user-123",
        "aud": "authenticated",
        "email": "investor@example.com",
        "exp": datetime.now(UTC) + timedelta(minutes=5),
    }
    payload.update(claims)
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def bearer_credentials(token: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


def assert_unauthorized(exc_info: pytest.ExceptionInfo[HTTPException]) -> None:
    assert exc_info.value.status_code == 401


def test_missing_authorization_header_returns_401(auth_settings: Settings) -> None:
    with pytest.raises(HTTPException) as exc_info:
        get_current_user(None, auth_settings)

    assert_unauthorized(exc_info)


def test_malformed_bearer_token_returns_401(auth_settings: Settings) -> None:
    credentials = bearer_credentials("not-a-jwt")

    with pytest.raises(HTTPException) as exc_info:
        get_current_user(credentials, auth_settings)

    assert_unauthorized(exc_info)


def test_valid_token_returns_authenticated_user_id(auth_settings: Settings) -> None:
    credentials = bearer_credentials(create_token())

    current_user = get_current_user(credentials, auth_settings)

    assert current_user == AuthenticatedUser(
        user_id="user-123",
        email="investor@example.com",
        claims=current_user.claims,
    )
    assert current_user.claims["sub"] == "user-123"


def test_token_without_sub_returns_401(auth_settings: Settings) -> None:
    credentials = bearer_credentials(create_token(sub=None))

    with pytest.raises(HTTPException) as exc_info:
        get_current_user(credentials, auth_settings)

    assert_unauthorized(exc_info)


def test_expired_token_returns_401(auth_settings: Settings) -> None:
    credentials = bearer_credentials(
        create_token(exp=datetime.now(UTC) - timedelta(minutes=1))
    )

    with pytest.raises(HTTPException) as exc_info:
        get_current_user(credentials, auth_settings)

    assert_unauthorized(exc_info)
