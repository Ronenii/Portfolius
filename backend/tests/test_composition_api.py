from datetime import date
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.api.v1.portfolio import read_portfolio_breakdowns, read_portfolio_composition
from app.core.auth import AuthenticatedUser, get_current_user
from app.data.models import Holding, Instrument, Price, Profile
from app.main import app


def add_profile(db_session: Session, user_id: str = "user-123") -> Profile:
    profile = Profile(
        user_id=user_id,
        display_name="Ronen",
        base_currency="USD",
        time_horizon="10+ years",
        investment_frequency="monthly",
    )
    db_session.add(profile)
    db_session.commit()
    return profile


def add_instrument(
    db_session: Session,
    symbol: str,
    *,
    currency: str = "USD",
    asset_class: str | None = "ETF",
    sector: str | None = "Broad Market",
    country: str | None = "United States",
    region: str | None = "North America",
    close_price: str | None = "500",
) -> Instrument:
    instrument = Instrument(
        symbol=symbol,
        name=f"{symbol} Fund",
        exchange="NYSEARCA",
        currency=currency,
        asset_class=asset_class,
        sector=sector,
        country=country,
        region=region,
    )
    db_session.add(instrument)
    db_session.flush()
    if close_price is not None:
        db_session.add(
            Price(
                instrument=instrument,
                price_date=date(2026, 6, 5),
                close_price=Decimal(close_price),
                currency=currency,
                source="fake",
            )
        )
    db_session.commit()
    return instrument


def add_holding(
    db_session: Session,
    user_id: str,
    instrument: Instrument,
    quantity: str = "2",
    average_cost: str = "400",
) -> Holding:
    holding = Holding(
        user_id=user_id,
        instrument=instrument,
        quantity=Decimal(quantity),
        average_cost=Decimal(average_cost),
    )
    db_session.add(holding)
    db_session.commit()
    return holding


def composition_routes() -> list[object]:
    return [
        route
        for route in app.routes
        if getattr(route, "path", None)
        == "/api/v1/portfolio/breakdowns/{dimension}/{key}/composition"
    ]


def test_composition_route_is_registered_and_requires_auth() -> None:
    routes = composition_routes()

    assert any("GET" in getattr(route, "methods", set()) for route in routes)
    for route in routes:
        dependency_calls = {
            dependency.call for dependency in route.dependant.dependencies
        }
        assert get_current_user in dependency_calls


def test_composition_returns_only_authenticated_users_holdings(
    authenticated_user: AuthenticatedUser,
    second_user: AuthenticatedUser,
    db_session: Session,
) -> None:
    add_profile(db_session, authenticated_user.user_id)
    add_profile(db_session, second_user.user_id)
    voo = add_instrument(db_session, "VOO", close_price="500")
    bnd = add_instrument(db_session, "BND", close_price="80")
    add_holding(db_session, authenticated_user.user_id, voo, quantity="2")
    add_holding(db_session, second_user.user_id, bnd, quantity="10")

    response = read_portfolio_composition(
        "asset_class",
        "ETF",
        authenticated_user,
        db_session,
    )

    assert [row.symbol for row in response.children] == ["VOO"]
    assert response.market_value == Decimal("1000")


def test_unknown_dimension_returns_404(
    authenticated_user: AuthenticatedUser,
    db_session: Session,
) -> None:
    add_profile(db_session, authenticated_user.user_id)

    with pytest.raises(HTTPException) as exc_info:
        read_portfolio_composition(
            "style",
            "ETF",
            authenticated_user,
            db_session,
        )

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Unknown allocation dimension"


def test_unknown_key_with_valid_dimension_returns_empty_children(
    authenticated_user: AuthenticatedUser,
    db_session: Session,
) -> None:
    add_profile(db_session, authenticated_user.user_id)
    voo = add_instrument(db_session, "VOO", asset_class="ETF")
    add_holding(db_session, authenticated_user.user_id, voo)

    response = read_portfolio_composition(
        "asset_class",
        "Bond",
        authenticated_user,
        db_session,
    )

    assert response.children == []
    assert response.market_value == Decimal("0")
    assert response.percent_of_portfolio == Decimal("0")


def test_missing_profile_returns_404(
    authenticated_user: AuthenticatedUser,
    db_session: Session,
) -> None:
    with pytest.raises(HTTPException) as exc_info:
        read_portfolio_composition(
            "asset_class",
            "ETF",
            authenticated_user,
            db_session,
        )

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Profile not found"


def test_currency_query_parameter_scopes_multicurrency_label(
    authenticated_user: AuthenticatedUser,
    db_session: Session,
) -> None:
    add_profile(db_session, authenticated_user.user_id)
    voo = add_instrument(db_session, "VOO", currency="USD", close_price="500")
    euna = add_instrument(db_session, "EUNA", currency="EUR", close_price="60")
    add_holding(db_session, authenticated_user.user_id, voo, quantity="2")
    add_holding(db_session, authenticated_user.user_id, euna, quantity="3")

    response = read_portfolio_composition(
        "asset_class",
        "ETF",
        authenticated_user,
        db_session,
        currency="EUR",
    )

    assert response.currency == "EUR"
    assert [row.symbol for row in response.children] == ["EUNA"]
    assert response.market_value == Decimal("180")
    assert response.percent_of_portfolio == Decimal("100")


def test_existing_breakdowns_response_shape_is_unchanged(
    authenticated_user: AuthenticatedUser,
    db_session: Session,
) -> None:
    add_profile(db_session, authenticated_user.user_id)
    voo = add_instrument(db_session, "VOO")
    add_holding(db_session, authenticated_user.user_id, voo)

    response = read_portfolio_breakdowns(authenticated_user, db_session)
    payload = response.model_dump(mode="json")

    assert set(payload) == {
        "instrument",
        "asset_class",
        "sector",
        "country",
        "region",
        "currency",
        "unpriced_holding_count",
    }
    assert set(payload["instrument"][0]) == {
        "dimension",
        "label",
        "currency",
        "market_value",
        "percent",
        "holding_count",
    }
