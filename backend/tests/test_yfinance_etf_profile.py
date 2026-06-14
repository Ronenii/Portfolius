from app.integrations.etf_classification import classify_yfinance_sector
from app.integrations.fmp import FmpInstrumentLookupClient
from app.integrations.instrument_lookup import CompositeInstrumentLookupClient
from app.integrations.yfinance_etf_profile import YFinanceEtfProfileClient
from app.schemas.instruments import InstrumentSearchResult


class FakeFundsData:
    def __init__(self, sector_weightings: dict[str, float]) -> None:
        self.sector_weightings = sector_weightings


class FakeTicker:
    def __init__(
        self,
        info: dict[str, object],
        sector_weightings: dict[str, float] | None = None,
        funds_data_error: Exception | None = None,
    ) -> None:
        self._info = info
        self._sector_weightings = sector_weightings or {}
        self._funds_data_error = funds_data_error

    @property
    def info(self) -> dict[str, object]:
        return self._info

    @property
    def funds_data(self) -> FakeFundsData:
        if self._funds_data_error is not None:
            raise self._funds_data_error
        return FakeFundsData(self._sector_weightings)


class FakeYFinanceModule:
    def __init__(self, tickers: dict[str, FakeTicker]) -> None:
        self.tickers = tickers
        self.requested_symbols: list[str] = []

    def Ticker(self, symbol: str) -> FakeTicker:  # noqa: N802 (mirrors yfinance API)
        self.requested_symbols.append(symbol)
        return self.tickers[symbol]


def test_classify_yfinance_sector_picks_dominant_fraction() -> None:
    assert classify_yfinance_sector({"energy": 1.0, "technology": 0.0}) == "Energy"


def test_classify_yfinance_sector_marks_mixed_as_diversified() -> None:
    assert (
        classify_yfinance_sector(
            {
                "financial_services": 0.2249,
                "industrials": 0.2025,
                "healthcare": 0.1247,
            }
        )
        == "Diversified ETF"
    )


def test_classify_yfinance_sector_returns_none_without_weights() -> None:
    assert classify_yfinance_sector({}) is None
    assert classify_yfinance_sector({"energy": 0.0}) is None


def test_yfinance_profile_classifies_dominant_sector_and_region() -> None:
    module = FakeYFinanceModule(
        {
            "IXC": FakeTicker(
                info={
                    "quoteType": "ETF",
                    "longName": "iShares Global Energy ETF",
                    "category": "Equity Energy",
                },
                sector_weightings={"energy": 1.0, "financial_services": 0.0},
            )
        }
    )
    client = YFinanceEtfProfileClient(yfinance_module=module)

    result = client.profile("ixc")

    assert result == InstrumentSearchResult(
        symbol="IXC",
        name="iShares Global Energy ETF",
        exchange=None,
        currency=None,
        asset_class="ETF",
        sector="Energy",
        country=None,
        region="Global",
        source="yfinance",
    )
    assert module.requested_symbols == ["IXC"]


def test_yfinance_profile_infers_region_from_diversified_european_etf() -> None:
    module = FakeYFinanceModule(
        {
            "IEUR": FakeTicker(
                info={
                    "quoteType": "ETF",
                    "longName": "iShares Core MSCI Europe ETF",
                    "category": "Europe Stock",
                },
                sector_weightings={
                    "financial_services": 0.2249,
                    "industrials": 0.2025,
                    "healthcare": 0.1247,
                },
            )
        }
    )

    result = YFinanceEtfProfileClient(yfinance_module=module).profile("IEUR")

    assert result is not None
    assert result.sector == "Diversified ETF"
    assert result.region == "Europe"


def test_yfinance_profile_returns_none_for_non_etf() -> None:
    module = FakeYFinanceModule(
        {"AAPL": FakeTicker(info={"quoteType": "EQUITY", "longName": "Apple Inc."})}
    )

    assert YFinanceEtfProfileClient(yfinance_module=module).profile("AAPL") is None


def test_yfinance_profile_tolerates_missing_funds_data() -> None:
    module = FakeYFinanceModule(
        {
            "ARKK": FakeTicker(
                info={"quoteType": "ETF", "longName": "ARK Innovation ETF"},
                funds_data_error=RuntimeError("no funds data"),
            )
        }
    )

    result = YFinanceEtfProfileClient(yfinance_module=module).profile("ARKK")

    assert result is not None
    assert result.sector is None
    assert result.asset_class == "ETF"


def test_composite_overrides_etf_sector_and_region_from_yfinance() -> None:
    fmp_client = FmpInstrumentLookupClient(api_key="fmp-key")
    module = FakeYFinanceModule(
        {
            "IXC": FakeTicker(
                info={
                    "quoteType": "ETF",
                    "longName": "iShares Global Energy ETF",
                    "category": "Equity Energy",
                },
                sector_weightings={"energy": 1.0},
            )
        }
    )
    yfinance_client = YFinanceEtfProfileClient(yfinance_module=module)
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

    result = CompositeInstrumentLookupClient(fmp_client, yfinance_client).profile("IXC")

    assert result == InstrumentSearchResult(
        symbol="IXC",
        name="iShares Global Energy ETF",
        exchange="NYSEARCA",
        currency="USD",
        asset_class="ETF",
        sector="Energy",
        country="US",
        region="Global",
        source="fmp+yfinance",
    )
