from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.data.models import Holding, Instrument, Price
from app.data.repositories.prices import get_latest_prices_for_instruments
from app.domain.price_refresh import (
    ensure_instrument_has_price,
    refresh_prices_for_user,
)
from app.integrations.market_data import MarketDataClient, MarketPrice
from app.integrations.yfinance_client import YFinanceMarketDataClient


class FakeMarketDataClient:
    def get_latest_close(
        self,
        symbol: str,
        exchange: str,
        currency_hint: str | None,
    ) -> MarketPrice | None:
        return MarketPrice(
            symbol=symbol,
            exchange=exchange,
            price_date=date(2026, 6, 5),
            close_price=Decimal("500.25"),
            currency=currency_hint or "UNKNOWN",
            source="fake",
        )


class FakeHistory:
    empty = False

    @property
    def index(self) -> list[date]:
        return [date(2026, 6, 3), date(2026, 6, 4), date(2026, 6, 5)]

    def __getitem__(self, column_name: str) -> list[float | None]:
        assert column_name == "Close"
        return [498.12, None, 500.25]


class NanLatestHistory:
    empty = False

    @property
    def index(self) -> list[date]:
        return [date(2026, 6, 3), date(2026, 6, 4), date(2026, 6, 5)]

    def __getitem__(self, column_name: str) -> list[float | None]:
        assert column_name == "Close"
        return [498.12, 500.25, float("nan")]


class EmptyHistory:
    empty = True


class FakeTicker:
    fast_info = {"currency": "usd"}

    def __init__(self, symbol: str) -> None:
        self.symbol = symbol

    def history(self, period: str) -> FakeHistory:
        assert period == "7d"
        return FakeHistory()


class NanLatestTicker:
    fast_info = {"currency": "usd"}

    def __init__(self, symbol: str) -> None:
        self.symbol = symbol

    def history(self, period: str) -> NanLatestHistory:
        assert period == "7d"
        return NanLatestHistory()


class EmptyTicker:
    fast_info: dict[str, str] = {}

    def __init__(self, symbol: str) -> None:
        self.symbol = symbol

    def history(self, period: str) -> EmptyHistory:
        assert period == "7d"
        return EmptyHistory()


class CurrencyFallbackTicker:
    fast_info: dict[str, str] = {}

    def __init__(self, symbol: str) -> None:
        self.symbol = symbol

    def history(self, period: str) -> FakeHistory:
        assert period == "7d"
        return FakeHistory()


class ScriptedMarketDataClient:
    def __init__(
        self,
        prices: dict[str, MarketPrice | None],
        failing_symbols: set[str] | None = None,
    ) -> None:
        self.prices = prices
        self.failing_symbols = failing_symbols or set()
        self.requests: list[tuple[str, str, str | None]] = []

    def get_latest_close(
        self,
        symbol: str,
        exchange: str,
        currency_hint: str | None,
    ) -> MarketPrice | None:
        self.requests.append((symbol, exchange, currency_hint))
        if symbol in self.failing_symbols:
            raise RuntimeError("provider down")
        return self.prices.get(symbol)


class HistoricalReturnHistory:
    empty = False

    @property
    def index(self) -> list[date]:
        return [date(2021, 1, 4), date(2023, 6, 15), date(2026, 1, 2)]

    def __getitem__(self, column_name: str) -> list[float | None]:
        assert column_name == "Close"
        return [100.0, 150.0, 200.0]


class HistoricalReturnTicker:
    fast_info = {"currency": "usd"}

    def __init__(self, symbol: str) -> None:
        self.symbol = symbol

    def history(self, period: str) -> HistoricalReturnHistory:
        assert period == "5y"
        return HistoricalReturnHistory()


class ThinHistoryHistory:
    empty = False

    @property
    def index(self) -> list[date]:
        return [date(2024, 6, 1), date(2026, 1, 2)]

    def __getitem__(self, column_name: str) -> list[float | None]:
        assert column_name == "Close"
        return [100.0, 150.0]


class ThinHistoryTicker:
    fast_info: dict[str, str] = {}

    def __init__(self, symbol: str) -> None:
        self.symbol = symbol

    def history(self, period: str) -> ThinHistoryHistory:
        assert period == "5y"
        return ThinHistoryHistory()


class SingleValidCloseHistory:
    empty = False

    @property
    def index(self) -> list[date]:
        return [date(2021, 1, 4), date(2026, 1, 2)]

    def __getitem__(self, column_name: str) -> list[float | None]:
        assert column_name == "Close"
        return [float("nan"), 200.0]


class SingleValidCloseTicker:
    fast_info: dict[str, str] = {}

    def __init__(self, symbol: str) -> None:
        self.symbol = symbol

    def history(self, period: str) -> SingleValidCloseHistory:
        assert period == "5y"
        return SingleValidCloseHistory()


class EmptyHistoricalTicker:
    fast_info: dict[str, str] = {}

    def __init__(self, symbol: str) -> None:
        self.symbol = symbol

    def history(self, period: str) -> EmptyHistory:
        assert period == "5y"
        return EmptyHistory()


def add_holding(
    db_session: Session,
    user_id: str,
    instrument: Instrument,
    quantity: str = "1",
) -> Holding:
    holding = Holding(
        user_id=user_id,
        instrument=instrument,
        quantity=Decimal(quantity),
        average_cost=Decimal("100"),
    )
    db_session.add(holding)
    db_session.flush()
    return holding


def instrument(
    symbol: str,
    exchange: str = "NYSEARCA",
    currency: str | None = "USD",
) -> Instrument:
    return Instrument(
        symbol=symbol,
        name=f"{symbol} Fund",
        exchange=exchange,
        currency=currency,
        asset_class="ETF",
        sector="Broad Market",
        country="United States",
        region="North America",
    )


def market_price(
    symbol: str,
    close_price: str = "500.25",
    exchange: str = "NYSEARCA",
    currency: str = "USD",
    source: str = "fake",
) -> MarketPrice:
    return MarketPrice(
        symbol=symbol,
        exchange=exchange,
        price_date=date(2026, 6, 5),
        close_price=Decimal(close_price),
        currency=currency,
        source=source,
    )


def test_fake_market_data_client_satisfies_protocol() -> None:
    client: MarketDataClient = FakeMarketDataClient()

    price = client.get_latest_close("VOO", "NYSEARCA", "USD")

    assert price == MarketPrice(
        symbol="VOO",
        exchange="NYSEARCA",
        price_date=date(2026, 6, 5),
        close_price=Decimal("500.25"),
        currency="USD",
        source="fake",
    )


def test_ensure_instrument_price_fetches_and_stores_first_price(
    db_session: Session,
) -> None:
    held_instrument = instrument("INDA")
    db_session.add(held_instrument)
    db_session.commit()
    client = ScriptedMarketDataClient({"INDA": market_price("INDA", "44.50")})

    updated = ensure_instrument_has_price(db_session, held_instrument, client)

    saved = get_latest_prices_for_instruments(
        db_session,
        [held_instrument.id],
    )[held_instrument.id]
    assert updated is True
    assert saved.close_price == Decimal("44.50")
    assert client.requests == [("INDA", "NYSEARCA", "USD")]


def test_ensure_instrument_price_reuses_existing_price(
    db_session: Session,
) -> None:
    held_instrument = instrument("INDA")
    db_session.add(held_instrument)
    db_session.flush()
    db_session.add(
        Price(
            instrument=held_instrument,
            price_date=date(2026, 6, 4),
            close_price=Decimal("43.00"),
            currency="USD",
            source="fake",
        )
    )
    db_session.commit()
    client = ScriptedMarketDataClient({"INDA": market_price("INDA", "44.50")})

    updated = ensure_instrument_has_price(db_session, held_instrument, client)

    assert updated is False
    assert client.requests == []


def test_ensure_instrument_price_is_non_blocking_on_provider_failure(
    db_session: Session,
) -> None:
    held_instrument = instrument("INDA")
    db_session.add(held_instrument)
    db_session.commit()
    client = ScriptedMarketDataClient({}, failing_symbols={"INDA"})

    updated = ensure_instrument_has_price(db_session, held_instrument, client)

    assert updated is False
    assert get_latest_prices_for_instruments(db_session, [held_instrument.id]) == {}


def test_ensure_instrument_price_skips_missing_provider_price(
    db_session: Session,
) -> None:
    held_instrument = instrument("INDA")
    db_session.add(held_instrument)
    db_session.commit()
    client = ScriptedMarketDataClient({"INDA": None})

    updated = ensure_instrument_has_price(db_session, held_instrument, client)

    assert updated is False
    assert get_latest_prices_for_instruments(db_session, [held_instrument.id]) == {}


def test_ensure_instrument_price_skips_non_finite_provider_price(
    db_session: Session,
) -> None:
    held_instrument = instrument("INDA")
    db_session.add(held_instrument)
    db_session.commit()
    client = ScriptedMarketDataClient(
        {"INDA": market_price("INDA", "NaN")},
    )

    updated = ensure_instrument_has_price(db_session, held_instrument, client)

    assert updated is False
    assert get_latest_prices_for_instruments(db_session, [held_instrument.id]) == {}


def test_yfinance_adapter_parses_latest_non_null_close() -> None:
    client = YFinanceMarketDataClient(
        yfinance_module=SimpleNamespace(Ticker=FakeTicker),
    )

    price = client.get_latest_close("voo", "nysearca", "USD")

    assert price == MarketPrice(
        symbol="VOO",
        exchange="NYSEARCA",
        price_date=date(2026, 6, 5),
        close_price=Decimal("500.25"),
        currency="USD",
        source="yfinance",
    )


def test_yfinance_adapter_skips_nan_close_values() -> None:
    client = YFinanceMarketDataClient(
        yfinance_module=SimpleNamespace(Ticker=NanLatestTicker),
    )

    price = client.get_latest_close("voo", "nysearca", "USD")

    assert price is not None
    assert price.price_date == date(2026, 6, 4)
    assert price.close_price == Decimal("500.25")


def test_yfinance_adapter_returns_none_for_empty_history() -> None:
    client = YFinanceMarketDataClient(
        yfinance_module=SimpleNamespace(Ticker=EmptyTicker),
    )

    assert client.get_latest_close("VOO", "NYSEARCA", "USD") is None


def test_yfinance_adapter_uses_currency_hint_when_provider_currency_missing() -> None:
    client = YFinanceMarketDataClient(
        yfinance_module=SimpleNamespace(Ticker=CurrencyFallbackTicker),
    )

    price = client.get_latest_close("VOO", "NYSEARCA", "eur")

    assert price is not None
    assert price.currency == "EUR"


def test_yfinance_adapter_computes_annualized_return_over_full_history() -> None:
    client = YFinanceMarketDataClient(
        yfinance_module=SimpleNamespace(Ticker=HistoricalReturnTicker),
    )

    annualized_return = client.get_historical_annualized_return(
        "voo", "nysearca", "USD"
    )

    assert annualized_return == Decimal("14.89")


def test_yfinance_adapter_returns_none_when_history_spans_under_three_years() -> None:
    client = YFinanceMarketDataClient(
        yfinance_module=SimpleNamespace(Ticker=ThinHistoryTicker),
    )

    assert client.get_historical_annualized_return("VOO", "NYSEARCA", "USD") is None


def test_yfinance_adapter_returns_none_with_fewer_than_two_valid_closes() -> None:
    client = YFinanceMarketDataClient(
        yfinance_module=SimpleNamespace(Ticker=SingleValidCloseTicker),
    )

    assert client.get_historical_annualized_return("VOO", "NYSEARCA", "USD") is None


def test_yfinance_adapter_historical_return_none_for_empty_history() -> None:
    client = YFinanceMarketDataClient(
        yfinance_module=SimpleNamespace(Ticker=EmptyHistoricalTicker),
    )

    assert client.get_historical_annualized_return("VOO", "NYSEARCA", "USD") is None


def test_refresh_requests_each_distinct_user_instrument_once(
    db_session: Session,
) -> None:
    voo = instrument("VOO")
    vxus = instrument("VXUS")
    other_user_instrument = instrument("BND")
    db_session.add_all([voo, vxus, other_user_instrument])
    db_session.flush()
    add_holding(db_session, "user-123", voo)
    add_holding(db_session, "user-123", vxus)
    add_holding(db_session, "user-456", other_user_instrument)
    db_session.commit()
    client = ScriptedMarketDataClient(
        {
            "VOO": market_price("VOO"),
            "VXUS": market_price("VXUS", close_price="65.12"),
        }
    )

    result = refresh_prices_for_user(db_session, "user-123", client)

    assert result.requested == 2
    assert result.updated == 2
    assert result.skipped == 0
    assert result.failed == 0
    assert client.requests == [
        ("VOO", "NYSEARCA", "USD"),
        ("VXUS", "NYSEARCA", "USD"),
    ]
    assert db_session.scalar(select(func.count()).select_from(Price)) == 2


def test_refresh_updates_existing_same_day_price_from_same_source(
    db_session: Session,
) -> None:
    voo = instrument("VOO")
    db_session.add(voo)
    db_session.flush()
    add_holding(db_session, "user-123", voo)
    db_session.add(
        Price(
            instrument=voo,
            price_date=date(2026, 6, 5),
            close_price=Decimal("499.00"),
            currency="USD",
            source="fake",
        )
    )
    db_session.commit()
    client = ScriptedMarketDataClient(
        {
            "VOO": market_price("VOO"),
        }
    )

    result = refresh_prices_for_user(db_session, "user-123", client)

    saved_price = db_session.scalar(select(Price).where(Price.instrument_id == voo.id))
    assert result.updated == 1
    assert db_session.scalar(select(func.count()).select_from(Price)) == 1
    assert saved_price is not None
    assert saved_price.close_price == Decimal("500.25000000")


def test_get_latest_prices_for_instruments_returns_newest_per_instrument(
    db_session: Session,
) -> None:
    voo = instrument("VOO")
    vxus = instrument("VXUS")
    db_session.add_all([voo, vxus])
    db_session.flush()
    db_session.add_all(
        [
            Price(
                instrument=voo,
                price_date=date(2026, 6, 4),
                close_price=Decimal("499.00"),
                currency="USD",
                source="fake",
            ),
            Price(
                instrument=voo,
                price_date=date(2026, 6, 5),
                close_price=Decimal("500.25"),
                currency="USD",
                source="fake",
            ),
            Price(
                instrument=vxus,
                price_date=date(2026, 6, 3),
                close_price=Decimal("64.50"),
                currency="USD",
                source="fake",
            ),
        ]
    )
    db_session.commit()

    latest_prices = get_latest_prices_for_instruments(
        db_session,
        [voo.id, vxus.id],
    )

    assert latest_prices[voo.id].close_price == Decimal("500.25000000")
    assert latest_prices[vxus.id].close_price == Decimal("64.50000000")


def test_refresh_counts_missing_and_failed_provider_results(
    db_session: Session,
) -> None:
    voo = instrument("VOO")
    vxus = instrument("VXUS")
    bnd = instrument("BND")
    db_session.add_all([voo, vxus, bnd])
    db_session.flush()
    add_holding(db_session, "user-123", voo)
    add_holding(db_session, "user-123", vxus)
    add_holding(db_session, "user-123", bnd)
    db_session.commit()
    client = ScriptedMarketDataClient(
        {
            "VOO": market_price("VOO"),
            "VXUS": None,
        },
        failing_symbols={"BND"},
    )

    result = refresh_prices_for_user(db_session, "user-123", client)

    assert result.requested == 3
    assert result.updated == 1
    assert result.skipped == 1
    assert result.failed == 1
    assert db_session.scalar(select(func.count()).select_from(Price)) == 1


def test_refresh_skips_non_finite_provider_prices(
    db_session: Session,
) -> None:
    voo = instrument("VOO")
    db_session.add(voo)
    db_session.flush()
    add_holding(db_session, "user-123", voo)
    db_session.commit()
    client = ScriptedMarketDataClient(
        {
            "VOO": market_price("VOO", close_price="NaN"),
        }
    )

    result = refresh_prices_for_user(db_session, "user-123", client)

    assert result.requested == 1
    assert result.updated == 0
    assert result.skipped == 1
    assert result.failed == 0
    assert db_session.scalar(select(func.count()).select_from(Price)) == 0
