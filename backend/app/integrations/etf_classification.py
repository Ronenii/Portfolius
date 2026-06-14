"""Provider-agnostic ETF sector/region classification helpers.

``infer_etf_region`` lives here (rather than in a specific provider module) so the
FMP, Alpha Vantage, and yfinance clients can all share one keyword table. The
yfinance helpers expect sector weights as *fractions* (0.0-1.0), which is what the
``Ticker.funds_data.sector_weightings`` mapping returns.
"""

REGION_KEYWORDS = [
    ("Global", ("global", "world", "acwi")),
    ("Europe", ("europe", "eurozone", "euro stoxx", "msci europe")),
    ("Asia", ("asia", "asia pacific", "pacific ex-japan")),
    ("Emerging Markets", ("emerging markets", "emerging market")),
    ("North America", ("north america", "s&p 500", "russell", "nasdaq")),
    ("United States", ("u.s.", "us ", "usa", "united states")),
]

# yfinance reports sector weights as fractions, so a "dominant" sector is one that
# makes up at least half the fund. Below the threshold an ETF is "Diversified".
DOMINANT_SECTOR_THRESHOLD = 0.50

# Maps yfinance's snake_case sector keys to human-readable labels.
YFINANCE_SECTOR_LABELS = {
    "realestate": "Real Estate",
    "consumer_cyclical": "Consumer Cyclical",
    "basic_materials": "Basic Materials",
    "consumer_defensive": "Consumer Defensive",
    "technology": "Technology",
    "communication_services": "Communication Services",
    "financial_services": "Financial Services",
    "utilities": "Utilities",
    "industrials": "Industrials",
    "energy": "Energy",
    "healthcare": "Healthcare",
}


def infer_etf_region(name: str | None) -> str | None:
    normalized_name = f" {name.lower()} " if name else ""
    if not normalized_name:
        return None

    for region, keywords in REGION_KEYWORDS:
        if any(keyword in normalized_name for keyword in keywords):
            return region
    return None


def classify_yfinance_sector(
    sector_weightings: dict[str, object],
) -> str | None:
    """Pick the dominant sector from yfinance fractional weights.

    Returns the dominant sector label when one sector is at least
    ``DOMINANT_SECTOR_THRESHOLD`` of the fund, ``"Diversified ETF"`` when there are
    weights but none dominate, and ``None`` when there is no usable weight data.
    """
    weighted = [
        (key, float(weight))
        for key, weight in sector_weightings.items()
        if isinstance(weight, int | float) and float(weight) > 0
    ]
    if not weighted:
        return None

    dominant_key, dominant_weight = max(weighted, key=lambda item: item[1])
    if dominant_weight >= DOMINANT_SECTOR_THRESHOLD:
        return YFINANCE_SECTOR_LABELS.get(
            dominant_key,
            dominant_key.replace("_", " ").title(),
        )
    return "Diversified ETF"
