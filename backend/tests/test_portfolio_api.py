from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.api.v1.jobs import (
    refresh_etf_metadata,
    refresh_historical_returns,
    refresh_prices,
)
from app.api.v1.portfolio import read_portfolio_breakdowns, read_portfolio_snapshot
from app.core.auth import AuthenticatedUser, get_current_user
from app.core.config import Settings
from app.data.models import Holding, Instrument, Price, Profile
from app.integrations.market_data import MarketPrice
from app.main import app
from app.schemas.instruments import InstrumentSearchResult


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


class FakeHistoricalReturnClient:
    def __init__(self, returns: dict[str, Decimal | None]) -> None:
        self.returns = returns

    def get_historical_annualized_return(
        self,
        symbol: str,
        exchange: str,
        currency_hint: str | None,
    ) -> Decimal | None:
        return self.returns.get(symbol)


class FakeInstrumentLookupClient:
    def __init__(
        self,
        profiles: dict[str, InstrumentSearchResult | None],
        failing_symbols: set[str] | None = None,
    ) -> None:
        self.profiles = profiles
        self.failing_symbols = failing_symbols or set()
        self.requests: list[str] = []

    def profile(self, symbol: str) -> InstrumentSearchResult | None:
        self.requests.append(symbol)
        if symbol in self.failing_symbols:
            raise RuntimeError("provider failed")
        return self.profiles.get(symbol)


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
        datetime(2026, 6, 5, 21, 0, tzinfo=UTC),
        settings=Settings(),
        current_user=authenticated_user,
    )

    assert response.updated == 1
    assert market_data_client.requests == [("VOO", "NYSEARCA", "USD")]


def test_scheduler_secret_refreshes_all_users(
    authenticated_user: AuthenticatedUser,
    second_user: AuthenticatedUser,
    db_session: Session,
) -> None:
    add_profile(db_session, authenticated_user.user_id)
    add_profile(db_session, second_user.user_id)
    add_holding(db_session, authenticated_user.user_id, "VOO", close_price=None)
    add_holding(db_session, second_user.user_id, "BND", close_price=None)
    market_data_client = FakeMarketDataClient()

    response = refresh_prices(
        db_session,
        market_data_client,
        datetime(2026, 6, 5, 15, 0, tzinfo=UTC),
        settings=Settings(scheduler_secret="secret"),
        scheduler_secret="secret",
    )

    assert response.requested == 2
    assert response.updated == 2
    assert set(market_data_client.requests) == {
        ("VOO", "NYSEARCA", "USD"),
        ("BND", "NYSEARCA", "USD"),
    }


def test_etf_metadata_refresh_route_is_registered_as_migration_job() -> None:
    routes = [
        route
        for route in app.routes
        if getattr(route, "path", None) == "/api/v1/jobs/refresh-etf-metadata"
    ]

    assert len(routes) == 1
    dependency_calls = {
        dependency.call for dependency in routes[0].dependant.dependencies
    }
    assert get_current_user not in dependency_calls


def test_migration_refreshes_metadata_for_all_instruments(
    authenticated_user: AuthenticatedUser,
    second_user: AuthenticatedUser,
    db_session: Session,
) -> None:
    add_profile(db_session, authenticated_user.user_id)
    add_profile(db_session, second_user.user_id)
    ixc_holding = add_holding(db_session, authenticated_user.user_id, "IXC")
    ixc_holding.instrument.name = "iShares Global Energy ETF"
    ixc_holding.instrument.sector = "Financial Services"
    ixc_holding.instrument.region = "North America"
    other_holding = add_holding(db_session, second_user.user_id, "IEUR")
    stock = Instrument(
        symbol="AAPL",
        name="Apple Inc.",
        exchange="NASDAQ",
        currency="USD",
        asset_class="Stock",
        sector="Technology",
        country="United States",
        region="North America",
    )
    db_session.add(stock)
    db_session.commit()
    lookup_client = FakeInstrumentLookupClient(
        {
            "IXC": InstrumentSearchResult(
                symbol="IXC",
                name="iShares Global Energy ETF",
                exchange="NYSEARCA",
                currency="USD",
                asset_class="ETF",
                sector="Energy",
                country=None,
                region="Global",
                source="alphavantage",
            ),
            "IEUR": InstrumentSearchResult(
                symbol="IEUR",
                name="iShares Core MSCI Europe ETF",
                exchange="NYSEARCA",
                currency="USD",
                asset_class="ETF",
                sector="Diversified ETF",
                country=None,
                region="Europe",
                source="alphavantage",
            ),
        }
    )

    response = refresh_etf_metadata(
        db_session,
        lookup_client,
        settings=Settings(scheduler_secret="secret"),
        scheduler_secret="secret",
    )

    db_session.refresh(ixc_holding.instrument)
    db_session.refresh(other_holding.instrument)
    db_session.refresh(stock)
    assert response.requested == 3
    assert response.updated == 2
    assert response.skipped == 1
    assert response.failed == 0
    assert lookup_client.requests == ["AAPL", "IEUR", "IXC"]
    assert ixc_holding.instrument.sector == "Energy"
    assert ixc_holding.instrument.region == "Global"
    assert other_holding.instrument.sector == "Diversified ETF"
    assert other_holding.instrument.region == "Europe"
    assert stock.sector == "Technology"


def test_migration_metadata_refresh_counts_provider_misses_and_failures(
    authenticated_user: AuthenticatedUser,
    db_session: Session,
) -> None:
    add_profile(db_session, authenticated_user.user_id)
    add_holding(db_session, authenticated_user.user_id, "IXC")
    add_holding(db_session, authenticated_user.user_id, "BUG")
    lookup_client = FakeInstrumentLookupClient(
        profiles={"IXC": None},
        failing_symbols={"BUG"},
    )

    response = refresh_etf_metadata(
        db_session,
        lookup_client,
        settings=Settings(scheduler_secret="secret"),
        scheduler_secret="secret",
    )

    assert response.requested == 2
    assert response.updated == 0
    assert response.skipped == 1
    assert response.failed == 1
    assert lookup_client.requests == ["BUG", "IXC"]


def test_metadata_refresh_always_updates_and_stamps_updated_at(
    authenticated_user: AuthenticatedUser,
    db_session: Session,
) -> None:
    add_profile(db_session, authenticated_user.user_id)
    holding = add_holding(db_session, authenticated_user.user_id, "IXC")
    lookup_client = FakeInstrumentLookupClient(
        {
            "IXC": InstrumentSearchResult(
                symbol="IXC",
                name="IXC Fund",
                exchange="NYSEARCA",
                currency="USD",
                asset_class="ETF",
                sector="Broad Market",
                country="United States",
                region="North America",
                source="fmp",
            ),
        }
    )

    response = refresh_etf_metadata(
        db_session,
        lookup_client,
        settings=Settings(scheduler_secret="secret"),
        scheduler_secret="secret",
    )

    db_session.refresh(holding.instrument)
    assert response.requested == 1
    assert response.updated == 1
    assert response.skipped == 0
    assert response.failed == 0
    assert holding.instrument.metadata_updated_at is not None


def test_metadata_refresh_requires_scheduler_secret(
    db_session: Session,
) -> None:
    with pytest.raises(HTTPException) as exc_info:
        refresh_etf_metadata(
            db_session,
            FakeInstrumentLookupClient({}),
            settings=Settings(scheduler_secret="secret"),
        )

    assert exc_info.value.status_code == 401


def test_scheduler_refresh_skips_when_us_market_is_closed(
    authenticated_user: AuthenticatedUser,
    db_session: Session,
) -> None:
    add_profile(db_session, authenticated_user.user_id)
    add_holding(db_session, authenticated_user.user_id, "VOO", close_price=None)
    market_data_client = FakeMarketDataClient()

    response = refresh_prices(
        db_session,
        market_data_client,
        datetime(2026, 6, 5, 21, 0, tzinfo=UTC),
        settings=Settings(scheduler_secret="secret"),
        scheduler_secret="secret",
    )

    assert response.requested == 0
    assert response.updated == 0
    assert response.skipped == 0
    assert response.failed == 0
    assert market_data_client.requests == []


def test_wrong_scheduler_secret_returns_401(db_session: Session) -> None:
    with pytest.raises(HTTPException) as exc_info:
        refresh_prices(
            db_session,
            FakeMarketDataClient(),
            datetime(2026, 6, 5, 15, 0, tzinfo=UTC),
            settings=Settings(scheduler_secret="secret"),
            scheduler_secret="wrong",
        )

    assert exc_info.value.status_code == 401


def test_refresh_without_user_or_scheduler_secret_returns_401(
    db_session: Session,
) -> None:
    with pytest.raises(HTTPException) as exc_info:
        refresh_prices(
            db_session,
            FakeMarketDataClient(),
            datetime(2026, 6, 5, 15, 0, tzinfo=UTC),
            settings=Settings(),
        )

    assert exc_info.value.status_code == 401


def test_historical_returns_refresh_route_is_registered_as_migration_job() -> None:
    routes = [
        route
        for route in app.routes
        if getattr(route, "path", None) == "/api/v1/jobs/refresh-historical-returns"
    ]

    assert len(routes) == 1
    dependency_calls = {
        dependency.call for dependency in routes[0].dependant.dependencies
    }
    assert get_current_user not in dependency_calls


def test_historical_returns_refresh_computes_for_all_instruments(
    authenticated_user: AuthenticatedUser,
    db_session: Session,
) -> None:
    add_profile(db_session, authenticated_user.user_id)
    ixc_holding = add_holding(db_session, authenticated_user.user_id, "IXC")
    market_data_client = FakeHistoricalReturnClient({"IXC": Decimal("9.42")})

    response = refresh_historical_returns(
        db_session,
        market_data_client,
        settings=Settings(scheduler_secret="secret"),
        scheduler_secret="secret",
    )

    db_session.refresh(ixc_holding.instrument)
    assert response.requested == 1
    assert response.updated == 1
    assert response.skipped == 0
    assert response.failed == 0
    assert ixc_holding.instrument.historical_annual_return == Decimal("9.42")


def test_historical_returns_refresh_requires_scheduler_secret(
    db_session: Session,
) -> None:
    with pytest.raises(HTTPException) as exc_info:
        refresh_historical_returns(
            db_session,
            FakeHistoricalReturnClient({}),
            settings=Settings(scheduler_secret="secret"),
        )

    assert exc_info.value.status_code == 401
