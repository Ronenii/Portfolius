from app.integrations.alpha_vantage import (
    AlphaVantageEtfProfileClient,
    classify_etf_sector,
    infer_etf_region,
)
from app.integrations.fmp import FmpInstrumentLookupClient
from app.integrations.instrument_lookup import CompositeInstrumentLookupClient
from app.schemas.instruments import InstrumentSearchResult


class FakeResponse:
    def __init__(self, payload: object) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> object:
        return self._payload


class FakeHttpClient:
    def __init__(self) -> None:
        self.requested_urls: list[str] = []
        self.requested_params: list[dict[str, object]] = []

    def get(self, url: str, params: dict[str, object]) -> FakeResponse:
        self.requested_urls.append(url)
        self.requested_params.append(params)
        if url.endswith("/search-symbol"):
            assert params["query"] == "IN"
            assert params["limit"] == 10
            return FakeResponse(
                [
                    {
                        "symbol": "ivv",
                        "name": "iShares Core S&P 500 ETF",
                        "exchangeShortName": "arca",
                        "currency": "usd",
                        "type": "etf",
                    },
                    {
                        "symbol": "inda",
                        "name": "iShares MSCI India ETF",
                        "exchangeShortName": "bats",
                        "currency": "usd",
                        "type": "etf",
                    },
                ]
            )
        if url.endswith("/profile"):
            assert params["symbol"] == "TSM"
            return FakeResponse(
                [
                    {
                        "symbol": "tsm",
                        "companyName": (
                            "Taiwan Semiconductor Manufacturing Company Limited"
                        ),
                        "exchangeShortName": "nyse",
                        "currency": "usd",
                        "sector": "Technology",
                        "country": "TW",
                        "isAdr": True,
                        "isEtf": False,
                        "isFund": False,
                    }
                ]
            )
        raise AssertionError(f"Unexpected URL {url}")


class FakeAlphaVantageHttpClient:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload
        self.requested_urls: list[str] = []
        self.requested_params: list[dict[str, object]] = []

    def get(self, url: str, params: dict[str, object]) -> FakeResponse:
        self.requested_urls.append(url)
        self.requested_params.append(params)
        return FakeResponse(self.payload)


def test_fmp_lookup_normalizes_and_enriches_search_results() -> None:
    client = FmpInstrumentLookupClient(
        api_key="fmp-key",
        http_client=FakeHttpClient(),
    )

    results = client.search(" in ")

    assert results == [
        InstrumentSearchResult(
            symbol="INDA",
            name="iShares MSCI India ETF",
            exchange="BATS",
            currency="USD",
            asset_class="ETF",
            sector=None,
            country=None,
            region=None,
            source="fmp",
        ),
        InstrumentSearchResult(
            symbol="IVV",
            name="iShares Core S&P 500 ETF",
            exchange="ARCA",
            currency="USD",
            asset_class="ETF",
            sector=None,
            country=None,
            region=None,
            source="fmp",
        ),
    ]


def test_fmp_lookup_returns_empty_results_for_short_query() -> None:
    http_client = FakeHttpClient()
    client = FmpInstrumentLookupClient(api_key="fmp-key", http_client=http_client)

    assert client.search("i") == []
    assert http_client.requested_urls == []


def test_fmp_lookup_returns_empty_results_without_api_key() -> None:
    http_client = FakeHttpClient()
    client = FmpInstrumentLookupClient(api_key=None, http_client=http_client)

    assert client.search("IN") == []
    assert http_client.requested_urls == []


def test_fmp_lookup_uses_current_stable_endpoints() -> None:
    http_client = FakeHttpClient()
    client = FmpInstrumentLookupClient(api_key="fmp-key", http_client=http_client)

    client.search("IN")

    assert http_client.requested_urls == [
        "https://financialmodelingprep.com/stable/search-symbol",
    ]
    assert http_client.requested_params[0]["apikey"] == "fmp-key"


def test_fmp_lookup_uses_one_provider_call_per_search() -> None:
    http_client = FakeHttpClient()
    client = FmpInstrumentLookupClient(api_key="fmp-key", http_client=http_client)

    client.search("IN")

    assert len(http_client.requested_urls) == 1


def test_fmp_profile_returns_rich_instrument_metadata() -> None:
    http_client = FakeHttpClient()
    client = FmpInstrumentLookupClient(api_key="fmp-key", http_client=http_client)

    result = client.profile("tsm")

    assert result == InstrumentSearchResult(
        symbol="TSM",
        name="Taiwan Semiconductor Manufacturing Company Limited",
        exchange="NYSE",
        currency="USD",
        asset_class="ADR",
        sector="Technology",
        country="Taiwan",
        region="Asia ex-Japan",
        source="fmp",
    )
    assert http_client.requested_urls == [
        "https://financialmodelingprep.com/stable/profile",
    ]
    assert http_client.requested_params[0]["apikey"] == "fmp-key"


def test_fmp_profile_derives_etf_asset_class() -> None:
    client = FmpInstrumentLookupClient(api_key="fmp-key")

    result = client.result_from_profile_payload(
        {
            "symbol": "voo",
            "companyName": "Vanguard S&P 500 ETF",
            "currency": "usd",
            "isEtf": True,
            "isFund": False,
            "isAdr": False,
        }
    )

    assert result.asset_class == "ETF"


def test_alpha_vantage_profile_classifies_dominant_sector_etf() -> None:
    http_client = FakeAlphaVantageHttpClient(
        {
            "sectors": [
                {"sector": "Energy", "weight": "99.20"},
                {"sector": "Financial Services", "weight": "0.80"},
            ],
            "holdings": [
                {"symbol": "XOM", "description": "Exxon Mobil", "weight": "22.4"}
            ],
        }
    )
    client = AlphaVantageEtfProfileClient(
        api_key="alpha-key",
        http_client=http_client,
    )

    result = client.profile("ixc")

    assert result is not None
    assert result.symbol == "IXC"
    assert result.asset_class == "ETF"
    assert result.sector == "Energy"
    assert result.source == "alphavantage"
    assert http_client.requested_params[0] == {
        "function": "ETF_PROFILE",
        "symbol": "IXC",
        "apikey": "alpha-key",
    }


def test_alpha_vantage_profile_infers_country_and_region_from_name() -> None:
    client = AlphaVantageEtfProfileClient(
        api_key="alpha-key",
        http_client=FakeAlphaVantageHttpClient(
            {
                "name": "iShares MSCI India ETF",
                "sectors": [
                    {"sector": "Financial Services", "weight": "30.0"},
                    {"sector": "Technology", "weight": "20.0"},
                ],
            }
        ),
    )

    result = client.profile("inda")

    assert result is not None
    assert result.country == "India"
    assert result.region == "Asia ex-Japan"


def test_alpha_vantage_profile_marks_mixed_sector_etf_as_diversified() -> None:
    assert (
        classify_etf_sector(
            [
                {"sector": "Technology", "weight": "31.0"},
                {"sector": "Financial Services", "weight": "18.5"},
                {"sector": "Healthcare", "weight": "16.0"},
            ]
        )
        == "Diversified ETF"
    )


def test_etf_region_can_be_inferred_from_fund_name() -> None:
    assert infer_etf_region("iShares Core MSCI Europe ETF") == "Europe"
    assert infer_etf_region("iShares Global Energy ETF") == "Global"


def test_composite_lookup_overrides_etf_sector_and_region_from_alpha_vantage() -> None:
    fmp_client = FmpInstrumentLookupClient(api_key="fmp-key")
    alpha_client = AlphaVantageEtfProfileClient(api_key="alpha-key")
    fmp_client.profile = lambda symbol: InstrumentSearchResult(  # type: ignore[method-assign]
        symbol="IXC",
        name="iShares Global Energy ETF",
        exchange="NYSEARCA",
        currency="USD",
        asset_class="ETF",
        sector="Financial Services",
        country="US",
        region="North America",
        source="fmp",
    )
    alpha_client.profile = lambda symbol: InstrumentSearchResult(  # type: ignore[method-assign]
        symbol="IXC",
        name=None,
        exchange=None,
        currency=None,
        asset_class="ETF",
        sector="Energy",
        country=None,
        region=None,
        source="alphavantage",
    )

    result = CompositeInstrumentLookupClient(fmp_client, alpha_client).profile("IXC")

    assert result == InstrumentSearchResult(
        symbol="IXC",
        name="iShares Global Energy ETF",
        exchange="NYSEARCA",
        currency="USD",
        asset_class="ETF",
        sector="Energy",
        country="US",
        region="Global",
        source="fmp+alphavantage",
    )
