from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Protocol


@dataclass(frozen=True)
class MarketPrice:
    symbol: str
    exchange: str
    price_date: date
    close_price: Decimal
    currency: str
    source: str


class MarketDataClient(Protocol):
    def get_latest_close(
        self,
        symbol: str,
        exchange: str,
        currency_hint: str | None,
    ) -> MarketPrice | None:
        ...

    def get_historical_annualized_return(
        self,
        symbol: str,
        exchange: str,
        currency_hint: str | None,
    ) -> Decimal | None:
        ...
