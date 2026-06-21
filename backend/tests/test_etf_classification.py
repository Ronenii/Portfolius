import pytest

from app.integrations.etf_classification import (
    EtfGeography,
    infer_etf_geography,
)


@pytest.mark.parametrize(
    ("hint", "country", "region"),
    [
        ("iShares MSCI India ETF", "India", "Asia ex-Japan"),
        ("iShares MSCI Japan ETF", "Japan", "Japan"),
        ("iShares MSCI China ETF", "China", "Asia ex-Japan"),
        ("MSCI South Korea ETF", "South Korea", "Asia ex-Japan"),
        ("MSCI Taiwan ETF", "Taiwan", "Asia ex-Japan"),
        ("MSCI Australia ETF", "Australia", "Asia Pacific"),
        ("MSCI Brazil ETF", "Brazil", "Latin America"),
        ("MSCI Mexico ETF", "Mexico", "Latin America"),
        ("MSCI Israel ETF", "Israel", "Middle East"),
        ("MSCI South Africa ETF", "South Africa", "Africa"),
        ("MSCI United Kingdom ETF", "United Kingdom", "Europe"),
        ("MSCI Canada ETF", "Canada", "North America"),
        ("Core S&P 500 UCITS ETF", "United States", "North America"),
        ("Nasdaq 100 UCITS ETF", "United States", "North America"),
        ("Russell 2000 ETF", "United States", "North America"),
        ("MSCI USA Quality ETF", "United States", "North America"),
    ],
)
def test_infers_country_focused_etf_exposure(
    hint: str,
    country: str,
    region: str,
) -> None:
    assert infer_etf_geography(hint) == EtfGeography(country, region)


@pytest.mark.parametrize(
    ("hint", "region"),
    [
        ("Asia Pacific Equity ETF", "Asia Pacific"),
        ("Asia Pacific ex-Japan ETF", "Asia ex-Japan"),
        ("Pacific ex Japan ETF", "Asia ex-Japan"),
        ("MSCI Emerging Markets ETF", "Emerging Markets"),
        ("Developed Markets ex-US ETF", "Global ex-US"),
        ("Global ex US ETF", "Global ex-US"),
        ("MSCI Europe ETF", "Europe"),
        ("Latin America 40 ETF", "Latin America"),
        ("Middle East Dividend ETF", "Middle East"),
        ("Africa Index ETF", "Africa"),
        ("World Equity ETF", "Global"),
    ],
)
def test_infers_multi_country_region_without_country(
    hint: str,
    region: str,
) -> None:
    assert infer_etf_geography(hint) == EtfGeography(None, region)


def test_geography_matching_normalizes_punctuation_and_case() -> None:
    assert infer_etf_geography("core s&p 500 u.c.i.t.s. etf") == EtfGeography(
        "United States",
        "North America",
    )


@pytest.mark.parametrize(
    "hint",
    ["Industrial Select ETF", "Customer Value ETF", "Trustworthy Dividend ETF"],
)
def test_geography_matching_does_not_use_partial_words(hint: str) -> None:
    assert infer_etf_geography(hint) == EtfGeography(None, None)
