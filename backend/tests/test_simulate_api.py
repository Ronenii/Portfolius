from datetime import date
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.api.v1.portfolio import simulate_portfolio
from app.core.auth import AuthenticatedUser, get_current_user
from app.data.models import Holding, Instrument, Price, Profile
from app.integrations.market_data import MarketPrice
from app.main import app
from app.schemas.instruments import InstrumentSearchResult
from app.schemas.simulation import SimulationRequest, TradeLeg


class FakeInstrumentLookupClient:
    def __init__(self, profiles: dict[str, InstrumentSearchResult | None]) -> None:
        self.profiles = profiles
        self.requests: list[str] = []

    def profile(self, symbol: str) -> InstrumentSearchResult | None:
        self.requests.append(symbol)
        return self.profiles.get(symbol)


class FakeMarketDataClient:
    def __init__(self, prices: dict[str, MarketPrice | None]) -> None:
        self.prices = prices
        self.requests: list[tuple[str, str, str | None]] = []

    def get_latest_close(
        self,
        symbol: str,
        exchange: str,
        currency_hint: str | None,
    ) -> MarketPrice | None:
        self.requests.append((symbol, exchange, currency_hint))
        return self.prices.get(symbol)


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
    asset_class: str = "ETF",
    sector: str = "Broad Market",
    country: str = "United States",
    region: str = "North America",
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


def simulate_routes() -> list[object]:
    return [
        route
        for route in app.routes
        if getattr(route, "path", None) == "/api/v1/portfolio/simulate"
    ]


def simulate_payload(*legs: TradeLeg) -> SimulationRequest:
    return SimulationRequest(legs=list(legs))


def empty_lookup_client() -> FakeInstrumentLookupClient:
    return FakeInstrumentLookupClient({})


def empty_market_data_client() -> FakeMarketDataClient:
    return FakeMarketDataClient({})


def market_price(symbol: str, close_price: str) -> MarketPrice:
    return MarketPrice(
        symbol=symbol,
        exchange="NYSEARCA",
        price_date=date(2026, 6, 8),
        close_price=Decimal(close_price),
        currency="USD",
        source="fake",
    )


def test_simulate_route_is_registered_and_requires_auth() -> None:
    routes = simulate_routes()

    assert any("POST" in getattr(route, "methods", set()) for route in routes)
    for route in routes:
        dependency_calls = {
            dependency.call for dependency in route.dependant.dependencies
        }
        assert get_current_user in dependency_calls


def test_simulation_uses_only_authenticated_users_holdings(
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

    response = simulate_portfolio(
        simulate_payload(
            TradeLeg(instrument_id=voo.id, action="sell", quantity=Decimal("1"))
        ),
        authenticated_user,
        db_session,
        empty_lookup_client(),
        empty_market_data_client(),
    )

    assert [row.label for row in response.current.instrument] == ["VOO"]
    assert [row.label for row in response.simulated.instrument] == ["VOO"]
    assert response.simulated.instrument[0].market_value == Decimal("500")


def test_buy_sell_basket_returns_current_simulated_and_delta(
    authenticated_user: AuthenticatedUser,
    db_session: Session,
) -> None:
    add_profile(db_session, authenticated_user.user_id)
    voo = add_instrument(db_session, "VOO", close_price="500")
    add_instrument(db_session, "QQQ", close_price="250")
    add_holding(db_session, authenticated_user.user_id, voo, quantity="2")

    response = simulate_portfolio(
        simulate_payload(
            TradeLeg(instrument_id=voo.id, action="sell", quantity=Decimal("1")),
            TradeLeg(symbol="QQQ", action="buy", quantity=Decimal("2")),
        ),
        authenticated_user,
        db_session,
        empty_lookup_client(),
        empty_market_data_client(),
    )

    assert response.current.instrument[0].label == "VOO"
    assert {row.label for row in response.simulated.instrument} == {"VOO", "QQQ"}
    assert response.delta
    assert response.warnings == []


def test_over_sell_returns_warning_not_error(
    authenticated_user: AuthenticatedUser,
    db_session: Session,
) -> None:
    add_profile(db_session, authenticated_user.user_id)
    voo = add_instrument(db_session, "VOO", close_price="500")
    add_holding(db_session, authenticated_user.user_id, voo, quantity="2")

    response = simulate_portfolio(
        simulate_payload(
            TradeLeg(instrument_id=voo.id, action="sell", quantity=Decimal("5"))
        ),
        authenticated_user,
        db_session,
        empty_lookup_client(),
        empty_market_data_client(),
    )

    assert response.simulated.instrument == []
    assert response.warnings == ["Sell for VOO capped at held quantity 2.00000000."]


def test_new_instrument_buy_resolved_from_local_instrument_metadata(
    authenticated_user: AuthenticatedUser,
    db_session: Session,
) -> None:
    add_profile(db_session, authenticated_user.user_id)
    vxus = add_instrument(
        db_session,
        "VXUS",
        sector="International",
        country="Global",
        region="Global ex-US",
        close_price="100",
    )

    response = simulate_portfolio(
        simulate_payload(TradeLeg(symbol="VXUS", action="buy", quantity=Decimal("2"))),
        authenticated_user,
        db_session,
        empty_lookup_client(),
        empty_market_data_client(),
    )

    assert response.simulated.instrument[0].label == vxus.symbol
    assert response.simulated.sector[0].label == "International"
    assert response.simulated.country[0].label == "Global"
    assert response.simulated.region[0].label == "Global ex-US"


def test_new_instrument_buy_creates_and_prices_missing_instrument(
    authenticated_user: AuthenticatedUser,
    db_session: Session,
) -> None:
    add_profile(db_session, authenticated_user.user_id)
    lookup_client = FakeInstrumentLookupClient(
        {
            "IEMG": InstrumentSearchResult(
                symbol="IEMG",
                name="iShares Core MSCI Emerging Markets ETF",
                exchange="NYSEARCA",
                currency="USD",
                asset_class="ETF",
                sector="Broad Market",
                country="United States",
                region="North America",
                source="fake",
            )
        }
    )
    market_data_client = FakeMarketDataClient(
        {"IEMG": market_price("IEMG", "54.12")}
    )

    response = simulate_portfolio(
        simulate_payload(TradeLeg(symbol="IEMG", action="buy", quantity=Decimal("3"))),
        authenticated_user,
        db_session,
        lookup_client,
        market_data_client,
    )

    instrument = (
        db_session.query(Instrument).filter(Instrument.symbol == "IEMG").one()
    )
    saved_price = (
        db_session.query(Price).filter(Price.instrument_id == instrument.id).one()
    )
    assert lookup_client.requests == ["IEMG"]
    assert market_data_client.requests == [("IEMG", "NYSEARCA", "USD")]
    assert instrument.name == "iShares Core MSCI Emerging Markets ETF"
    assert saved_price.close_price == Decimal("54.12000000")
    assert response.warnings == []
    assert response.simulated.instrument[0].label == "IEMG"
    assert response.simulated.instrument[0].market_value == Decimal("162.36000000")


def test_missing_profile_returns_404(
    authenticated_user: AuthenticatedUser,
    db_session: Session,
) -> None:
    with pytest.raises(HTTPException) as exc_info:
        simulate_portfolio(
            simulate_payload(
                TradeLeg(symbol="VOO", action="buy", quantity=Decimal("1"))
            ),
            authenticated_user,
            db_session,
            empty_lookup_client(),
            empty_market_data_client(),
        )

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Profile not found"
