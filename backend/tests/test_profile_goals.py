from decimal import Decimal

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


def test_creating_profile_with_projection_fields_persists_them(
    authenticated_user: AuthenticatedUser,
    db_session: Session,
) -> None:
    response = save_profile(
        profile_payload(
            goal_target_amount="100000",
            contribution_amount="500",
            expected_annual_return="7.5",
        ),
        authenticated_user,
        db_session,
    )

    assert response.goal_target_amount == Decimal("100000")
    assert response.contribution_amount == Decimal("500")
    assert response.expected_annual_return == Decimal("7.5")

    reloaded = read_profile(authenticated_user, db_session)
    assert reloaded.goal_target_amount == Decimal("100000")
    assert reloaded.contribution_amount == Decimal("500")
    assert reloaded.expected_annual_return == Decimal("7.5")


def test_creating_profile_without_projection_fields_leaves_them_none(
    authenticated_user: AuthenticatedUser,
    db_session: Session,
) -> None:
    response = save_profile(
        profile_payload(),
        authenticated_user,
        db_session,
    )

    assert response.goal_target_amount is None
    assert response.contribution_amount is None
    assert response.expected_annual_return is None


def test_updating_profile_without_projection_fields_preserves_existing_values(
    authenticated_user: AuthenticatedUser,
    db_session: Session,
) -> None:
    first_response = save_profile(
        profile_payload(
            goal_target_amount="100000",
            contribution_amount="500",
            expected_annual_return="7.5",
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
    assert second_response.goal_target_amount == Decimal("100000")
    assert second_response.contribution_amount == Decimal("500")
    assert second_response.expected_annual_return == Decimal("7.5")

    saved_profile = db_session.scalar(select(Profile))
    assert saved_profile is not None
    assert saved_profile.goal_target_amount == Decimal("100000")
    assert saved_profile.contribution_amount == Decimal("500")
    assert saved_profile.expected_annual_return == Decimal("7.5")


def test_updating_profile_with_new_projection_fields_updates_them(
    authenticated_user: AuthenticatedUser,
    db_session: Session,
) -> None:
    save_profile(
        profile_payload(
            goal_target_amount="100000",
            contribution_amount="500",
            expected_annual_return="7.5",
        ),
        authenticated_user,
        db_session,
    )

    second_response = save_profile(
        profile_payload(
            goal_target_amount="200000",
            contribution_amount="750",
            expected_annual_return="6.0",
        ),
        authenticated_user,
        db_session,
    )

    assert second_response.goal_target_amount == Decimal("200000")
    assert second_response.contribution_amount == Decimal("750")
    assert second_response.expected_annual_return == Decimal("6.0")


def test_negative_goal_target_amount_is_rejected() -> None:
    with pytest.raises(ValidationError):
        profile_payload(goal_target_amount="-1")


def test_negative_contribution_amount_is_rejected() -> None:
    with pytest.raises(ValidationError):
        profile_payload(contribution_amount="-1")


def test_negative_expected_annual_return_is_accepted() -> None:
    payload = profile_payload(expected_annual_return="-2.5")

    assert payload.expected_annual_return == Decimal("-2.5")
