import pytest
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.profile import read_profile, save_profile
from app.core.auth import AuthenticatedUser
from app.data.models import Profile
from app.schemas.profile import ProfileRequest


def profile_payload(**overrides: object) -> ProfileRequest:
    payload: dict[str, object] = {
        "display_name": " Ronen ",
        "base_currency": "USD",
        "time_horizon": " 10+ years ",
        "investment_frequency": " monthly ",
    }
    payload.update(overrides)
    return ProfileRequest.model_validate(payload)


def test_profile_goal_fields_round_trip_through_api(
    authenticated_user: AuthenticatedUser,
    db_session: Session,
) -> None:
    response = save_profile(
        profile_payload(
            risk_tolerance="balanced",
            interest_tags=["Dividends", "AI Infrastructure", "dividends"],
            excluded_sectors=["TOBACCO", "high fee funds", "tobacco"],
            goals_note="  Prefer low-fee ETFs for a home down payment.  ",
        ),
        authenticated_user,
        db_session,
    )

    assert response.risk_tolerance == "balanced"
    assert response.interest_tags == ["dividends", "ai infrastructure"]
    assert response.excluded_sectors == ["tobacco", "high fee funds"]
    assert response.goals_note == "Prefer low-fee ETFs for a home down payment."

    reloaded = read_profile(authenticated_user, db_session)
    assert reloaded.risk_tolerance == "balanced"
    assert reloaded.interest_tags == ["dividends", "ai infrastructure"]
    assert reloaded.excluded_sectors == ["tobacco", "high fee funds"]
    assert reloaded.goals_note == "Prefer low-fee ETFs for a home down payment."


def test_existing_profile_without_goal_fields_uses_response_defaults(
    authenticated_user: AuthenticatedUser,
    db_session: Session,
) -> None:
    profile = Profile(
        user_id=authenticated_user.user_id,
        display_name="Ronen",
        base_currency="USD",
        time_horizon="10+ years",
        investment_frequency="monthly",
    )
    db_session.add(profile)
    db_session.commit()

    response = read_profile(authenticated_user, db_session)

    assert response.risk_tolerance is None
    assert response.interest_tags == []
    assert response.excluded_sectors == []
    assert response.goals_note is None


def test_free_form_keywords_are_normalized_and_deduped() -> None:
    payload = profile_payload(
        interest_tags=["growth", "moonshots", "GROWTH", "real estate"],
        excluded_sectors=["gambling", "space mining", "GAMBLING"],
    )

    assert payload.interest_tags == ["growth", "moonshots", "real estate"]
    assert payload.excluded_sectors == ["gambling", "space mining"]


def test_invalid_risk_tolerance_is_rejected() -> None:
    with pytest.raises(ValidationError):
        profile_payload(risk_tolerance="maximum")


def test_updating_required_fields_preserves_existing_goal_fields(
    authenticated_user: AuthenticatedUser,
    db_session: Session,
) -> None:
    first_response = save_profile(
        profile_payload(
            risk_tolerance="aggressive",
            interest_tags=["technology", "growth"],
            excluded_sectors=["fossil_fuels"],
            goals_note="Long-term growth.",
        ),
        authenticated_user,
        db_session,
    )

    second_response = save_profile(
        profile_payload(display_name="Ron"),
        authenticated_user,
        db_session,
    )

    assert second_response.id == first_response.id
    assert second_response.display_name == "Ron"
    assert second_response.risk_tolerance == "aggressive"
    assert second_response.interest_tags == ["technology", "growth"]
    assert second_response.excluded_sectors == ["fossil_fuels"]
    assert second_response.goals_note == "Long-term growth."

    saved_profile = db_session.scalar(select(Profile))
    assert saved_profile is not None
    assert saved_profile.risk_tolerance == "aggressive"
    assert saved_profile.interest_tags == ["technology", "growth"]
    assert saved_profile.excluded_sectors == ["fossil_fuels"]
    assert saved_profile.goals_note == "Long-term growth."


def test_blank_goals_note_becomes_null() -> None:
    payload = profile_payload(goals_note="   ")

    assert payload.goals_note is None
