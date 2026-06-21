from app.integrations.etf_classification import infer_etf_region
from app.schemas.instruments import InstrumentSearchResult


def is_etf(profile: InstrumentSearchResult | None) -> bool:
    return profile is not None and profile.asset_class == "ETF"


def value_or_fallback(value: str | None, fallback: str | None) -> str | None:
    return value if value is not None else fallback


class CompositeInstrumentLookupClient:
    def __init__(
        self,
        primary_client,
        etf_profile_client,
    ) -> None:
        self.primary_client = primary_client
        self.etf_profile_client = etf_profile_client

    def search(self, query: str, limit: int = 10) -> list[InstrumentSearchResult]:
        return self.primary_client.search(query, limit=limit)

    def profile(self, symbol: str) -> InstrumentSearchResult | None:
        primary_profile = self.primary_client.profile(symbol)
        etf_profile = None
        if primary_profile is None or is_etf(primary_profile):
            etf_profile = self.etf_profile_client.profile(symbol)

        if primary_profile is None:
            return etf_profile
        if etf_profile is None:
            return primary_profile

        name = value_or_fallback(primary_profile.name, etf_profile.name)
        return InstrumentSearchResult(
            symbol=value_or_fallback(primary_profile.symbol, etf_profile.symbol)
            or symbol.strip().upper(),
            name=name,
            exchange=value_or_fallback(primary_profile.exchange, etf_profile.exchange),
            currency=value_or_fallback(primary_profile.currency, etf_profile.currency),
            asset_class=value_or_fallback(
                etf_profile.asset_class,
                primary_profile.asset_class,
            ),
            sector=value_or_fallback(etf_profile.sector, primary_profile.sector),
            country=value_or_fallback(etf_profile.country, primary_profile.country),
            region=value_or_fallback(
                etf_profile.region or infer_etf_region(name),
                primary_profile.region,
            ),
            source=f"{primary_profile.source}+{etf_profile.source}",
        )
