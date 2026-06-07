from datetime import date
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.api.v1.jobs import refresh_prices
from app.api.v1.portfolio import read_portfolio_breakdowns, read_portfolio_snapshot
from app.core.auth import AuthenticatedUser, get_current_user
from app.core.config import Settings
from app.data.models import Holding, Instrument, Price, Profile
from app.integrations.market_data import MarketPrice
from app.main import app


class FakeMarketDataClient:
    def __init__(self) -> None:
        self.requests: list[tuple[str, str, str | None]] = []

    def get_latest_close(
        self,
        symbol: str,
        exchange: str,
        currency_hint: str | None,
    ) -> MarketPrice | None:
        self.requests.append((symbol, exchange, currency_hint))
        return MarketPrice(
            symbol=symbol,
            exchange=exchange,
            price_date=date(2026, 6, 5),
            close_price=Decimal("500"),
            currency=currency_hint or "UNKNOWN",
            source="fake",
        )


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


def portfolio_routes() -> list[object]:
    return [
        route
        for route in app.routes
        if getattr(route, "path", "").startswith("/api/v1/portfolio")
    ]


def test_portfolio_and_refresh_routes_require_auth() -> None:
    route_paths = {getattr(route, "path", None) for route in app.routes}

    assert "/api/v1/portfolio/snapshot" in route_paths
    assert "/api/v1/portfolio/breakdowns" in route_paths
    assert "/api/v1/jobs/refresh-prices" in route_paths
    for route in portfolio_routes():
        dependency_calls = {
            dependency.call for dependency in route.dependant.dependencies
        }
        assert get_current_user in dependency_calls


def test_snapshot_returns_only_authenticated_users_holdings(
    authenticated_user: AuthenticatedUser,
    second_user: AuthenticatedUser,
    db_session: Session,
) -> None:
    add_profile(db_session, authenticated_user.user_id)
    add_profile(db_session, second_user.user_id)
    add_holding(db_session, authenticated_user.user_id, "VOO")
    add_holding(db_session, second_user.user_id, "BND", close_price="80")

    response = read_portfolio_snapshot(authenticated_user, db_session)

    assert len(response.holdings) == 1
    assert response.holdings[0].instrument.symbol == "VOO"
    assert response.summary.total_market_value == Decimal("1000")


def test_breakdowns_return_only_authenticated_users_holdings(
    authenticated_user: AuthenticatedUser,
    second_user: AuthenticatedUser,
    db_session: Session,
) -> None:
    add_profile(db_session, authenticated_user.user_id)
    add_profile(db_session, second_user.user_id)
    add_holding(db_session, authenticated_user.user_id, "VOO")
    add_holding(db_session, second_user.user_id, "BND", close_price="80")

    response = read_portfolio_breakdowns(authenticated_user, db_session)

    assert [row.label for row in response.instrument] == ["VOO"]
    assert response.instrument[0].market_value == Decimal("1000")


def test_snapshot_returns_404_when_profile_is_missing(
    authenticated_user: AuthenticatedUser,
    db_session: Session,
) -> None:
    with pytest.raises(HTTPException) as exc_info:
        read_portfolio_snapshot(authenticated_user, db_session)

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Profile not found"


def test_empty_holdings_return_zero_snapshot_and_empty_breakdowns(
    authenticated_user: AuthenticatedUser,
    db_session: Session,
) -> None:
    add_profile(db_session, authenticated_user.user_id)

    snapshot = read_portfolio_snapshot(authenticated_user, db_session)
    breakdowns = read_portfolio_breakdowns(authenticated_user, db_session)

    assert snapshot.summary.total_market_value == Decimal("0")
    assert snapshot.summary.priced_holdings == 0
    assert snapshot.holdings == []
    assert breakdowns.instrument == []
    assert breakdowns.unpriced_holding_count == 0


def test_manual_refresh_uses_authenticated_user(
    authenticated_user: AuthenticatedUser,
    db_session: Session,
) -> None:
    add_profile(db_session, authenticated_user.user_id)
    add_holding(db_session, authenticated_user.user_id, "VOO", close_price=None)
    market_data_client = FakeMarketDataClient()

    response = refresh_prices(
        db_session,
        market_data_client,
        settings=Settings(),
        current_user=authenticated_user,
    )

    assert response.updated == 1
    assert market_data_client.requests == [("VOO", "NYSEARCA", "USD")]


def test_scheduler_secret_can_refresh_requested_user(
    authenticated_user: AuthenticatedUser,
    db_session: Session,
) -> None:
    add_profile(db_session, authenticated_user.user_id)
    add_holding(db_session, authenticated_user.user_id, "VOO", close_price=None)
    market_data_client = FakeMarketDataClient()

    response = refresh_prices(
        db_session,
        market_data_client,
        settings=Settings(scheduler_secret="secret"),
        scheduler_secret="secret",
        user_id=authenticated_user.user_id,
    )

    assert response.requested == 1
    assert response.updated == 1


def test_wrong_scheduler_secret_returns_401(db_session: Session) -> None:
    with pytest.raises(HTTPException) as exc_info:
        refresh_prices(
            db_session,
            FakeMarketDataClient(),
            settings=Settings(scheduler_secret="secret"),
            scheduler_secret="wrong",
            user_id="user-123",
        )

    assert exc_info.value.status_code == 401


def test_refresh_without_user_or_scheduler_secret_returns_401(
    db_session: Session,
) -> None:
    with pytest.raises(HTTPException) as exc_info:
        refresh_prices(
            db_session,
            FakeMarketDataClient(),
            settings=Settings(),
        )

    assert exc_info.value.status_code == 401
