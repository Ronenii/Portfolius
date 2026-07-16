from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any

from app.integrations.market_data import MarketPrice


def normalize_code(value: str | None, fallback: str = "UNKNOWN") -> str:
    if value is None:
        return fallback
    normalized_value = value.strip().upper()
    return normalized_value or fallback


HISTORICAL_RETURN_PERIOD = "5y"
MIN_HISTORICAL_YEARS = Decimal("3")
DAYS_PER_YEAR = Decimal("365.25")
RETURN_QUANTIZE = Decimal("0.01")


class YFinanceMarketDataClient:
    def __init__(self, yfinance_module: Any | None = None) -> None:
        self._yfinance_module = yfinance_module

    @property
    def yfinance_module(self) -> Any:
        if self._yfinance_module is None:
            import yfinance

            self._yfinance_module = yfinance

        return self._yfinance_module

    def get_latest_close(
        self,
        symbol: str,
        exchange: str,
        currency_hint: str | None,
    ) -> MarketPrice | None:
        normalized_symbol = normalize_code(symbol)
        normalized_exchange = normalize_code(exchange, fallback="")
        ticker = self.yfinance_module.Ticker(normalized_symbol)
        history = ticker.history(period="7d")

        if getattr(history, "empty", False):
            return None

        latest_close = latest_non_null_close(history)
        if latest_close is None:
            return None

        price_date, close_price = latest_close
        currency = normalize_code(
            provider_currency(ticker) or currency_hint,
            fallback="UNKNOWN",
        )

        return MarketPrice(
            symbol=normalized_symbol,
            exchange=normalized_exchange,
            price_date=price_date,
            close_price=close_price,
            currency=currency,
            source="yfinance",
        )

    def get_historical_annualized_return(
        self,
        symbol: str,
        exchange: str,
        currency_hint: str | None,
    ) -> Decimal | None:
        normalized_symbol = normalize_code(symbol)
        ticker = self.yfinance_module.Ticker(normalized_symbol)
        history = ticker.history(period=HISTORICAL_RETURN_PERIOD)

        if getattr(history, "empty", False):
            return None

        first = first_non_null_close(history)
        last = latest_non_null_close(history)
        if first is None or last is None:
            return None

        start_date, start_price = first
        end_date, end_price = last
        if end_date <= start_date or start_price <= 0:
            return None

        years = Decimal((end_date - start_date).days) / DAYS_PER_YEAR
        if years < MIN_HISTORICAL_YEARS:
            return None

        growth = end_price / start_price
        annualized_growth = growth ** (Decimal(1) / years)
        return ((annualized_growth - 1) * 100).quantize(
            RETURN_QUANTIZE, rounding=ROUND_HALF_UP
        )


def provider_currency(ticker: Any) -> str | None:
    fast_info = getattr(ticker, "fast_info", None)
    if isinstance(fast_info, dict):
        currency = fast_info.get("currency")
        return currency if isinstance(currency, str) else None

    currency = getattr(fast_info, "currency", None)
    return currency if isinstance(currency, str) else None


def latest_non_null_close(history: Any) -> tuple[date, Decimal] | None:
    closes = history["Close"]
    indexes = history.index

    for raw_date, raw_close in reversed(list(zip(indexes, closes, strict=False))):
        close_price = parse_finite_decimal(raw_close)
        if close_price is None:
            continue

        return normalize_date(raw_date), close_price

    return None


def first_non_null_close(history: Any) -> tuple[date, Decimal] | None:
    closes = history["Close"]
    indexes = history.index

    for raw_date, raw_close in zip(indexes, closes, strict=False):
        close_price = parse_finite_decimal(raw_close)
        if close_price is None:
            continue

        return normalize_date(raw_date), close_price

    return None


def parse_finite_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None

    try:
        decimal_value = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None

    if not decimal_value.is_finite():
        return None

    return decimal_value


def normalize_date(value: Any) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value

    to_pydatetime = getattr(value, "to_pydatetime", None)
    if callable(to_pydatetime):
        return to_pydatetime().date()

    raise TypeError(f"Unsupported price date value: {value!r}")
