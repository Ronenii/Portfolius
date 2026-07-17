from datetime import date
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.api.v1.portfolio import read_portfolio_projection
from app.core.auth import AuthenticatedUser, get_current_user
from app.data.models import Holding, Instrument, Price, Profile
from app.main import app


def add_profile(
    db_session: Session,
    user_id: str = "user-123",
    *,
    time_horizon: str = "10+ years",
    investment_frequency: str = "monthly",
    risk_tolerance: str | None = None,
    goal_target_amount: str | None = None,
    contribution_amount: str | None = None,
) -> Profile:
    profile = Profile(
        user_id=user_id,
        display_name="Ronen",
        base_currency="USD",
        time_horizon=time_horizon,
        investment_frequency=investment_frequency,
        risk_tolerance=risk_tolerance,
        goal_target_amount=(
            Decimal(goal_target_amount) if goal_target_amount is not None else None
        ),
        contribution_amount=(
            Decimal(contribution_amount) if contribution_amount is not None else None
        ),
    )
    db_session.add(profile)
    db_session.commit()
    return profile


def add_holding(
    db_session: Session,
    user_id: str,
    symbol: str,
    quantity: str = "2",
    average_cost: str = "400",
    close_price: str | None = "500",
) -> Holding:
    instrument = Instrument(
        symbol=symbol,
        name=f"{symbol} Fund",
        exchange="NYSEARCA",
        currency="USD",
        asset_class="ETF",
        sector="Broad Market",
        country="United States",
        region="North America",
    )
    holding = Holding(
        user_id=user_id,
        instrument=instrument,
        quantity=Decimal(quantity),
        average_cost=Decimal(average_cost),
    )
    db_session.add(holding)
    db_session.flush()
    if close_price is not None:
        db_session.add(
            Price(
                instrument=instrument,
                price_date=date(2026, 6, 5),
                close_price=Decimal(close_price),
                currency="USD",
                source="fake",
            )
        )
    db_session.commit()
    return holding


def test_projection_route_requires_auth() -> None:
    routes = [
        route
        for route in app.routes
        if getattr(route, "path", None) == "/api/v1/portfolio/projection"
    ]

    assert len(routes) == 1
    dependency_calls = {
        dependency.call for dependency in routes[0].dependant.dependencies
    }
    assert get_current_user in dependency_calls


def test_projection_returns_404_when_profile_is_missing(
    authenticated_user: AuthenticatedUser,
    db_session: Session,
) -> None:
    with pytest.raises(HTTPException) as exc_info:
        read_portfolio_projection(authenticated_user, db_session)

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Profile not found"


def test_projection_uses_profile_stored_values_by_default(
    authenticated_user: AuthenticatedUser,
    db_session: Session,
) -> None:
    add_profile(
        db_session,
        authenticated_user.user_id,
        time_horizon="10+ years",
        investment_frequency="monthly",
        goal_target_amount="50000",
        contribution_amount="200",
    )
    add_holding(db_session, authenticated_user.user_id, "VOO")

    response = read_portfolio_projection(authenticated_user, db_session)

    assert response.start_value == Decimal("1000")
    assert response.target_amount == Decimal("50000")
    assert response.contribution_amount == Decimal("200")
    assert response.contribution_frequency == "monthly"
    assert response.annual_return_expected == Decimal("8")
    assert response.horizon_years == 15


def test_projection_uses_computed_weighted_average_return(
    authenticated_user: AuthenticatedUser,
    db_session: Session,
) -> None:
    add_profile(db_session, authenticated_user.user_id, risk_tolerance="conservative")
    voo = add_holding(db_session, authenticated_user.user_id, "VOO")
    voo.instrument.historical_annual_return = Decimal("11.50")
    db_session.commit()

    response = read_portfolio_projection(authenticated_user, db_session)

    assert response.annual_return_expected == Decimal("11.50")


def test_projection_falls_back_to_risk_tolerance_default_return(
    authenticated_user: AuthenticatedUser,
    db_session: Session,
) -> None:
    add_profile(
        db_session,
        authenticated_user.user_id,
        risk_tolerance="aggressive",
    )

    response = read_portfolio_projection(authenticated_user, db_session)

    assert response.annual_return_expected == Decimal("8")


def test_projection_falls_back_to_default_annual_return_when_unset(
    authenticated_user: AuthenticatedUser,
    db_session: Session,
) -> None:
    add_profile(
        db_session,
        authenticated_user.user_id,
        risk_tolerance=None,
    )

    response = read_portfolio_projection(authenticated_user, db_session)

    assert response.annual_return_expected == Decimal("6")


@pytest.mark.parametrize(
    ("time_horizon", "expected_years"),
    [
        ("1-3 years", 3),
        ("3-7 years", 7),
        ("7-10 years", 10),
        ("10+ years", 15),
    ],
)
def test_projection_maps_known_time_horizon_labels(
    authenticated_user: AuthenticatedUser,
    db_session: Session,
    time_horizon: str,
    expected_years: int,
) -> None:
    add_profile(db_session, authenticated_user.user_id, time_horizon=time_horizon)

    response = read_portfolio_projection(authenticated_user, db_session)

    assert response.horizon_years == expected_years


def test_projection_falls_back_to_default_horizon_for_unrecognized_label(
    authenticated_user: AuthenticatedUser,
    db_session: Session,
) -> None:
    add_profile(db_session, authenticated_user.user_id, time_horizon="some nonsense")

    response = read_portfolio_projection(authenticated_user, db_session)

    assert response.horizon_years == 7


def test_projection_overrides_take_precedence_over_profile_values(
    authenticated_user: AuthenticatedUser,
    db_session: Session,
) -> None:
    add_profile(
        db_session,
        authenticated_user.user_id,
        time_horizon="10+ years",
        goal_target_amount="50000",
        contribution_amount="200",
    )

    response = read_portfolio_projection(
        authenticated_user,
        db_session,
        target=Decimal("90000"),
        contribution=Decimal("500"),
        annual_return=Decimal("10"),
        years=20,
    )

    assert response.target_amount == Decimal("90000")
    assert response.contribution_amount == Decimal("500")
    assert response.annual_return_expected == Decimal("10")
    assert response.horizon_years == 20


def test_projection_rejects_negative_target(
    authenticated_user: AuthenticatedUser,
    db_session: Session,
) -> None:
    add_profile(db_session, authenticated_user.user_id)

    with pytest.raises(HTTPException) as exc_info:
        read_portfolio_projection(
            authenticated_user, db_session, target=Decimal("-1")
        )

    assert exc_info.value.status_code == 422


def test_projection_rejects_negative_contribution(
    authenticated_user: AuthenticatedUser,
    db_session: Session,
) -> None:
    add_profile(db_session, authenticated_user.user_id)

    with pytest.raises(HTTPException) as exc_info:
        read_portfolio_projection(
            authenticated_user, db_session, contribution=Decimal("-1")
        )

    assert exc_info.value.status_code == 422


def test_projection_rejects_non_positive_years(
    authenticated_user: AuthenticatedUser,
    db_session: Session,
) -> None:
    add_profile(db_session, authenticated_user.user_id)

    with pytest.raises(HTTPException) as exc_info:
        read_portfolio_projection(authenticated_user, db_session, years=0)

    assert exc_info.value.status_code == 422


def test_projection_zero_override_is_treated_as_provided(
    authenticated_user: AuthenticatedUser,
    db_session: Session,
) -> None:
    add_profile(
        db_session,
        authenticated_user.user_id,
        contribution_amount="200",
    )

    response = read_portfolio_projection(
        authenticated_user,
        db_session,
        contribution=Decimal("0"),
    )

    assert response.contribution_amount == Decimal("0")


def test_projection_scopes_start_value_to_authenticated_user(
    authenticated_user: AuthenticatedUser,
    second_user: AuthenticatedUser,
    db_session: Session,
) -> None:
    add_profile(db_session, authenticated_user.user_id)
    add_profile(db_session, second_user.user_id)
    add_holding(db_session, authenticated_user.user_id, "VOO")
    add_holding(db_session, second_user.user_id, "BND", close_price="80")

    response_one = read_portfolio_projection(authenticated_user, db_session)
    response_two = read_portfolio_projection(second_user, db_session)

    assert response_one.start_value == Decimal("1000")
    assert response_two.start_value == Decimal("160")


def test_projection_uses_zero_computed_return_not_risk_tolerance_default(
    authenticated_user: AuthenticatedUser,
    db_session: Session,
) -> None:
    """Regression test: computed return of Decimal("0.00") should not be
    overridden by risk-tolerance default (which would be Decimal("4") for
    conservative). Tests the fix for the falsy Decimal("0") bug in the `or`
    operator fallback logic."""
    add_profile(db_session, authenticated_user.user_id, risk_tolerance="conservative")
    holding = add_holding(db_session, authenticated_user.user_id, "FLAT")
    holding.instrument.historical_annual_return = Decimal("0.00")
    db_session.commit()

    response = read_portfolio_projection(authenticated_user, db_session)

    assert response.annual_return_expected == Decimal("0.00")
