from typing import Any

from app.integrations.etf_classification import (
    classify_yfinance_sector,
    infer_etf_geography,
    infer_etf_sector,
)
from app.schemas.instruments import InstrumentSearchResult


def optional_text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    trimmed_value = value.strip()
    return trimmed_value or None


def ticker_info(ticker: Any) -> dict[str, object]:
    try:
        info = ticker.info
    except Exception:
        return {}
    return info if isinstance(info, dict) else {}


def sector_weightings(ticker: Any) -> dict[str, object]:
    try:
        funds_data = ticker.funds_data
    except Exception:
        return {}
    weightings = getattr(funds_data, "sector_weightings", None)
    return weightings if isinstance(weightings, dict) else {}


class YFinanceEtfProfileClient:
    """ETF metadata via yfinance (sector from holdings, region from fund name).

    Drop-in replacement for the Alpha Vantage profile client in
    ``CompositeInstrumentLookupClient``: same ``profile(symbol)`` contract, but
    without Alpha Vantage's 25-requests-per-day free-tier cap. Returns ``None`` for
    anything yfinance does not classify as an ETF so non-ETF symbols fall back to the
    primary (FMP) profile unchanged.
    """

    def __init__(self, yfinance_module: Any | None = None) -> None:
        self._yfinance_module = yfinance_module

    @property
    def yfinance_module(self) -> Any:
        if self._yfinance_module is None:
            import yfinance

            self._yfinance_module = yfinance

        return self._yfinance_module

    def profile(self, symbol: str) -> InstrumentSearchResult | None:
        normalized_symbol = symbol.strip().upper()
        if not normalized_symbol:
            return None

        ticker = self.yfinance_module.Ticker(normalized_symbol)
        info = ticker_info(ticker)

        quote_type = optional_text(info.get("quoteType"))
        if quote_type is None or quote_type.upper() != "ETF":
            return None

        name = optional_text(info.get("longName") or info.get("shortName"))
        category = optional_text(info.get("category"))
        profile_hint = " ".join(part for part in (name, category) if part)
        weighted_sector = classify_yfinance_sector(sector_weightings(ticker))
        geography = infer_etf_geography(profile_hint)

        return InstrumentSearchResult(
            symbol=normalized_symbol,
            name=name,
            exchange=None,
            currency=None,
            asset_class="ETF",
            sector=weighted_sector or infer_etf_sector(profile_hint),
            country=geography.country,
            region=geography.region,
            source="yfinance",
        )
