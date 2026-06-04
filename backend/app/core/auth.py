from dataclasses import dataclass
from functools import lru_cache
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import InvalidTokenError, PyJWKClient, PyJWKClientError

from app.core.config import Settings, get_settings


@dataclass(frozen=True)
class AuthenticatedUser:
    user_id: str
    email: str | None
    claims: dict[str, object]


bearer_scheme = HTTPBearer(auto_error=False)


def unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid authentication credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


def supabase_issuer(supabase_url: str) -> str:
    return f"{supabase_url.rstrip('/')}/auth/v1"


@lru_cache
def get_jwks_client(supabase_url: str) -> PyJWKClient:
    return PyJWKClient(f"{supabase_issuer(supabase_url)}/.well-known/jwks.json")


def decode_supabase_jwt(token: str, settings: Settings) -> dict[str, object]:
    if not settings.supabase_url:
        raise unauthorized()

    try:
        signing_key = get_jwks_client(
            settings.supabase_url,
        ).get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["ES256"],
            audience=settings.auth_audience,
            issuer=supabase_issuer(settings.supabase_url),
        )
    except (InvalidTokenError, PyJWKClientError) as exc:
        raise unauthorized() from exc

    if not isinstance(claims, dict):
        raise unauthorized()

    return claims


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AuthenticatedUser:
    if credentials is None:
        raise unauthorized()

    claims = decode_supabase_jwt(credentials.credentials, settings)
    subject = claims.get("sub")
    if not isinstance(subject, str) or not subject:
        raise unauthorized()

    email = claims.get("email")
    return AuthenticatedUser(
        user_id=subject,
        email=email if isinstance(email, str) else None,
        claims=claims,
    )
