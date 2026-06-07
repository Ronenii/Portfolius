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

    def get(self, url: str, params: dict[str, object]) -> FakeResponse:
        self.requested_urls.append(url)
        if url.endswith("/search"):
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
        if url.endswith("/profile/IVV"):
            return FakeResponse(
                [
                    {
                        "sector": "Broad Market",
                        "country": "United States",
                    }
                ]
            )
        if url.endswith("/profile/INDA"):
            return FakeResponse(
                [
                    {
                        "sector": "Broad Market",
                        "country": "India",
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
            sector="Broad Market",
            country="India",
            region="Asia",
            source="fmp",
        ),
        InstrumentSearchResult(
            symbol="IVV",
            name="iShares Core S&P 500 ETF",
            exchange="ARCA",
            currency="USD",
            asset_class="ETF",
            sector="Broad Market",
            country="United States",
            region="North America",
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
