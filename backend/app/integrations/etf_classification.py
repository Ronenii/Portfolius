"""Provider-agnostic ETF exposure classification helpers.

The shared classifiers live here so FMP, Alpha Vantage, and yfinance adapters
describe an ETF's underlying exposure consistently. The yfinance sector helper
expects weights as fractions (0.0-1.0), matching
``Ticker.funds_data.sector_weightings``.
"""

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class EtfGeography:
    country: str | None
    region: str | None


EXCLUSION_REGION_ALIASES = (
    (
        "Global ex-US",
        (
            "global ex us",
            "world ex us",
            "developed markets ex us",
            "developed ex us",
        ),
    ),
    (
        "Asia ex-Japan",
        (
            "asia ex japan",
            "asia pacific ex japan",
            "pacific ex japan",
        ),
    ),
)

EXPLICIT_REGION_ALIASES = (
    ("Asia Pacific", ("asia pacific",)),
    ("Emerging Markets", ("emerging markets", "emerging market")),
    ("Latin America", ("latin america", "latin american")),
    ("Middle East", ("middle east", "middle eastern")),
    ("Africa", ("africa", "african")),
    ("Europe", ("europe", "european", "eurozone", "euro stoxx")),
    ("North America", ("north america", "north american")),
    ("Global", ("global", "world", "acwi")),
)

COUNTRY_EXPOSURES = (
    (
        "United States",
        "North America",
        (
            "united states",
            "us",
            "u s",
            "usa",
            "msci usa",
            "s&p 500",
            "sp 500",
            "nasdaq",
            "russell",
        ),
    ),
    ("Canada", "North America", ("canada", "canadian")),
    ("Mexico", "Latin America", ("mexico", "mexican")),
    ("Brazil", "Latin America", ("brazil", "brazilian")),
    ("Chile", "Latin America", ("chile", "chilean")),
    ("Colombia", "Latin America", ("colombia", "colombian")),
    ("Peru", "Latin America", ("peru", "peruvian")),
    ("Argentina", "Latin America", ("argentina", "argentinian")),
    (
        "United Kingdom",
        "Europe",
        ("united kingdom", "uk", "britain", "british"),
    ),
    ("Ireland", "Europe", ("ireland", "irish")),
    ("France", "Europe", ("france", "french")),
    ("Germany", "Europe", ("germany", "german")),
    ("Italy", "Europe", ("italy", "italian")),
    ("Spain", "Europe", ("spain", "spanish")),
    ("Portugal", "Europe", ("portugal", "portuguese")),
    ("Netherlands", "Europe", ("netherlands", "dutch")),
    ("Belgium", "Europe", ("belgium", "belgian")),
    ("Switzerland", "Europe", ("switzerland", "swiss")),
    ("Austria", "Europe", ("austria", "austrian")),
    ("Sweden", "Europe", ("sweden", "swedish")),
    ("Norway", "Europe", ("norway", "norwegian")),
    ("Denmark", "Europe", ("denmark", "danish")),
    ("Finland", "Europe", ("finland", "finnish")),
    ("Poland", "Europe", ("poland", "polish")),
    ("Greece", "Europe", ("greece", "greek")),
    ("Türkiye", "Europe", ("turkiye", "turkey", "turkish")),
    ("Japan", "Japan", ("japan", "japanese", "nikkei", "topix")),
    ("China", "Asia ex-Japan", ("china", "chinese", "msci china")),
    ("India", "Asia ex-Japan", ("india", "indian", "nifty", "sensex")),
    (
        "South Korea",
        "Asia ex-Japan",
        ("south korea", "korea", "korean", "kospi"),
    ),
    ("Taiwan", "Asia ex-Japan", ("taiwan", "taiwanese")),
    ("Hong Kong", "Asia ex-Japan", ("hong kong", "hang seng")),
    ("Singapore", "Asia ex-Japan", ("singapore", "singaporean")),
    ("Indonesia", "Asia ex-Japan", ("indonesia", "indonesian")),
    ("Malaysia", "Asia ex-Japan", ("malaysia", "malaysian")),
    ("Thailand", "Asia ex-Japan", ("thailand", "thai")),
    ("Vietnam", "Asia ex-Japan", ("vietnam", "vietnamese")),
    ("Philippines", "Asia ex-Japan", ("philippines", "philippine")),
    ("Pakistan", "Asia ex-Japan", ("pakistan", "pakistani")),
    ("Bangladesh", "Asia ex-Japan", ("bangladesh", "bangladeshi")),
    ("Australia", "Asia Pacific", ("australia", "australian", "asx")),
    ("New Zealand", "Asia Pacific", ("new zealand",)),
    ("Israel", "Middle East", ("israel", "israeli")),
    ("Saudi Arabia", "Middle East", ("saudi arabia", "saudi")),
    (
        "United Arab Emirates",
        "Middle East",
        ("united arab emirates", "uae"),
    ),
    ("Qatar", "Middle East", ("qatar", "qatari")),
    ("Kuwait", "Middle East", ("kuwait", "kuwaiti")),
    ("South Africa", "Africa", ("south africa", "south african")),
    ("Egypt", "Africa", ("egypt", "egyptian")),
    ("Nigeria", "Africa", ("nigeria", "nigerian")),
    ("Morocco", "Africa", ("morocco", "moroccan")),
    ("Kenya", "Africa", ("kenya", "kenyan")),
)

SECTOR_ALIASES = (
    (
        "Communication Services",
        ("communication services", "telecommunications", "telecom", "media"),
    ),
    (
        "Consumer Defensive",
        ("consumer staples", "consumer defensive", "food and beverage"),
    ),
    (
        "Consumer Cyclical",
        (
            "consumer discretionary",
            "consumer cyclical",
            "travel and leisure",
            "automotive",
            "retail",
        ),
    ),
    (
        "Basic Materials",
        ("basic materials", "metals and mining", "materials", "mining"),
    ),
    (
        "Financial Services",
        ("financial services", "financials", "insurance", "banking", "banks"),
    ),
    (
        "Healthcare",
        (
            "medical devices",
            "health care",
            "healthcare",
            "biotechnology",
            "biotech",
            "pharmaceutical",
        ),
    ),
    (
        "Industrials",
        (
            "aerospace and defense",
            "transportation",
            "infrastructure",
            "industrials",
            "industrial",
        ),
    ),
    ("Real Estate", ("real estate", "property", "reit")),
    (
        "Technology",
        (
            "information technology",
            "artificial intelligence",
            "cloud computing",
            "semiconductor",
            "cybersecurity",
            "technology",
            "software",
            "robotics",
        ),
    ),
    ("Utilities", ("utilities", "utility")),
    (
        "Energy",
        ("oil and gas", "clean energy", "wind energy", "energy", "solar"),
    ),
)

# Kept as a compatibility export for provider modules and older callers.
REGION_KEYWORDS = list(EXCLUSION_REGION_ALIASES + EXPLICIT_REGION_ALIASES)

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


def normalize_hint(value: str | None) -> str:
    if not value:
        return ""
    return " ".join(re.sub(r"[^a-z0-9]+", " ", value.casefold()).split())


def contains_phrase(normalized_hint: str, alias: str) -> bool:
    normalized_alias = normalize_hint(alias)
    return f" {normalized_alias} " in f" {normalized_hint} "


def infer_etf_geography(hint: str | None) -> EtfGeography:
    normalized_hint = normalize_hint(hint)
    if not normalized_hint:
        return EtfGeography(None, None)

    for region, aliases in EXCLUSION_REGION_ALIASES:
        if any(contains_phrase(normalized_hint, alias) for alias in aliases):
            return EtfGeography(None, region)

    for country, region, aliases in COUNTRY_EXPOSURES:
        if any(contains_phrase(normalized_hint, alias) for alias in aliases):
            return EtfGeography(country, region)

    for region, aliases in EXPLICIT_REGION_ALIASES:
        if any(contains_phrase(normalized_hint, alias) for alias in aliases):
            return EtfGeography(None, region)

    return EtfGeography(None, None)


def infer_etf_region(name: str | None) -> str | None:
    return infer_etf_geography(name).region


def infer_etf_sector(hint: str | None) -> str | None:
    normalized_hint = normalize_hint(hint)
    if not normalized_hint:
        return None

    for sector, aliases in SECTOR_ALIASES:
        if any(contains_phrase(normalized_hint, alias) for alias in aliases):
            return sector
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
