from typing import Any

import httpx

from app.integrations.etf_classification import normalize_country_geography
from app.schemas.instruments import InstrumentSearchResult


def optional_text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    trimmed_value = value.strip()
    return trimmed_value or None


def uppercase_optional(value: object) -> str | None:
    text = optional_text(value)
    return text.upper() if text is not None else None


def bool_value(value: object) -> bool:
    return value is True


def profile_asset_class(item: dict[str, object]) -> str | None:
    explicit_type = uppercase_optional(item.get("type"))
    if explicit_type is not None:
        return explicit_type
    if bool_value(item.get("isEtf")):
        return "ETF"
    if bool_value(item.get("isFund")):
        return "FUND"
    if bool_value(item.get("isAdr")):
        return "ADR"
    return "STOCK"


class FmpInstrumentLookupClient:
    def __init__(
        self,
        api_key: str | None,
        http_client: Any | None = None,
        base_url: str = "https://financialmodelingprep.com/stable",
    ) -> None:
        self.api_key = api_key
        self.http_client = http_client or httpx.Client(timeout=8.0)
        self.base_url = base_url.rstrip("/")

    def search(self, query: str, limit: int = 10) -> list[InstrumentSearchResult]:
        normalized_query = query.strip().upper()
        if len(normalized_query) < 2 or not self.api_key:
            return []

        response = self.http_client.get(
            f"{self.base_url}/search-symbol",
            params={
                "query": normalized_query,
                "limit": limit,
                "apikey": self.api_key,
            },
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, list):
            return []

        results = [
            self.result_from_payload(item)
            for item in payload
            if isinstance(item, dict) and optional_text(item.get("symbol"))
        ]
        return sorted(
            results,
            key=lambda result: (
                not result.symbol.startswith(normalized_query),
                result.symbol,
            ),
        )[:limit]

    def result_from_payload(self, item: dict[str, object]) -> InstrumentSearchResult:
        symbol = uppercase_optional(item.get("symbol")) or ""

        return InstrumentSearchResult(
            symbol=symbol,
            name=optional_text(item.get("name")),
            exchange=uppercase_optional(
                item.get("exchangeShortName") or item.get("exchange")
            ),
            currency=uppercase_optional(item.get("currency")),
            asset_class=uppercase_optional(item.get("type")),
            sector=None,
            country=None,
            region=None,
            source="fmp",
        )

    def profile(self, symbol: str) -> InstrumentSearchResult | None:
        normalized_symbol = symbol.strip().upper()
        if not normalized_symbol or not self.api_key:
            return None

        response = self.http_client.get(
            f"{self.base_url}/profile",
            params={"symbol": normalized_symbol, "apikey": self.api_key},
        )
        response.raise_for_status()
        payload = response.json()
        if (
            not isinstance(payload, list)
            or not payload
            or not isinstance(payload[0], dict)
        ):
            return None

        return self.result_from_profile_payload(payload[0])

    def result_from_profile_payload(
        self,
        item: dict[str, object],
    ) -> InstrumentSearchResult:
        geography = normalize_country_geography(optional_text(item.get("country")))

        return InstrumentSearchResult(
            symbol=uppercase_optional(item.get("symbol")) or "",
            name=optional_text(item.get("companyName") or item.get("name")),
            exchange=uppercase_optional(
                item.get("exchangeShortName") or item.get("exchange")
            ),
            currency=uppercase_optional(item.get("currency")),
            asset_class=profile_asset_class(item),
            sector=optional_text(item.get("sector")),
            country=geography.country,
            region=geography.region,
            source="fmp",
        )
