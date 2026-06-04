import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.v1.profile import read_profile, save_profile
from app.core.auth import AuthenticatedUser, get_current_user
from app.data.models import Profile
from app.main import app
from app.schemas.profile import ProfileRequest


def profile_payload(**overrides: str) -> ProfileRequest:
    payload = {
        "display_name": " Ronen ",
        "base_currency": "USD",
        "time_horizon": " 10+ years ",
        "investment_frequency": " monthly ",
    }
    payload.update(overrides)
    return ProfileRequest.model_validate(payload)


def profile_routes() -> list[object]:
    return [
        route
        for route in app.routes
        if getattr(route, "path", None) == "/api/v1/profile"
    ]


def test_profile_routes_are_registered_and_require_auth() -> None:
    routes = profile_routes()
    methods_by_route = [getattr(route, "methods", set()) for route in routes]

    assert any("GET" in methods for methods in methods_by_route)
    assert any("PUT" in methods for methods in methods_by_route)
    for route in routes:
        dependency_calls = {
            dependency.call for dependency in route.dependant.dependencies
        }
        assert get_current_user in dependency_calls


def test_get_profile_returns_404_when_missing(
    authenticated_user: AuthenticatedUser,
    db_session: Session,
) -> None:
    with pytest.raises(HTTPException) as exc_info:
        read_profile(authenticated_user, db_session)

    assert exc_info.value.status_code == 404


def test_put_profile_creates_profile_scoped_to_authenticated_user(
    authenticated_user: AuthenticatedUser,
    db_session: Session,
) -> None:
    payload = ProfileRequest.model_validate(
        {
            "user_id": "client-owned-user-id",
            "display_name": " Ronen ",
            "base_currency": "USD",
            "time_horizon": " 10+ years ",
            "investment_frequency": " monthly ",
        }
    )

    response = save_profile(payload, authenticated_user, db_session)

    assert response.user_id == "user-123"
    assert response.display_name == "Ronen"
    assert response.time_horizon == "10+ years"
    assert response.investment_frequency == "monthly"
    saved_profile = db_session.scalar(select(Profile))
    assert saved_profile is not None
    assert saved_profile.user_id == "user-123"


def test_put_profile_updates_existing_profile_instead_of_creating_second_row(
    authenticated_user: AuthenticatedUser,
    db_session: Session,
) -> None:
    first_response = save_profile(
        profile_payload(display_name="Ronen"),
        authenticated_user,
        db_session,
    )
    second_response = save_profile(
        profile_payload(display_name="Ron", investment_frequency="weekly"),
        authenticated_user,
        db_session,
    )

    profile_count = db_session.scalar(select(func.count()).select_from(Profile))

    assert profile_count == 1
    assert second_response.id == first_response.id
    assert second_response.display_name == "Ron"
    assert second_response.investment_frequency == "weekly"


def test_second_user_cannot_read_first_users_profile(
    authenticated_user: AuthenticatedUser,
    second_user: AuthenticatedUser,
    db_session: Session,
) -> None:
    save_profile(profile_payload(), authenticated_user, db_session)

    with pytest.raises(HTTPException) as exc_info:
        read_profile(second_user, db_session)

    assert exc_info.value.status_code == 404


def test_invalid_currency_is_rejected() -> None:
    with pytest.raises(ValidationError):
        profile_payload(base_currency="usd")
