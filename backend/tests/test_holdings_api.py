from datetime import date
from decimal import Decimal

import pytest
from fastapi import HTTPException, Response
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.v1.holdings import (
    add_holding,
    edit_holding,
    list_holdings,
    read_holding,
    remove_holding,
    router,
)
from app.core.auth import AuthenticatedUser, get_current_user
from app.data.models import Holding, Instrument
from app.data.repositories.prices import get_latest_prices_for_instruments
from app.integrations.market_data import MarketPrice
from app.main import app
from app.schemas.holdings import HoldingRequest
from app.schemas.instruments import InstrumentSearchResult


class FakeInstrumentLookupClient:
    def __init__(
        self,
        profile_result: InstrumentSearchResult | None = None,
        should_raise: bool = False,
    ) -> None:
        self.profile_result = profile_result
        self.should_raise = should_raise
        self.profile_symbols: list[str] = []

    def profile(self, symbol: str) -> InstrumentSearchResult | None:
        self.profile_symbols.append(symbol)
        if self.should_raise:
            raise RuntimeError("provider down")
        return self.profile_result


class FakeMarketDataClient:
    def __init__(
        self,
        price: MarketPrice | None = None,
        should_raise: bool = False,
    ) -> None:
        self.price = price
        self.should_raise = should_raise
        self.requests: list[tuple[str, str, str | None]] = []

    def get_latest_close(
        self,
        symbol: str,
        exchange: str,
        currency_hint: str | None,
    ) -> MarketPrice | None:
        self.requests.append((symbol, exchange, currency_hint))
        if self.should_raise:
            raise RuntimeError("provider down")
        return self.price


def market_price(
    symbol: str,
    close_price: str = "500.25",
) -> MarketPrice:
    return MarketPrice(
        symbol=symbol,
        exchange="NYSEARCA",
        price_date=date(2026, 6, 5),
        close_price=Decimal(close_price),
        currency="USD",
        source="fake",
    )


def holding_payload(**overrides: object) -> HoldingRequest:
    payload: dict[str, object] = {
        "symbol": " voo ",
        "name": " Vanguard S&P 500 ETF ",
        "exchange": " nysearca ",
        "currency": "usd",
        "asset_class": " ETF ",
        "sector": " Broad Market ",
        "country": " United States ",
        "region": " North America ",
        "quantity": "12.5",
        "average_cost": "418.23",
    }
    payload.update(overrides)
    return HoldingRequest.model_validate(payload)


def profile_result(**overrides: object) -> InstrumentSearchResult:
    payload: dict[str, object] = {
        "symbol": "VOO",
        "name": "Vanguard S&P 500 ETF",
        "exchange": "NYSEARCA",
        "currency": "USD",
        "asset_class": "ETF",
        "sector": "Broad Market",
        "country": "United States",
        "region": "North America",
        "source": "fmp",
    }
    payload.update(overrides)
    return InstrumentSearchResult.model_validate(payload)


def save_holding(
    payload: HoldingRequest,
    authenticated_user: AuthenticatedUser,
    db_session: Session,
    lookup_client: FakeInstrumentLookupClient | None = None,
    market_data_client: FakeMarketDataClient | None = None,
):
    return add_holding(
        payload,
        authenticated_user,
        db_session,
        lookup_client or FakeInstrumentLookupClient(),
        market_data_client or FakeMarketDataClient(),
    )


def save_holding_update(
    holding_id: int,
    payload: HoldingRequest,
    authenticated_user: AuthenticatedUser,
    db_session: Session,
    lookup_client: FakeInstrumentLookupClient | None = None,
):
    return edit_holding(
        holding_id,
        payload,
        authenticated_user,
        db_session,
        lookup_client or FakeInstrumentLookupClient(),
    )


def test_holdings_routes_require_auth() -> None:
    route_paths = {getattr(route, "path", None) for route in app.routes}

    assert {"/api/v1/holdings", "/api/v1/holdings/{holding_id}"}.issubset(
        route_paths
    )
    for route in router.routes:
        dependency_calls = {
            dependency.call for dependency in route.dependant.dependencies
        }
        assert get_current_user in dependency_calls


def test_creating_holding_inserts_and_reuses_instrument(
    authenticated_user: AuthenticatedUser,
    db_session: Session,
) -> None:
    first_response = save_holding(holding_payload(), authenticated_user, db_session)
    second_response = save_holding(
        holding_payload(quantity="3"),
        authenticated_user,
        db_session,
    )

    instrument_count = db_session.scalar(select(func.count()).select_from(Instrument))
    holding_count = db_session.scalar(select(func.count()).select_from(Holding))

    assert instrument_count == 1
    assert holding_count == 2
    assert first_response.instrument.id == second_response.instrument.id
    assert first_response.instrument.symbol == "VOO"
    assert first_response.instrument.exchange == "NYSEARCA"
    assert first_response.instrument.currency == "USD"


def test_creating_first_holding_fetches_instrument_price(
    authenticated_user: AuthenticatedUser,
    db_session: Session,
) -> None:
    client = FakeMarketDataClient(market_price("VOO"))

    response = save_holding(
        holding_payload(),
        authenticated_user,
        db_session,
        market_data_client=client,
    )

    saved = get_latest_prices_for_instruments(
        db_session,
        [response.instrument.id],
    )
    assert saved[response.instrument.id].close_price == Decimal("500.25")
    assert client.requests == [("VOO", "NYSEARCA", "USD")]


def test_creating_later_holding_reuses_existing_instrument_price(
    authenticated_user: AuthenticatedUser,
    db_session: Session,
) -> None:
    client = FakeMarketDataClient(market_price("VOO"))

    save_holding(
        holding_payload(),
        authenticated_user,
        db_session,
        market_data_client=client,
    )
    save_holding(
        holding_payload(quantity="3"),
        authenticated_user,
        db_session,
        market_data_client=client,
    )

    assert client.requests == [("VOO", "NYSEARCA", "USD")]


def test_creating_holding_continues_when_price_lookup_fails(
    authenticated_user: AuthenticatedUser,
    db_session: Session,
) -> None:
    client = FakeMarketDataClient(should_raise=True)

    response = save_holding(
        holding_payload(),
        authenticated_user,
        db_session,
        market_data_client=client,
    )

    assert response.instrument.symbol == "VOO"
    assert client.requests == [("VOO", "NYSEARCA", "USD")]
    assert get_latest_prices_for_instruments(
        db_session,
        [response.instrument.id],
    ) == {}


def test_creating_holding_enriches_missing_metadata_from_profile(
    authenticated_user: AuthenticatedUser,
    db_session: Session,
) -> None:
    lookup_client = FakeInstrumentLookupClient(profile_result())

    response = save_holding(
        holding_payload(name=None, sector=None, country=None, region=None),
        authenticated_user,
        db_session,
        lookup_client,
    )

    assert lookup_client.profile_symbols == ["VOO"]
    assert response.instrument.name == "Vanguard S&P 500 ETF"
    assert response.instrument.sector == "Broad Market"
    assert response.instrument.country == "United States"
    assert response.instrument.region == "North America"


def test_creating_existing_complete_instrument_skips_profile_lookup(
    authenticated_user: AuthenticatedUser,
    db_session: Session,
) -> None:
    db_session.add(
        Instrument(
            symbol="TSM",
            name="Taiwan Semiconductor Manufacturing Company Limited",
            exchange="NYSE",
            currency="USD",
            asset_class="ADR",
            sector="Technology",
            country="TW",
            region="Asia",
        )
    )
    db_session.commit()
    lookup_client = FakeInstrumentLookupClient(profile_result(symbol="TSM"))

    response = save_holding(
        holding_payload(
            symbol="TSM",
            name=None,
            exchange="",
            currency=None,
            asset_class=None,
            sector=None,
            country=None,
            region=None,
        ),
        authenticated_user,
        db_session,
        lookup_client,
    )

    assert lookup_client.profile_symbols == []
    assert response.instrument.exchange == "NYSE"
    assert response.instrument.asset_class == "ADR"
    assert response.instrument.region == "Asia"


def test_creating_existing_complete_etf_refreshes_profile_metadata(
    authenticated_user: AuthenticatedUser,
    db_session: Session,
) -> None:
    db_session.add(
        Instrument(
            symbol="IXC",
            name="iShares Global Energy ETF",
            exchange="NYSEARCA",
            currency="USD",
            asset_class="ETF",
            sector="Financial Services",
            country="US",
            region="North America",
        )
    )
    db_session.commit()
    lookup_client = FakeInstrumentLookupClient(
        profile_result(
            symbol="IXC",
            name="iShares Global Energy ETF",
            exchange="NYSEARCA",
            currency="USD",
            asset_class="ETF",
            sector="Energy",
            country="US",
            region="Global",
            source="fmp+alphavantage",
        )
    )

    response = save_holding(
        holding_payload(
            symbol="IXC",
            name=None,
            sector=None,
            country=None,
            region=None,
        ),
        authenticated_user,
        db_session,
        lookup_client,
    )

    assert lookup_client.profile_symbols == ["IXC"]
    assert response.instrument.sector == "Energy"
    assert response.instrument.region == "Global"


def test_creating_existing_incomplete_instrument_enriches_once(
    authenticated_user: AuthenticatedUser,
    db_session: Session,
) -> None:
    db_session.add(
        Instrument(
            symbol="TSM",
            name="Taiwan Semiconductor Manufacturing Company Limited",
            exchange="NYSE",
            currency="USD",
            asset_class=None,
            sector=None,
            country=None,
            region=None,
        )
    )
    db_session.commit()
    lookup_client = FakeInstrumentLookupClient(
        profile_result(
            symbol="TSM",
            name="Taiwan Semiconductor Manufacturing Company Limited",
            exchange="NYSE",
            currency="USD",
            asset_class="ADR",
            sector="Technology",
            country="TW",
            region="Asia",
        )
    )

    response = save_holding(
        holding_payload(
            symbol="TSM",
            name=None,
            exchange="",
            currency=None,
            asset_class=None,
            sector=None,
            country=None,
            region=None,
        ),
        authenticated_user,
        db_session,
        lookup_client,
    )

    assert lookup_client.profile_symbols == ["TSM"]
    assert response.instrument.asset_class == "ADR"
    assert response.instrument.sector == "Technology"


def test_creating_holding_continues_when_profile_lookup_fails(
    authenticated_user: AuthenticatedUser,
    db_session: Session,
) -> None:
    lookup_client = FakeInstrumentLookupClient(should_raise=True)

    response = save_holding(
        holding_payload(sector=None, country=None, region=None),
        authenticated_user,
        db_session,
        lookup_client,
    )

    assert lookup_client.profile_symbols == ["VOO"]
    assert response.instrument.symbol == "VOO"
    assert response.instrument.sector is None


def test_listing_holdings_returns_only_authenticated_users_holdings(
    authenticated_user: AuthenticatedUser,
    second_user: AuthenticatedUser,
    db_session: Session,
) -> None:
    own_holding = save_holding(
        holding_payload(symbol="VOO"),
        authenticated_user,
        db_session,
    )
    save_holding(holding_payload(symbol="VXUS"), second_user, db_session)

    holdings = list_holdings(authenticated_user, db_session)

    assert [holding.id for holding in holdings] == [own_holding.id]


def test_getting_another_users_holding_returns_404(
    authenticated_user: AuthenticatedUser,
    second_user: AuthenticatedUser,
    db_session: Session,
) -> None:
    other_holding = save_holding(holding_payload(), second_user, db_session)

    with pytest.raises(HTTPException) as exc_info:
        read_holding(other_holding.id, authenticated_user, db_session)

    assert exc_info.value.status_code == 404


def test_updating_another_users_holding_returns_404(
    authenticated_user: AuthenticatedUser,
    second_user: AuthenticatedUser,
    db_session: Session,
) -> None:
    other_holding = save_holding(holding_payload(), second_user, db_session)

    with pytest.raises(HTTPException) as exc_info:
        save_holding_update(
            other_holding.id,
            holding_payload(quantity="5"),
            authenticated_user,
            db_session,
        )

    assert exc_info.value.status_code == 404


def test_deleting_another_users_holding_returns_404(
    authenticated_user: AuthenticatedUser,
    second_user: AuthenticatedUser,
    db_session: Session,
) -> None:
    other_holding = save_holding(holding_payload(), second_user, db_session)

    with pytest.raises(HTTPException) as exc_info:
        remove_holding(other_holding.id, authenticated_user, db_session)

    assert exc_info.value.status_code == 404


def test_updating_own_holding_changes_quantity_and_instrument(
    authenticated_user: AuthenticatedUser,
    db_session: Session,
) -> None:
    holding = save_holding(holding_payload(), authenticated_user, db_session)

    response = save_holding_update(
        holding.id,
        holding_payload(symbol="vxus", exchange="", quantity="7.25"),
        authenticated_user,
        db_session,
    )

    assert response.id == holding.id
    assert response.quantity == Decimal("7.25")
    assert response.instrument.symbol == "VXUS"
    assert response.instrument.exchange == ""


def test_deleting_own_holding_returns_204_and_removes_row(
    authenticated_user: AuthenticatedUser,
    db_session: Session,
) -> None:
    holding = save_holding(holding_payload(), authenticated_user, db_session)

    response = remove_holding(holding.id, authenticated_user, db_session)

    assert isinstance(response, Response)
    assert response.status_code == 204
    assert db_session.get(Holding, holding.id) is None


def test_invalid_quantity_or_average_cost_is_rejected() -> None:
    with pytest.raises(ValidationError):
        holding_payload(quantity="0")

    with pytest.raises(ValidationError):
        holding_payload(average_cost="-1")


def test_symbol_and_currency_are_normalized_in_responses(
    authenticated_user: AuthenticatedUser,
    db_session: Session,
) -> None:
    response = save_holding(
        holding_payload(symbol="voo", currency="usd"),
        authenticated_user,
        db_session,
    )

    assert response.instrument.symbol == "VOO"
    assert response.instrument.currency == "USD"
    assert response.model_dump(mode="json")["quantity"] == "12.50000000"
