from typing import Any

import httpx

from app.schemas.instruments import InstrumentSearchResult

REGIONS_BY_COUNTRY = {
    "Canada": "North America",
    "China": "Asia",
    "France": "Europe",
    "Germany": "Europe",
    "India": "Asia",
    "Israel": "Middle East",
    "Japan": "Asia",
    "Netherlands": "Europe",
    "Switzerland": "Europe",
    "United Kingdom": "Europe",
    "United States": "North America",
}


def optional_text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    trimmed_value = value.strip()
    return trimmed_value or None


def uppercase_optional(value: object) -> str | None:
    text = optional_text(value)
    return text.upper() if text is not None else None


class FmpInstrumentLookupClient:
    def __init__(
        self,
        api_key: str | None,
        http_client: Any | None = None,
        base_url: str = "https://financialmodelingprep.com/api/v3",
    ) -> None:
        self.api_key = api_key
        self.http_client = http_client or httpx.Client(timeout=8.0)
        self.base_url = base_url.rstrip("/")

    def search(self, query: str, limit: int = 10) -> list[InstrumentSearchResult]:
        normalized_query = query.strip().upper()
        if len(normalized_query) < 2 or not self.api_key:
            return []

        response = self.http_client.get(
            f"{self.base_url}/search",
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
        profile = self.profile_for_symbol(symbol)
        country = optional_text(profile.get("country"))

        return InstrumentSearchResult(
            symbol=symbol,
            name=optional_text(item.get("name")),
            exchange=uppercase_optional(
                item.get("exchangeShortName") or item.get("exchange")
            ),
            currency=uppercase_optional(item.get("currency")),
            asset_class=uppercase_optional(item.get("type")),
            sector=optional_text(profile.get("sector")),
            country=country,
            region=REGIONS_BY_COUNTRY.get(country or ""),
            source="fmp",
        )

    def profile_for_symbol(self, symbol: str) -> dict[str, object]:
        response = self.http_client.get(
            f"{self.base_url}/profile/{symbol}",
            params={"apikey": self.api_key},
        )
        response.raise_for_status()
        payload = response.json()
        if isinstance(payload, list) and payload and isinstance(payload[0], dict):
            return payload[0]
        return {}
