from datetime import date
from decimal import Decimal
from types import SimpleNamespace

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


class EmptyHistory:
    empty = True


class FakeTicker:
    fast_info = {"currency": "usd"}

    def __init__(self, symbol: str) -> None:
        self.symbol = symbol

    def history(self, period: str) -> FakeHistory:
        assert period == "7d"
        return FakeHistory()


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
