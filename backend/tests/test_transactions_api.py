from datetime import date
from decimal import Decimal

import pytest
from fastapi import HTTPException, Response
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.api.v1.transactions import (
    add_transaction,
    edit_transaction,
    list_transactions,
    read_transaction,
    remove_transaction,
    router,
)
from app.core.auth import AuthenticatedUser, get_current_user
from app.data.models import Instrument
from app.data.repositories.prices import get_latest_prices_for_instruments
from app.integrations.market_data import MarketPrice
from app.main import app
from app.schemas.instruments import InstrumentSearchResult
from app.schemas.transactions import TransactionRequest


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


def market_price(symbol: str, close_price: str = "500.25") -> MarketPrice:
    return MarketPrice(
        symbol=symbol,
        exchange="NYSEARCA",
        price_date=date(2026, 6, 5),
        close_price=Decimal(close_price),
        currency="USD",
        source="fake",
    )


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


def rich_payload(**overrides: object) -> TransactionRequest:
    payload: dict[str, object] = {
        "symbol": "voo",
        "name": " Vanguard S&P 500 ETF ",
        "exchange": " nysearca ",
        "currency": "usd",
        "asset_class": " ETF ",
        "sector": " Broad Market ",
        "country": " United States ",
        "region": " North America ",
        "action": "buy",
        "quantity": "10",
        "price": "100",
        "fees": "1",
        "trade_date": date(2026, 1, 1),
        "notes": "opening",
    }
    payload.update(overrides)
    return TransactionRequest.model_validate(payload)


def bare_symbol_payload(**overrides: object) -> TransactionRequest:
    payload: dict[str, object] = {
        "symbol": "voo",
        "action": "buy",
        "quantity": "10",
        "price": "100",
        "trade_date": date(2026, 1, 1),
    }
    payload.update(overrides)
    return TransactionRequest.model_validate(payload)


def instrument_id_payload(
    instrument_id: int,
    **overrides: object,
) -> TransactionRequest:
    payload: dict[str, object] = {
        "instrument_id": instrument_id,
        "action": "buy",
        "quantity": "10",
        "price": "100",
        "trade_date": date(2026, 1, 1),
    }
    payload.update(overrides)
    return TransactionRequest.model_validate(payload)


def save_transaction(
    payload: TransactionRequest,
    authenticated_user: AuthenticatedUser,
    db_session: Session,
    lookup_client: FakeInstrumentLookupClient | None = None,
    market_data_client: FakeMarketDataClient | None = None,
):
    return add_transaction(
        payload,
        authenticated_user,
        db_session,
        lookup_client or FakeInstrumentLookupClient(),
        market_data_client or FakeMarketDataClient(),
    )


def save_transaction_update(
    transaction_id: int,
    payload: TransactionRequest,
    authenticated_user: AuthenticatedUser,
    db_session: Session,
    lookup_client: FakeInstrumentLookupClient | None = None,
):
    return edit_transaction(
        transaction_id,
        payload,
        authenticated_user,
        db_session,
        lookup_client or FakeInstrumentLookupClient(),
    )


def make_instrument(db_session: Session, **overrides: object) -> Instrument:
    fields: dict[str, object] = {
        "symbol": "VOO",
        "name": "Vanguard S&P 500 ETF",
        "exchange": "NYSEARCA",
        "currency": "USD",
        "asset_class": "ETF",
        "sector": "Broad Market",
        "country": "United States",
        "region": "North America",
    }
    fields.update(overrides)
    instrument = Instrument(**fields)
    db_session.add(instrument)
    db_session.commit()
    db_session.refresh(instrument)
    return instrument


def test_transactions_routes_require_auth() -> None:
    route_paths = {getattr(route, "path", None) for route in app.routes}

    assert {"/api/v1/transactions", "/api/v1/transactions/{transaction_id}"}.issubset(
        route_paths
    )
    for route in router.routes:
        dependency_calls = {
            dependency.call for dependency in route.dependant.dependencies
        }
        assert get_current_user in dependency_calls


# -- Instrument resolution ---------------------------------------------------


def test_creating_transaction_with_instrument_id_resolves_directly(
    authenticated_user: AuthenticatedUser,
    db_session: Session,
) -> None:
    instrument = make_instrument(db_session)
    lookup_client = FakeInstrumentLookupClient()

    response = save_transaction(
        instrument_id_payload(instrument.id),
        authenticated_user,
        db_session,
        lookup_client,
    )

    assert response.instrument.id == instrument.id
    assert lookup_client.profile_symbols == []


def test_creating_transaction_with_unknown_instrument_id_returns_404(
    authenticated_user: AuthenticatedUser,
    db_session: Session,
) -> None:
    with pytest.raises(HTTPException) as exc_info:
        save_transaction(
            instrument_id_payload(999),
            authenticated_user,
            db_session,
        )

    assert exc_info.value.status_code == 404


def test_creating_transaction_with_rich_symbol_creates_instrument_without_lookup(
    authenticated_user: AuthenticatedUser,
    db_session: Session,
) -> None:
    lookup_client = FakeInstrumentLookupClient()

    response = save_transaction(
        rich_payload(),
        authenticated_user,
        db_session,
        lookup_client,
    )

    assert lookup_client.profile_symbols == []
    assert response.instrument.symbol == "VOO"
    assert response.instrument.exchange == "NYSEARCA"
    assert response.instrument.currency == "USD"
    assert response.instrument.sector == "Broad Market"


def test_creating_transaction_with_bare_symbol_reuses_local_instrument(
    authenticated_user: AuthenticatedUser,
    db_session: Session,
) -> None:
    instrument = make_instrument(db_session)
    lookup_client = FakeInstrumentLookupClient()

    response = save_transaction(
        bare_symbol_payload(symbol="voo"),
        authenticated_user,
        db_session,
        lookup_client,
    )

    assert response.instrument.id == instrument.id
    assert lookup_client.profile_symbols == []


def test_creating_transaction_with_bare_symbol_falls_back_to_lookup_client(
    authenticated_user: AuthenticatedUser,
    db_session: Session,
) -> None:
    lookup_client = FakeInstrumentLookupClient(profile_result())

    response = save_transaction(
        bare_symbol_payload(symbol="voo"),
        authenticated_user,
        db_session,
        lookup_client,
    )

    assert lookup_client.profile_symbols == ["VOO"]
    assert response.instrument.symbol == "VOO"
    assert response.instrument.sector == "Broad Market"


def test_creating_transaction_with_unresolvable_bare_symbol_returns_404(
    authenticated_user: AuthenticatedUser,
    db_session: Session,
) -> None:
    lookup_client = FakeInstrumentLookupClient(profile_result=None)

    with pytest.raises(HTTPException) as exc_info:
        save_transaction(
            bare_symbol_payload(symbol="zzz"),
            authenticated_user,
            db_session,
            lookup_client,
        )

    assert exc_info.value.status_code == 404


def test_creating_transaction_fetches_instrument_price(
    authenticated_user: AuthenticatedUser,
    db_session: Session,
) -> None:
    market_data_client = FakeMarketDataClient(market_price("VOO"))

    response = save_transaction(
        rich_payload(),
        authenticated_user,
        db_session,
        market_data_client=market_data_client,
    )

    saved = get_latest_prices_for_instruments(db_session, [response.instrument.id])
    assert saved[response.instrument.id].close_price == Decimal("500.25")
    assert market_data_client.requests == [("VOO", "NYSEARCA", "USD")]


def test_currency_falls_back_to_usd_when_instrument_currency_missing(
    authenticated_user: AuthenticatedUser,
    db_session: Session,
) -> None:
    response = save_transaction(
        bare_symbol_payload(symbol="zzz"),
        authenticated_user,
        db_session,
        FakeInstrumentLookupClient(profile_result(symbol="ZZZ", currency=None)),
    )

    assert response.currency == "USD"


# -- Create / list / update / delete -----------------------------------------


def test_creating_transaction_returns_201_response(
    authenticated_user: AuthenticatedUser,
    db_session: Session,
) -> None:
    response = save_transaction(rich_payload(), authenticated_user, db_session)

    assert response.action == "buy"
    assert response.quantity == Decimal("10")
    assert response.price == Decimal("100")
    assert response.fees == Decimal("1")
    assert response.notes == "opening"
    assert response.model_dump(mode="json")["quantity"] == "10.00000000"


def test_listing_transactions_scoped_to_user(
    authenticated_user: AuthenticatedUser,
    second_user: AuthenticatedUser,
    db_session: Session,
) -> None:
    mine = save_transaction(rich_payload(), authenticated_user, db_session)
    save_transaction(rich_payload(symbol="vxus"), second_user, db_session)

    transactions = list_transactions(authenticated_user, db_session, None, None)

    assert [transaction.id for transaction in transactions] == [mine.id]


def test_listing_transactions_orders_by_trade_date_then_id_descending(
    authenticated_user: AuthenticatedUser,
    db_session: Session,
) -> None:
    first = save_transaction(
        rich_payload(trade_date=date(2026, 1, 1)),
        authenticated_user,
        db_session,
    )
    second = save_transaction(
        rich_payload(trade_date=date(2026, 1, 3)),
        authenticated_user,
        db_session,
    )
    third = save_transaction(
        rich_payload(trade_date=date(2026, 1, 3)),
        authenticated_user,
        db_session,
    )

    transactions = list_transactions(authenticated_user, db_session, None, None)

    assert [t.id for t in transactions] == [third.id, second.id, first.id]


def test_listing_transactions_filters_by_instrument_id(
    authenticated_user: AuthenticatedUser,
    db_session: Session,
) -> None:
    voo = save_transaction(rich_payload(), authenticated_user, db_session)
    save_transaction(rich_payload(symbol="vxus"), authenticated_user, db_session)

    transactions = list_transactions(
        authenticated_user,
        db_session,
        voo.instrument.id,
        None,
    )

    assert [t.id for t in transactions] == [voo.id]


def test_listing_transactions_filters_by_symbol(
    authenticated_user: AuthenticatedUser,
    db_session: Session,
) -> None:
    voo = save_transaction(rich_payload(), authenticated_user, db_session)
    save_transaction(rich_payload(symbol="vxus"), authenticated_user, db_session)

    transactions = list_transactions(authenticated_user, db_session, None, "voo")

    assert [t.id for t in transactions] == [voo.id]


def test_listing_transactions_rejects_both_filters(
    authenticated_user: AuthenticatedUser,
    db_session: Session,
) -> None:
    with pytest.raises(HTTPException) as exc_info:
        list_transactions(authenticated_user, db_session, 1, "voo")

    assert exc_info.value.status_code == 422


def test_getting_another_users_transaction_returns_404(
    authenticated_user: AuthenticatedUser,
    second_user: AuthenticatedUser,
    db_session: Session,
) -> None:
    other = save_transaction(rich_payload(), second_user, db_session)

    with pytest.raises(HTTPException) as exc_info:
        read_transaction(other.id, authenticated_user, db_session)

    assert exc_info.value.status_code == 404


def test_updating_another_users_transaction_returns_404(
    authenticated_user: AuthenticatedUser,
    second_user: AuthenticatedUser,
    db_session: Session,
) -> None:
    other = save_transaction(rich_payload(), second_user, db_session)

    with pytest.raises(HTTPException) as exc_info:
        save_transaction_update(
            other.id,
            rich_payload(quantity="5"),
            authenticated_user,
            db_session,
        )

    assert exc_info.value.status_code == 404


def test_deleting_another_users_transaction_returns_404(
    authenticated_user: AuthenticatedUser,
    second_user: AuthenticatedUser,
    db_session: Session,
) -> None:
    other = save_transaction(rich_payload(), second_user, db_session)

    with pytest.raises(HTTPException) as exc_info:
        remove_transaction(other.id, authenticated_user, db_session)

    assert exc_info.value.status_code == 404


def test_updating_own_transaction_changes_quantity(
    authenticated_user: AuthenticatedUser,
    db_session: Session,
) -> None:
    transaction = save_transaction(rich_payload(), authenticated_user, db_session)

    updated = save_transaction_update(
        transaction.id,
        rich_payload(quantity="20"),
        authenticated_user,
        db_session,
    )

    assert updated.quantity == Decimal("20")


def test_deleting_own_transaction_returns_204(
    authenticated_user: AuthenticatedUser,
    db_session: Session,
) -> None:
    transaction = save_transaction(rich_payload(), authenticated_user, db_session)

    response = remove_transaction(transaction.id, authenticated_user, db_session)

    assert isinstance(response, Response)
    assert response.status_code == 204


# -- Oversell handling --------------------------------------------------------


def test_creating_oversell_transaction_returns_422(
    authenticated_user: AuthenticatedUser,
    db_session: Session,
) -> None:
    save_transaction(
        rich_payload(action="buy", quantity="10"),
        authenticated_user,
        db_session,
    )

    with pytest.raises(HTTPException) as exc_info:
        save_transaction(
            rich_payload(action="sell", quantity="20", trade_date=date(2026, 1, 2)),
            authenticated_user,
            db_session,
        )

    assert exc_info.value.status_code == 422


def test_updating_transaction_to_oversell_returns_422(
    authenticated_user: AuthenticatedUser,
    db_session: Session,
) -> None:
    save_transaction(
        rich_payload(action="buy", quantity="10"),
        authenticated_user,
        db_session,
    )
    sell = save_transaction(
        rich_payload(action="sell", quantity="5", trade_date=date(2026, 1, 2)),
        authenticated_user,
        db_session,
    )

    with pytest.raises(HTTPException) as exc_info:
        save_transaction_update(
            sell.id,
            rich_payload(
                action="sell",
                quantity="50",
                trade_date=date(2026, 1, 2),
            ),
            authenticated_user,
            db_session,
        )

    assert exc_info.value.status_code == 422


def test_deleting_transaction_that_would_go_negative_returns_422(
    authenticated_user: AuthenticatedUser,
    db_session: Session,
) -> None:
    first_buy = save_transaction(
        rich_payload(action="buy", quantity="10"),
        authenticated_user,
        db_session,
    )
    save_transaction(
        rich_payload(action="sell", quantity="10", trade_date=date(2026, 1, 2)),
        authenticated_user,
        db_session,
    )

    with pytest.raises(HTTPException) as exc_info:
        remove_transaction(first_buy.id, authenticated_user, db_session)

    assert exc_info.value.status_code == 422


# -- Schema validation --------------------------------------------------------


def test_invalid_quantity_price_or_fees_is_rejected() -> None:
    with pytest.raises(ValidationError):
        rich_payload(quantity="0")

    with pytest.raises(ValidationError):
        rich_payload(price="-1")

    with pytest.raises(ValidationError):
        rich_payload(fees="-1")


def test_requires_exactly_one_of_instrument_id_or_symbol() -> None:
    with pytest.raises(ValidationError):
        TransactionRequest.model_validate(
            {
                "action": "buy",
                "quantity": "1",
                "price": "1",
                "trade_date": date(2026, 1, 1),
            }
        )

    with pytest.raises(ValidationError):
        TransactionRequest.model_validate(
            {
                "instrument_id": 1,
                "symbol": "voo",
                "action": "buy",
                "quantity": "1",
                "price": "1",
                "trade_date": date(2026, 1, 1),
            }
        )
