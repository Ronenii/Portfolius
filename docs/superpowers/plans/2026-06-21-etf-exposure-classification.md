# ETF Exposure Classification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Classify ETFs by underlying country, region, and sector exposure instead of exchange listing or fund domicile, including correct results for INDA and CSPX.

**Architecture:** Replace independent region substring matching with a shared structured ETF exposure classifier that returns a consistent country/region pair from normalized fund names and categories. Provider clients use that classifier for ETF metadata, while holdings-based sector weights remain authoritative and name/category sector aliases act only as fallback. The composite lookup prefers ETF exposure metadata over primary-provider listing geography, and an Alembic data migration repairs already-stored INDA metadata.

**Tech Stack:** Python 3.11+, dataclasses, regular expressions, FastAPI schemas, yfinance and Alpha Vantage adapters, SQLAlchemy/Alembic, pytest, Ruff.

**Completed:** 2026-06-21

---

## File Map

- Create `backend/tests/test_etf_classification.py`: table-driven unit tests for geography, precedence, normalization, sector aliases, and false-positive boundaries.
- Modify `backend/app/integrations/etf_classification.py`: structured geography model, normalized phrase matching, country/region tables, benchmark aliases, and fallback sector inference.
- Modify `backend/app/integrations/yfinance_etf_profile.py`: populate ETF country/region together and use name/category sector fallback only without holdings weights.
- Modify `backend/app/integrations/alpha_vantage.py`: populate ETF country/region together and retain profiles when geography or sector fallback is available.
- Modify `backend/app/integrations/instrument_lookup.py`: prefer ETF exposure country and region over listing geography.
- Modify `backend/tests/test_yfinance_etf_profile.py`: provider and composite regressions for INDA, CSPX, and sector precedence.
- Modify `backend/tests/test_instrument_lookup.py`: Alpha Vantage structured exposure regression.
- Create `backend/alembic/versions/20260621_0006_fix_etf_exposure.py`: correct stored INDA and CSPX country and region.
- Delete `backend/alembic/versions/20260621_0006_fix_inda_region.py`: replace the uncommitted narrow migration with the complete exposure correction.
- Modify `backend/tests/test_m3_schema.py`: verify the migration updates only known incorrect INDA and CSPX metadata.

### Task 1: Build Structured ETF Geography Inference

**Files:**
- Create: `backend/tests/test_etf_classification.py`
- Modify: `backend/app/integrations/etf_classification.py`

- [x] **Step 1: Write failing table-driven geography tests**

Create tests that import `EtfGeography` and `infer_etf_geography` and assert the
following exact cases:

```python
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
```

Add explicit regional and precedence cases:

```python
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
```

Add normalization and false-positive tests:

```python
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
```

- [x] **Step 2: Run the geography tests and verify RED**

Run:

```bash
cd backend
source .venv/bin/activate
pytest tests/test_etf_classification.py -q
```

Expected: collection fails because `EtfGeography` and
`infer_etf_geography` do not exist.

- [x] **Step 3: Implement normalized structured geography inference**

In `backend/app/integrations/etf_classification.py`:

1. Add `EtfGeography` as a frozen dataclass.
2. Normalize punctuation and whitespace with a helper that preserves phrase
   boundaries.
3. Define ordered explicit-region phrases before country phrases.
4. Define country exposures as canonical country, canonical region, and aliases.
5. Match aliases as complete normalized phrases.
6. Retain `infer_etf_region(name)` as a compatibility wrapper returning
   `infer_etf_geography(name).region`.

The public interface must be:

```python
@dataclass(frozen=True)
class EtfGeography:
    country: str | None
    region: str | None


def infer_etf_geography(hint: str | None) -> EtfGeography:
    ...


def infer_etf_region(name: str | None) -> str | None:
    return infer_etf_geography(name).region
```

Use ordered explicit region aliases for:

```python
EXPLICIT_REGION_ALIASES = (
    ("Global ex-US", ("global ex us", "world ex us", "developed markets ex us")),
    (
        "Asia ex-Japan",
        ("asia ex japan", "asia pacific ex japan", "pacific ex japan"),
    ),
    ("Asia Pacific", ("asia pacific", "asia-pacific")),
    ("Emerging Markets", ("emerging markets", "emerging market")),
    ("Latin America", ("latin america", "latin american")),
    ("Middle East", ("middle east", "middle eastern")),
    ("Africa", ("africa", "african")),
    ("Europe", ("europe", "european", "eurozone", "euro stoxx")),
    ("North America", ("north america", "north american")),
    ("Global", ("global", "world", "acwi")),
)
```

Cover common investable countries with canonical mappings:

```python
COUNTRY_EXPOSURES = (
    ("United States", "North America", ("united states", "us", "u s", "usa",
        "msci usa", "s&p 500", "sp 500", "nasdaq", "russell")),
    ("Canada", "North America", ("canada", "canadian")),
    ("Mexico", "Latin America", ("mexico", "mexican")),
    ("Brazil", "Latin America", ("brazil", "brazilian")),
    ("Chile", "Latin America", ("chile", "chilean")),
    ("Colombia", "Latin America", ("colombia", "colombian")),
    ("Peru", "Latin America", ("peru", "peruvian")),
    ("Argentina", "Latin America", ("argentina", "argentinian")),
    ("United Kingdom", "Europe", ("united kingdom", "uk", "britain", "british")),
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
    ("South Korea", "Asia ex-Japan", ("south korea", "korea", "korean", "kospi")),
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
    ("United Arab Emirates", "Middle East", ("united arab emirates", "uae")),
    ("Qatar", "Middle East", ("qatar", "qatari")),
    ("Kuwait", "Middle East", ("kuwait", "kuwaiti")),
    ("South Africa", "Africa", ("south africa", "south african")),
    ("Egypt", "Africa", ("egypt", "egyptian")),
    ("Nigeria", "Africa", ("nigeria", "nigerian")),
    ("Morocco", "Africa", ("morocco", "moroccan")),
    ("Kenya", "Africa", ("kenya", "kenyan")),
)
```

Ensure explicit exclusion phrases run before countries so `Asia Pacific
ex-Japan` does not resolve to Japan or Australia.

- [x] **Step 4: Run geography tests and verify GREEN**

Run:

```bash
cd backend
source .venv/bin/activate
pytest tests/test_etf_classification.py -q
```

Expected: all geography tests pass.

- [x] **Step 5: Commit structured geography inference**

```bash
git add backend/app/integrations/etf_classification.py \
  backend/tests/test_etf_classification.py
git commit -m "feat: infer structured ETF geography"
```

### Task 2: Add Conservative ETF Sector Fallbacks

**Files:**
- Modify: `backend/tests/test_etf_classification.py`
- Modify: `backend/app/integrations/etf_classification.py`
- Modify: `backend/app/integrations/yfinance_etf_profile.py`
- Modify: `backend/tests/test_yfinance_etf_profile.py`

- [x] **Step 1: Write failing sector alias tests**

Add table-driven tests for `infer_etf_sector`:

```python
from app.integrations.etf_classification import infer_etf_sector


@pytest.mark.parametrize(
    ("hint", "sector"),
    [
        ("Global Mining and Metals ETF", "Basic Materials"),
        ("Communication Services ETF", "Communication Services"),
        ("Global Travel and Leisure ETF", "Consumer Cyclical"),
        ("Consumer Staples ETF", "Consumer Defensive"),
        ("Clean Energy ETF", "Energy"),
        ("Global Banks ETF", "Financial Services"),
        ("Biotechnology ETF", "Healthcare"),
        ("Aerospace and Defense ETF", "Industrials"),
        ("Global REIT ETF", "Real Estate"),
        ("Semiconductor ETF", "Technology"),
        ("Global Utilities ETF", "Utilities"),
    ],
)
def test_infers_etf_sector_from_name_or_category(
    hint: str,
    sector: str,
) -> None:
    assert infer_etf_sector(hint) == sector


@pytest.mark.parametrize(
    "hint",
    [
        "Total World Stock ETF",
        "Dividend Growth ETF",
        "Quality Factor ETF",
        "Aggregate Bond ETF",
        "Gold Trust",
    ],
)
def test_does_not_force_broad_or_non_equity_funds_into_sector(hint: str) -> None:
    assert infer_etf_sector(hint) is None
```

In `backend/tests/test_yfinance_etf_profile.py`, add:

```python
def test_yfinance_profile_uses_sector_name_fallback_without_weights() -> None:
    module = FakeYFinanceModule(
        {
            "SOXX": FakeTicker(
                info={
                    "quoteType": "ETF",
                    "longName": "iShares Semiconductor ETF",
                    "category": "Technology",
                },
                sector_weightings={},
            )
        }
    )

    result = YFinanceEtfProfileClient(yfinance_module=module).profile("SOXX")

    assert result is not None
    assert result.sector == "Technology"


def test_yfinance_sector_weights_override_name_fallback() -> None:
    module = FakeYFinanceModule(
        {
            "MIX": FakeTicker(
                info={
                    "quoteType": "ETF",
                    "longName": "Technology Leaders ETF",
                },
                sector_weightings={"financial_services": 0.6},
            )
        }
    )

    result = YFinanceEtfProfileClient(yfinance_module=module).profile("MIX")

    assert result is not None
    assert result.sector == "Financial Services"
```

- [x] **Step 2: Run sector tests and verify RED**

Run:

```bash
cd backend
source .venv/bin/activate
pytest tests/test_etf_classification.py \
  tests/test_yfinance_etf_profile.py::test_yfinance_profile_uses_sector_name_fallback_without_weights \
  tests/test_yfinance_etf_profile.py::test_yfinance_sector_weights_override_name_fallback -q
```

Expected: failures because `infer_etf_sector` does not exist and yfinance has
no name/category fallback.

- [x] **Step 3: Implement canonical sector aliases**

Add `infer_etf_sector(hint)` to `etf_classification.py` using the same
normalized complete-phrase matching. Use ordered aliases:

```python
SECTOR_ALIASES = (
    ("Communication Services", (
        "communication services", "telecom", "telecommunications", "media",
    )),
    ("Consumer Defensive", (
        "consumer staples", "consumer defensive", "food and beverage",
    )),
    ("Consumer Cyclical", (
        "consumer discretionary", "consumer cyclical", "retail",
        "travel and leisure", "automotive",
    )),
    ("Basic Materials", (
        "basic materials", "materials", "metals and mining", "mining",
    )),
    ("Financial Services", (
        "financial services", "financials", "banks", "banking", "insurance",
    )),
    ("Healthcare", (
        "healthcare", "health care", "biotechnology", "biotech",
        "pharmaceutical", "medical devices",
    )),
    ("Industrials", (
        "industrials", "industrial", "aerospace and defense",
        "transportation", "infrastructure",
    )),
    ("Real Estate", ("real estate", "reit", "property")),
    ("Technology", (
        "technology", "information technology", "semiconductor",
        "software", "cybersecurity", "cloud computing", "robotics",
        "artificial intelligence",
    )),
    ("Utilities", ("utilities", "utility")),
    ("Energy", (
        "energy", "oil and gas", "clean energy", "solar", "wind energy",
    )),
)
```

Match more specific phrases before generic ones.

- [x] **Step 4: Integrate fallback into yfinance**

In `YFinanceEtfProfileClient.profile`, build one combined `profile_hint` from
name and category. Compute:

```python
weighted_sector = classify_yfinance_sector(sector_weightings(ticker))
geography = infer_etf_geography(profile_hint)
sector = weighted_sector or infer_etf_sector(profile_hint)
```

Populate `country=geography.country`, `region=geography.region`, and
`sector=sector`.

- [x] **Step 5: Run sector and yfinance tests and verify GREEN**

Run:

```bash
cd backend
source .venv/bin/activate
pytest tests/test_etf_classification.py tests/test_yfinance_etf_profile.py -q
```

Expected: all tests pass.

- [x] **Step 6: Commit sector fallbacks**

```bash
git add backend/app/integrations/etf_classification.py \
  backend/app/integrations/yfinance_etf_profile.py \
  backend/tests/test_etf_classification.py \
  backend/tests/test_yfinance_etf_profile.py
git commit -m "feat: infer ETF sector fallbacks"
```

### Task 3: Override Listing Geography in Provider Composition

**Files:**
- Modify: `backend/tests/test_yfinance_etf_profile.py`
- Modify: `backend/tests/test_instrument_lookup.py`
- Modify: `backend/app/integrations/instrument_lookup.py`
- Modify: `backend/app/integrations/alpha_vantage.py`

- [x] **Step 1: Expand failing INDA and CSPX composite tests**

Replace the current INDA regression expectation with:

```python
assert result.country == "India"
assert result.region == "Asia ex-Japan"
```

Add a CSPX regression where FMP returns Irish domicile:

```python
def test_composite_classifies_cspx_by_us_exposure_not_irish_domicile() -> None:
    fmp_client = FmpInstrumentLookupClient(api_key="fmp-key")
    module = FakeYFinanceModule(
        {
            "CSPX": FakeTicker(
                info={
                    "quoteType": "ETF",
                    "longName": "iShares Core S&P 500 UCITS ETF USD (Acc)",
                    "category": "US Large-Cap Blend Equity",
                },
                sector_weightings={},
            )
        }
    )
    yfinance_client = YFinanceEtfProfileClient(yfinance_module=module)
    fmp_client.profile = lambda symbol: InstrumentSearchResult(
        symbol="CSPX",
        name="iShares Core S&P 500 UCITS ETF USD (Acc)",
        exchange="LSE",
        currency="USD",
        asset_class="ETF",
        sector=None,
        country="Ireland",
        region="Europe",
        source="fmp",
    )

    result = CompositeInstrumentLookupClient(fmp_client, yfinance_client).profile(
        "CSPX"
    )

    assert result is not None
    assert result.exchange == "LSE"
    assert result.country == "United States"
    assert result.region == "North America"
```

In `test_instrument_lookup.py`, add an Alpha Vantage profile using
`"iShares MSCI India ETF"` and assert country `India`, region
`Asia ex-Japan`.

- [x] **Step 2: Run provider/composite regressions and verify RED**

Run:

```bash
cd backend
source .venv/bin/activate
pytest tests/test_yfinance_etf_profile.py \
  tests/test_instrument_lookup.py -q
```

Expected: INDA and CSPX country assertions fail because the composite currently
prefers the primary provider country.

- [x] **Step 3: Prefer ETF exposure country and region**

In `CompositeInstrumentLookupClient.profile`, change country composition to:

```python
country=value_or_fallback(etf_profile.country, primary_profile.country),
```

Keep region composition ETF-first:

```python
region=value_or_fallback(
    etf_profile.region or infer_etf_region(name),
    primary_profile.region,
),
```

This preserves the primary exchange and currency while replacing only
exposure fields.

- [x] **Step 4: Integrate structured exposure into Alpha Vantage**

Build a combined hint from Alpha Vantage name/description, infer geography and
fallback sector, and return an ETF profile when at least one useful exposure
field is available. Populate:

```python
geography = infer_etf_geography(name)
sector = classify_etf_sector(etf_sectors(payload)) or infer_etf_sector(name)
```

Return `None` only when both `sector` and both geography fields are absent.

- [x] **Step 5: Run provider/composite regressions and verify GREEN**

Run:

```bash
cd backend
source .venv/bin/activate
pytest tests/test_yfinance_etf_profile.py \
  tests/test_instrument_lookup.py -q
```

Expected: all tests pass, including INDA and CSPX.

- [x] **Step 6: Commit provider composition**

```bash
git add backend/app/integrations/instrument_lookup.py \
  backend/app/integrations/alpha_vantage.py \
  backend/tests/test_yfinance_etf_profile.py \
  backend/tests/test_instrument_lookup.py
git commit -m "fix: prefer ETF exposure geography"
```

### Task 4: Correct Existing INDA and CSPX Metadata

**Files:**
- Create: `backend/alembic/versions/20260621_0006_fix_etf_exposure.py`
- Delete: `backend/alembic/versions/20260621_0006_fix_inda_region.py`
- Modify: `backend/tests/test_m3_schema.py`

- [x] **Step 1: Strengthen the migration test and verify RED**

Seed three instruments before upgrading:

```sql
INSERT INTO instruments (symbol, exchange, country, region)
VALUES
  ('INDA', 'BATS', 'US', 'North America'),
  ('INDA', 'LSE', 'India', 'Asia ex-Japan'),
  ('CSPX', 'LSE', 'Ireland', 'Europe');
```

After upgrading, assert:

```python
rows = connection.execute(
    text(
        """
        SELECT symbol, exchange, country, region
        FROM instruments
        ORDER BY symbol, exchange
        """
    )
).all()

assert rows == [
    ("CSPX", "LSE", "United States", "North America"),
    ("INDA", "BATS", "India", "Asia ex-Japan"),
    ("INDA", "LSE", "India", "Asia ex-Japan"),
]
```

Run:

```bash
cd backend
source .venv/bin/activate
pytest tests/test_m3_schema.py::test_inda_region_data_correction -q
```

Expected: failure because the narrow migration sets only INDA region `Asia`
and does not correct CSPX.

- [x] **Step 2: Replace the narrow migration with ETF exposure corrections**

Create `20260621_0006_fix_etf_exposure.py` with the same revision identifiers
as the uncommitted narrow migration and delete
`20260621_0006_fix_inda_region.py`. Use two targeted statements:

```python
op.execute(
    sa.text(
        """
        UPDATE instruments
        SET country = 'India', region = 'Asia ex-Japan'
        WHERE symbol = 'INDA'
          AND region = 'North America'
          AND (country IS NULL OR country IN ('US', 'United States'))
        """
    )
)
op.execute(
    sa.text(
        """
        UPDATE instruments
        SET country = 'United States', region = 'North America'
        WHERE symbol = 'CSPX'
          AND region = 'Europe'
          AND country IN ('IE', 'Ireland')
        """
    )
)
```

Keep downgrade non-destructive with `pass`, because the prior country/region
metadata cannot be reconstructed reliably.

- [x] **Step 3: Run migration tests and verify GREEN**

Run:

```bash
cd backend
source .venv/bin/activate
pytest tests/test_m3_schema.py -q
```

Expected: all schema tests pass.

- [x] **Step 4: Commit stored-data correction**

```bash
git add backend/alembic/versions/20260621_0006_fix_etf_exposure.py \
  backend/alembic/versions/20260621_0006_fix_inda_region.py \
  backend/tests/test_m3_schema.py
git commit -m "fix: migrate ETF exposure metadata"
```

### Task 5: Full Verification and Cleanup

**Files:**
- Review all files changed in Tasks 1-4.

- [x] **Step 1: Run focused ETF tests**

```bash
cd backend
source .venv/bin/activate
pytest tests/test_etf_classification.py \
  tests/test_yfinance_etf_profile.py \
  tests/test_instrument_lookup.py \
  tests/test_m3_schema.py -q
```

Expected: all focused tests pass.

- [x] **Step 2: Run the full backend suite**

```bash
cd backend
source .venv/bin/activate
pytest
```

Expected: zero failures.

- [x] **Step 3: Run lint and formatting checks**

```bash
cd backend
source .venv/bin/activate
ruff check .
ruff format --check \
  app/integrations/etf_classification.py \
  app/integrations/yfinance_etf_profile.py \
  app/integrations/alpha_vantage.py \
  app/integrations/instrument_lookup.py \
  tests/test_etf_classification.py \
  tests/test_yfinance_etf_profile.py \
  tests/test_instrument_lookup.py \
  tests/test_m3_schema.py \
  alembic/versions/20260621_0006_fix_etf_exposure.py
```

Expected: Ruff reports no errors and all listed files are formatted.

- [x] **Step 4: Verify the diff**

```bash
git diff --check
git status --short
```

Expected: no whitespace errors; only planned files are modified.

- [x] **Step 5: Commit final cleanup if needed**

If verification required formatting-only or test-only cleanup:

```bash
git add backend
git commit -m "test: verify ETF exposure classification"
```

If no cleanup was needed, do not create an empty commit.

### Task 6: Canonical provider country geography

**Files:**
- Modify: `backend/tests/test_etf_classification.py`
- Modify: `backend/tests/test_instrument_lookup.py`
- Modify: `backend/app/integrations/etf_classification.py`
- Modify: `backend/app/integrations/fmp.py`

- [x] **Step 1: Write failing provider-normalization tests** <!-- added 2026-06-21 -->

Add table-driven tests for `normalize_country_geography` covering:

```python
("TW", EtfGeography("Taiwan", "Asia ex-Japan"))
("Taiwan", EtfGeography("Taiwan", "Asia ex-Japan"))
("JP", EtfGeography("Japan", "Japan"))
("AU", EtfGeography("Australia", "Asia Pacific"))
```

Update the FMP TSM profile expectation from country `TW`, region `Asia` to
country `Taiwan`, region `Asia ex-Japan`.

- [x] **Step 2: Run tests and verify RED** <!-- added 2026-06-21 -->

Run from `backend/`:

```bash
source .venv/bin/activate
pytest tests/test_etf_classification.py \
  tests/test_instrument_lookup.py::test_fmp_profile_returns_rich_instrument_metadata -q
```

Expected: FAIL because `normalize_country_geography` does not exist and FMP
still uses its broad region table.

- [x] **Step 3: Implement canonical normalization** <!-- added 2026-06-21 -->

Add exact provider-country aliases to `etf_classification.py`:

```python
PROVIDER_COUNTRY_ALIASES = {
    "TW": ("Taiwan", "Asia ex-Japan"),
    "TAIWAN": ("Taiwan", "Asia ex-Japan"),
    "JP": ("Japan", "Japan"),
    "JAPAN": ("Japan", "Japan"),
    "AU": ("Australia", "Asia Pacific"),
    "AUSTRALIA": ("Australia", "Asia Pacific"),
}
```

Include the existing supported FMP countries, using canonical full country
names and the same regions as ETF country exposure. Implement:

```python
def normalize_country_geography(country: str | None) -> EtfGeography:
    normalized = normalize_hint(country).upper()
    canonical = PROVIDER_COUNTRY_ALIASES.get(normalized)
    return EtfGeography(*canonical) if canonical else EtfGeography(country, None)
```

Use this helper in `FmpInstrumentLookupClient.result_from_profile_payload` for
both returned country and region, removing `REGIONS_BY_COUNTRY`.

- [x] **Step 4: Run tests and verify GREEN** <!-- added 2026-06-21 -->

Run the command from Step 2.

Expected: all selected tests pass.

- [x] **Step 5: Commit provider normalization** <!-- added 2026-06-21 -->

```bash
git add backend/app/integrations/etf_classification.py \
  backend/app/integrations/fmp.py \
  backend/tests/test_etf_classification.py \
  backend/tests/test_instrument_lookup.py
git commit -m "fix: normalize provider country regions"
```

### Task 7: AAXJ exposure inference and stored-data migration

**Files:**
- Modify: `backend/tests/test_etf_classification.py`
- Modify: `backend/tests/test_yfinance_etf_profile.py`
- Create: `backend/alembic/versions/20260621_0007_normalize_asia_regions.py`
- Modify: `backend/tests/test_m3_schema.py`

- [x] **Step 1: Write failing AAXJ and migration tests** <!-- added 2026-06-21 -->

Add classifier and yfinance-profile cases for:

```python
"iShares MSCI All Country Asia ex Japan ETF"
```

Both must return region `Asia ex-Japan` with no single country. Add a migration
test that inserts:

```text
TSM | country TW | region Asia
AAXJ | asset_class ETF | name iShares MSCI All Country Asia ex Japan ETF
     | country US | region Asia
EWJ | country JP | region Asia
```

After upgrading to `0007`, assert TSM is `Taiwan / Asia ex-Japan`, AAXJ is
`NULL / Asia ex-Japan`, and EWJ is `Japan / Japan`.

- [x] **Step 2: Run tests and verify RED** <!-- added 2026-06-21 -->

Run:

```bash
source .venv/bin/activate
pytest tests/test_etf_classification.py \
  tests/test_yfinance_etf_profile.py \
  tests/test_m3_schema.py -q
```

Expected: migration test fails because revision `0007` does not exist. Any AAXJ
classifier failure must be fixed before continuing; if it already passes, keep
the regression test as proof of existing general inference.

- [x] **Step 3: Add general data migration** <!-- added 2026-06-21 -->

Create revision `20260621_0007`, down revision `20260621_0006`. Use general SQL:

```sql
UPDATE instruments
SET country = 'Taiwan', region = 'Asia ex-Japan'
WHERE UPPER(country) IN ('TW', 'TAIWAN');

UPDATE instruments
SET country = 'Japan', region = 'Japan'
WHERE UPPER(country) IN ('JP', 'JAPAN');

UPDATE instruments
SET country = NULL, region = 'Asia ex-Japan'
WHERE UPPER(asset_class) = 'ETF'
  AND (
    LOWER(name) LIKE '%asia%ex%japan%'
    OR LOWER(name) LIKE '%pacific%ex%japan%'
  );
```

Include equivalent general updates for supported non-Japan Asian country codes
currently mapped to broad `Asia`, and Australia/New Zealand to `Asia Pacific`.
Keep downgrade non-destructive.

- [x] **Step 4: Run tests and verify GREEN** <!-- added 2026-06-21 -->

Run the command from Step 2.

Expected: all selected tests pass.

- [x] **Step 5: Commit inference and migration** <!-- added 2026-06-21 -->

```bash
git add backend/tests/test_etf_classification.py \
  backend/tests/test_yfinance_etf_profile.py \
  backend/tests/test_m3_schema.py \
  backend/alembic/versions/20260621_0007_normalize_asia_regions.py
git commit -m "fix: migrate canonical Asia regions"
```

### Task 8: Full Asia classification verification

**Files:**
- Review all files changed in Tasks 6-7.

- [x] **Step 1: Run focused tests** <!-- added 2026-06-21 -->

```bash
cd backend
source .venv/bin/activate
pytest tests/test_etf_classification.py \
  tests/test_instrument_lookup.py \
  tests/test_yfinance_etf_profile.py \
  tests/test_holdings_api.py \
  tests/test_m3_schema.py -q
```

Expected: all focused tests pass.

- [x] **Step 2: Run full backend gates** <!-- added 2026-06-21 -->

```bash
ruff check .
ruff format --check \
  app/integrations/etf_classification.py \
  app/integrations/fmp.py \
  tests/test_etf_classification.py \
  tests/test_instrument_lookup.py \
  tests/test_yfinance_etf_profile.py \
  tests/test_m3_schema.py \
  alembic/versions/20260621_0007_normalize_asia_regions.py
pytest
```

Expected: lint and changed-file formatting clean; all backend tests pass. The
repository has unrelated pre-existing formatting drift outside these files.

- [x] **Step 3: Review mappings and migration diff** <!-- added 2026-06-21 -->

```bash
rg -n '"Asia"|Asia ex-Japan|Asia Pacific|Japan' \
  app/integrations tests alembic/versions/20260621_0007_normalize_asia_regions.py
git diff --check
git status --short
```

Expected: provider mappings use canonical regions, migration is general rather
than symbol-specific, and `PR_DESCRIPTION.md` remains untouched.

- [x] **Step 4: Run frontend safety gates** <!-- added 2026-06-21 -->

```bash
cd ../frontend
npm run lint
npm run test
npm run build
```

Expected: all frontend gates pass because region labels are API data.

- [x] **Step 5: Commit verification cleanup if required** <!-- added 2026-06-21 -->

If verification changes formatting or tests:

```bash
git add backend frontend docs/superpowers/plans/2026-06-21-etf-exposure-classification.md
git commit -m "test: verify canonical Asia regions"
```

If no cleanup is required, commit only the completed tracker update.
