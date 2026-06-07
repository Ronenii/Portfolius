from app.integrations.fmp import FmpInstrumentLookupClient
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
        country="TW",
        region="Asia",
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
