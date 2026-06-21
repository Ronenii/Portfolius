from typing import Any

import httpx

from app.integrations.etf_classification import (  # noqa: F401 (re-exported)
    REGION_KEYWORDS,
    infer_etf_geography,
    infer_etf_region,
    infer_etf_sector,
)
from app.schemas.instruments import InstrumentSearchResult

DOMINANT_SECTOR_THRESHOLD = 60.0


def optional_text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    trimmed_value = value.strip()
    return trimmed_value or None


def parse_weight(value: object) -> float | None:
    if isinstance(value, int | float):
        return float(value)
    text = optional_text(value)
    if text is None:
        return None
    try:
        return float(text.rstrip("%"))
    except ValueError:
        return None


def sector_entry_name(entry: dict[str, object]) -> str | None:
    return optional_text(
        entry.get("sector")
        or entry.get("name")
        or entry.get("category")
        or entry.get("label")
    )


def sector_entry_weight(entry: dict[str, object]) -> float | None:
    return parse_weight(
        entry.get("weight")
        or entry.get("weight_pct")
        or entry.get("allocation")
        or entry.get("percentage")
    )


def classify_etf_sector(sectors: list[dict[str, object]]) -> str | None:
    weighted_sectors = [
        (name, weight)
        for entry in sectors
        if (name := sector_entry_name(entry)) is not None
        and (weight := sector_entry_weight(entry)) is not None
    ]
    if not weighted_sectors:
        return None

    dominant_sector, dominant_weight = max(weighted_sectors, key=lambda item: item[1])
    if dominant_weight >= DOMINANT_SECTOR_THRESHOLD:
        return dominant_sector
    return "Diversified ETF"


def etf_sectors(payload: dict[str, object]) -> list[dict[str, object]]:
    sectors = payload.get("sectors") or payload.get("sector_weightings")
    if isinstance(sectors, list):
        return [sector for sector in sectors if isinstance(sector, dict)]
    return []


class AlphaVantageEtfProfileClient:
    def __init__(
        self,
        api_key: str | None,
        http_client: Any | None = None,
        base_url: str = "https://www.alphavantage.co/query",
    ) -> None:
        self.api_key = api_key
        self.http_client = http_client or httpx.Client(timeout=8.0)
        self.base_url = base_url

    def profile(self, symbol: str) -> InstrumentSearchResult | None:
        normalized_symbol = symbol.strip().upper()
        if not normalized_symbol or not self.api_key:
            return None

        response = self.http_client.get(
            self.base_url,
            params={
                "function": "ETF_PROFILE",
                "symbol": normalized_symbol,
                "apikey": self.api_key,
            },
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict) or "Information" in payload:
            return None

        name = optional_text(payload.get("name") or payload.get("description"))
        geography = infer_etf_geography(name)
        sector = classify_etf_sector(etf_sectors(payload)) or infer_etf_sector(name)
        if (
            sector is None
            and geography.country is None
            and geography.region is None
        ):
            return None

        return InstrumentSearchResult(
            symbol=normalized_symbol,
            name=name,
            exchange=None,
            currency=None,
            asset_class="ETF",
            sector=sector,
            country=geography.country,
            region=geography.region,
            source="alphavantage",
        )
