from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

import app.core.auth as auth_module
from app.core.auth import AuthenticatedUser, get_current_user
from app.core.config import Settings

PRIVATE_KEY = ec.generate_private_key(ec.SECP256R1())
PUBLIC_KEY = PRIVATE_KEY.public_key()
KEY_ID = "test-key-id"


@dataclass(frozen=True)
class FakeSigningKey:
    key: object


class FakeJwksClient:
    def get_signing_key_from_jwt(self, token: str) -> FakeSigningKey:
        return FakeSigningKey(PUBLIC_KEY)


@pytest.fixture
def auth_settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    monkeypatch.setattr(
        auth_module,
        "get_jwks_client",
        lambda supabase_url: FakeJwksClient(),
    )
    return Settings(
        supabase_url="https://example.supabase.co",
        auth_audience="authenticated",
    )


def create_token(**claims: object) -> str:
    payload: dict[str, object] = {
        "sub": "user-123",
        "aud": "authenticated",
        "email": "investor@example.com",
        "exp": datetime.now(UTC) + timedelta(minutes=5),
        "iss": "https://example.supabase.co/auth/v1",
    }
    payload.update(claims)
    return jwt.encode(
        payload,
        PRIVATE_KEY,
        algorithm="ES256",
        headers={"kid": KEY_ID},
    )


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
