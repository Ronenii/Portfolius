# Auto-Computed Expected Annual Return Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the manually-entered `expected_annual_return` profile field with a value computed from the user's actual portfolio — each holding's own trailing-5-year historical CAGR where at least 3 years of it exists, falling back to an asset-class bucket table otherwise.

**Architecture:** A new `MarketDataClient` method computes historical CAGR from yfinance data; a new monthly scheduled job (plus a one-time startup bootstrap) precomputes and stores it per instrument; a new pure function in `portfolio_math.py` combines each holding's stored return (or the bucket fallback) into a market-value-weighted average that `build_projection_for_user` uses in place of the removed manual field.

**Tech Stack:** FastAPI + SQLAlchemy + Alembic + Pydantic + `Decimal` (backend), yfinance (already a dependency), GitHub Actions (scheduled workflow), React + TypeScript (frontend removal only).

## Global Constraints

- Historical CAGR lookback window: 5 years (`period="5y"` in yfinance). Minimum span to trust the result: 3 years — below that, treat as no data.
- Bucket fallback table (used only when an instrument has no computed historical return): `CRYPTO` → 12%, `COMMODITY` → 5%, `CASH`/`MONEY MARKET` → 2%, everything else (including `STOCK`/`ETF`/`FUND`/`ADR` and unrecognized labels) → 8% (`EQUITY_LIKE_RETURN`). Bucket matching is case/whitespace-insensitive.
- The historical-return refresh job runs monthly via a new scheduled GitHub Actions workflow, structurally identical to the existing `refresh-prices.yml` (same `PORTFOLIUS_API_URL`/`PORTFOLIUS_SCHEDULER_SECRET` secrets), hitting a new scheduler-secret-only endpoint (no per-user variant).
- A one-time startup-hook bootstrap (in `backend/app/main.py`) runs the refresh immediately if it has never run before (every instrument's `historical_return_updated_at` is still `None`), as a non-blocking background thread — confirmed safe because the backend is a single-instance deployment.
- The manual `expected_annual_return` profile field is removed entirely: DB column (migration), Pydantic schemas, SQLAlchemy model, both profile forms (frontend), and all references in tests.
- All new Decimal percentages are quantized to 2 places with `ROUND_HALF_UP`, matching this codebase's existing convention (e.g. `app/domain/projection.py`'s `_quantize`).

---

### Task 1: Historical CAGR computation (`YFinanceMarketDataClient`)

**Files:**
- Modify: `backend/app/integrations/market_data.py`
- Modify: `backend/app/integrations/yfinance_client.py`
- Modify: `backend/tests/test_price_refresh.py`

**Interfaces:**
- Consumes: nothing new — existing `normalize_code`, `latest_non_null_close`, `parse_finite_decimal`, `normalize_date` helpers already in `yfinance_client.py`.
- Produces: `MarketDataClient.get_historical_annualized_return(symbol: str, exchange: str, currency_hint: str | None) -> Decimal | None` (Protocol method) and its implementation on `YFinanceMarketDataClient`. Task 4's job calls this through the `MarketDataClient` protocol.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_price_refresh.py` (after the existing `CurrencyFallbackTicker`/`ScriptedMarketDataClient` class definitions, before `add_holding`):

```python
class HistoricalReturnHistory:
    empty = False

    @property
    def index(self) -> list[date]:
        return [date(2021, 1, 4), date(2023, 6, 15), date(2026, 1, 2)]

    def __getitem__(self, column_name: str) -> list[float | None]:
        assert column_name == "Close"
        return [100.0, 150.0, 200.0]


class HistoricalReturnTicker:
    fast_info = {"currency": "usd"}

    def __init__(self, symbol: str) -> None:
        self.symbol = symbol

    def history(self, period: str) -> HistoricalReturnHistory:
        assert period == "5y"
        return HistoricalReturnHistory()


class ThinHistoryHistory:
    empty = False

    @property
    def index(self) -> list[date]:
        return [date(2024, 6, 1), date(2026, 1, 2)]

    def __getitem__(self, column_name: str) -> list[float | None]:
        assert column_name == "Close"
        return [100.0, 150.0]


class ThinHistoryTicker:
    fast_info: dict[str, str] = {}

    def __init__(self, symbol: str) -> None:
        self.symbol = symbol

    def history(self, period: str) -> ThinHistoryHistory:
        assert period == "5y"
        return ThinHistoryHistory()


class SingleValidCloseHistory:
    empty = False

    @property
    def index(self) -> list[date]:
        return [date(2021, 1, 4), date(2026, 1, 2)]

    def __getitem__(self, column_name: str) -> list[float | None]:
        assert column_name == "Close"
        return [float("nan"), 200.0]


class SingleValidCloseTicker:
    fast_info: dict[str, str] = {}

    def __init__(self, symbol: str) -> None:
        self.symbol = symbol

    def history(self, period: str) -> SingleValidCloseHistory:
        assert period == "5y"
        return SingleValidCloseHistory()


class EmptyHistoricalTicker:
    fast_info: dict[str, str] = {}

    def __init__(self, symbol: str) -> None:
        self.symbol = symbol

    def history(self, period: str) -> EmptyHistory:
        assert period == "5y"
        return EmptyHistory()
```

Then append these test functions (after the existing `test_yfinance_adapter_*` tests, before `test_refresh_requests_each_distinct_user_instrument_once`):

```python
def test_yfinance_adapter_computes_annualized_return_over_full_history() -> None:
    client = YFinanceMarketDataClient(
        yfinance_module=SimpleNamespace(Ticker=HistoricalReturnTicker),
    )

    annualized_return = client.get_historical_annualized_return(
        "voo", "nysearca", "USD"
    )

    assert annualized_return == Decimal("14.89")


def test_yfinance_adapter_returns_none_when_history_spans_under_three_years() -> None:
    client = YFinanceMarketDataClient(
        yfinance_module=SimpleNamespace(Ticker=ThinHistoryTicker),
    )

    assert client.get_historical_annualized_return("VOO", "NYSEARCA", "USD") is None


def test_yfinance_adapter_returns_none_with_fewer_than_two_valid_closes() -> None:
    client = YFinanceMarketDataClient(
        yfinance_module=SimpleNamespace(Ticker=SingleValidCloseTicker),
    )

    assert client.get_historical_annualized_return("VOO", "NYSEARCA", "USD") is None


def test_yfinance_adapter_historical_return_none_for_empty_history() -> None:
    client = YFinanceMarketDataClient(
        yfinance_module=SimpleNamespace(Ticker=EmptyHistoricalTicker),
    )

    assert client.get_historical_annualized_return("VOO", "NYSEARCA", "USD") is None
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && pytest tests/test_price_refresh.py -v`
Expected: FAIL — `AttributeError: 'YFinanceMarketDataClient' object has no attribute 'get_historical_annualized_return'`.

- [ ] **Step 3: Add the Protocol method**

In `backend/app/integrations/market_data.py`, find:

```python
class MarketDataClient(Protocol):
    def get_latest_close(
        self,
        symbol: str,
        exchange: str,
        currency_hint: str | None,
    ) -> MarketPrice | None:
        ...
```

Replace with:

```python
class MarketDataClient(Protocol):
    def get_latest_close(
        self,
        symbol: str,
        exchange: str,
        currency_hint: str | None,
    ) -> MarketPrice | None:
        ...

    def get_historical_annualized_return(
        self,
        symbol: str,
        exchange: str,
        currency_hint: str | None,
    ) -> Decimal | None:
        ...
```

- [ ] **Step 4: Implement the yfinance adapter method**

In `backend/app/integrations/yfinance_client.py`, find the import line:

```python
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any
```

Replace with:

```python
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any
```

Right after the `normalize_code` function, add the new constants:

```python
HISTORICAL_RETURN_PERIOD = "5y"
MIN_HISTORICAL_YEARS = Decimal("3")
DAYS_PER_YEAR = Decimal("365.25")
RETURN_QUANTIZE = Decimal("0.01")
```

In the `YFinanceMarketDataClient` class, right after `get_latest_close`'s closing `)` (the method's final `return MarketPrice(...)` block), add a new method:

```python
    def get_historical_annualized_return(
        self,
        symbol: str,
        exchange: str,
        currency_hint: str | None,
    ) -> Decimal | None:
        normalized_symbol = normalize_code(symbol)
        ticker = self.yfinance_module.Ticker(normalized_symbol)
        history = ticker.history(period=HISTORICAL_RETURN_PERIOD)

        if getattr(history, "empty", False):
            return None

        first = first_non_null_close(history)
        last = latest_non_null_close(history)
        if first is None or last is None:
            return None

        start_date, start_price = first
        end_date, end_price = last
        if end_date <= start_date or start_price <= 0:
            return None

        years = Decimal((end_date - start_date).days) / DAYS_PER_YEAR
        if years < MIN_HISTORICAL_YEARS:
            return None

        growth = end_price / start_price
        annualized_growth = growth ** (Decimal(1) / years)
        return ((annualized_growth - 1) * 100).quantize(
            RETURN_QUANTIZE, rounding=ROUND_HALF_UP
        )
```

Right after the existing `latest_non_null_close` function, add its mirror-image counterpart:

```python
def first_non_null_close(history: Any) -> tuple[date, Decimal] | None:
    closes = history["Close"]
    indexes = history.index

    for raw_date, raw_close in zip(indexes, closes, strict=False):
        close_price = parse_finite_decimal(raw_close)
        if close_price is None:
            continue

        return normalize_date(raw_date), close_price

    return None
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd backend && pytest tests/test_price_refresh.py -v`
Expected: PASS (all tests in the file, including the 4 new ones).

- [ ] **Step 6: Run lint**

Run: `cd backend && ruff check .`
Expected: clean.

- [ ] **Step 7: Commit**

```bash
git add backend/app/integrations/market_data.py backend/app/integrations/yfinance_client.py backend/tests/test_price_refresh.py
git commit -m "feat: compute historical annualized return via yfinance"
```

---

### Task 2: Storage and weighted-average computation

**Files:**
- Modify: `backend/app/data/models.py`
- Create: `backend/alembic/versions/20260716_0010_add_instrument_historical_return.py`
- Modify: `backend/app/schemas/holdings.py`
- Modify: `backend/app/domain/portfolio_math.py`
- Modify: `backend/tests/test_portfolio_math.py`
- Modify: `backend/tests/test_m3_schema.py`

**Interfaces:**
- Consumes: nothing from Task 1 (independent).
- Produces: `Instrument.historical_annual_return: Decimal | None`, `Instrument.historical_return_updated_at: datetime | None` (model attributes); `InstrumentResponse.historical_annual_return: Decimal | None` (schema field, flows into `PortfolioHoldingSnapshot.instrument`); `compute_weighted_average_return(holdings: list[PortfolioHoldingSnapshot], base_currency: str) -> Decimal | None` and the constants `ASSET_CLASS_DEFAULT_RETURN: dict[str, Decimal]` / `EQUITY_LIKE_RETURN: Decimal` in `portfolio_math.py`. Task 3 calls `compute_weighted_average_return`; Task 4 writes to the two new model attributes.

- [ ] **Step 1: Write the failing tests for the migration**

Append to `backend/tests/test_m3_schema.py` (after `test_projection_profile_fields_upgrade_and_downgrade`, before `test_m3_assistant_tables_upgrade_and_downgrade`):

```python
def test_instrument_historical_return_upgrade_and_downgrade(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_url = (
        f"sqlite+pysqlite:///{tmp_path / 'instrument_historical_return_schema.db'}"
    )
    monkeypatch.setenv("DATABASE_URL", database_url)
    get_settings.cache_clear()
    config = alembic_config(database_url)

    command.upgrade(config, "head")

    engine = create_engine(database_url)
    columns = {
        column["name"] for column in inspect(engine).get_columns("instruments")
    }
    assert {"historical_annual_return", "historical_return_updated_at"}.issubset(
        columns
    )

    command.downgrade(config, "20260707_0009")

    downgraded_columns = {
        column["name"] for column in inspect(engine).get_columns("instruments")
    }
    assert "historical_annual_return" not in downgraded_columns
    assert "historical_return_updated_at" not in downgraded_columns
    get_settings.cache_clear()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd backend && pytest tests/test_m3_schema.py::test_instrument_historical_return_upgrade_and_downgrade -v`
Expected: FAIL — `head` does not include `historical_annual_return`/`historical_return_updated_at` on `instruments`.

- [ ] **Step 3: Add the migration**

Create `backend/alembic/versions/20260716_0010_add_instrument_historical_return.py`:

```python
"""add instrument historical return

Revision ID: 20260716_0010
Revises: 20260707_0009
Create Date: 2026-07-16

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260716_0010"
down_revision: str | None = "20260707_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "instruments",
        sa.Column("historical_annual_return", sa.Numeric(20, 8), nullable=True),
    )
    op.add_column(
        "instruments",
        sa.Column(
            "historical_return_updated_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("instruments", "historical_return_updated_at")
    op.drop_column("instruments", "historical_annual_return")
```

- [ ] **Step 4: Add the columns to the `Instrument` model**

In `backend/app/data/models.py`, find:

```python
    metadata_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    holdings: Mapped[list["Holding"]] = relationship(
```

Replace with:

```python
    metadata_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    historical_annual_return: Mapped[Decimal | None] = mapped_column(
        Numeric(20, 8),
        nullable=True,
    )
    historical_return_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    holdings: Mapped[list["Holding"]] = relationship(
```

- [ ] **Step 5: Run the migration test to verify it passes**

Run: `cd backend && pytest tests/test_m3_schema.py -v`
Expected: PASS (all tests in the file).

- [ ] **Step 6: Add `historical_annual_return` to `InstrumentResponse`**

In `backend/app/schemas/holdings.py`, find:

```python
class InstrumentResponse(BaseModel):
    id: int
    symbol: str
    name: str | None
    exchange: str
    currency: str | None
    asset_class: str | None
    sector: str | None
    country: str | None
    region: str | None

    model_config = ConfigDict(from_attributes=True)
```

Replace with:

```python
class InstrumentResponse(BaseModel):
    id: int
    symbol: str
    name: str | None
    exchange: str
    currency: str | None
    asset_class: str | None
    sector: str | None
    country: str | None
    region: str | None
    historical_annual_return: Decimal | None

    model_config = ConfigDict(from_attributes=True)

    @field_serializer("historical_annual_return")
    def serialize_historical_annual_return(self, value: Decimal | None) -> str | None:
        return None if value is None else str(value)
```

- [ ] **Step 7: Write the failing tests for `compute_weighted_average_return`**

In `backend/tests/test_portfolio_math.py`, find the `instrument` helper:

```python
def instrument(
    symbol: str,
    currency: str | None = "USD",
    exchange: str = "NYSEARCA",
) -> Instrument:
    return Instrument(
        id=len(symbol),
        symbol=symbol,
        name=f"{symbol} Fund",
        exchange=exchange,
        currency=currency,
        asset_class="ETF",
        sector="Broad Market",
        country="United States",
        region="North America",
    )
```

Replace with (adds two optional, backward-compatible parameters):

```python
def instrument(
    symbol: str,
    currency: str | None = "USD",
    exchange: str = "NYSEARCA",
    asset_class: str | None = "ETF",
    historical_annual_return: Decimal | None = None,
) -> Instrument:
    return Instrument(
        id=len(symbol),
        symbol=symbol,
        name=f"{symbol} Fund",
        exchange=exchange,
        currency=currency,
        asset_class=asset_class,
        sector="Broad Market",
        country="United States",
        region="North America",
        historical_annual_return=historical_annual_return,
    )
```

Find the import line:

```python
from app.data.models import Holding, Instrument, Price, Profile
from app.domain.portfolio_math import build_portfolio_snapshot
```

Replace with:

```python
from app.data.models import Holding, Instrument, Price, Profile
from app.domain.portfolio_math import (
    ASSET_CLASS_DEFAULT_RETURN,
    EQUITY_LIKE_RETURN,
    build_portfolio_snapshot,
    compute_weighted_average_return,
)
```

Append these test functions at the end of the file:

```python
def test_weighted_average_uses_stored_historical_return_over_bucket() -> None:
    voo = instrument(
        "VOO", asset_class="ETF", historical_annual_return=Decimal("11.50")
    )
    snapshot = build_portfolio_snapshot(
        profile(),
        [holding(1, voo, quantity="10", average_cost="80")],
        {voo.id: price(voo, "100")},
    )

    result = compute_weighted_average_return(
        snapshot.holdings, snapshot.summary.base_currency
    )

    assert result == Decimal("11.50")


def test_weighted_average_falls_back_to_asset_class_bucket() -> None:
    btc = instrument("BTCUSD", asset_class="CRYPTO")
    snapshot = build_portfolio_snapshot(
        profile(),
        [holding(1, btc, quantity="1", average_cost="20000")],
        {btc.id: price(btc, "25000")},
    )

    result = compute_weighted_average_return(
        snapshot.holdings, snapshot.summary.base_currency
    )

    assert result == ASSET_CLASS_DEFAULT_RETURN["CRYPTO"]


def test_weighted_average_bucket_matching_is_case_and_whitespace_insensitive() -> None:
    gold = instrument("GLD", asset_class="  commodity ")
    snapshot = build_portfolio_snapshot(
        profile(),
        [holding(1, gold, quantity="10", average_cost="150")],
        {gold.id: price(gold, "180")},
    )

    result = compute_weighted_average_return(
        snapshot.holdings, snapshot.summary.base_currency
    )

    assert result == ASSET_CLASS_DEFAULT_RETURN["COMMODITY"]


def test_weighted_average_defaults_unrecognized_asset_class_to_equity_like() -> None:
    mystery = instrument("XYZ", asset_class="SOMETHING_ELSE")
    snapshot = build_portfolio_snapshot(
        profile(),
        [holding(1, mystery, quantity="5", average_cost="40")],
        {mystery.id: price(mystery, "50")},
    )

    result = compute_weighted_average_return(
        snapshot.holdings, snapshot.summary.base_currency
    )

    assert result == EQUITY_LIKE_RETURN


def test_weighted_average_combines_multiple_holdings_by_market_value() -> None:
    voo = instrument(
        "VOO", asset_class="ETF", historical_annual_return=Decimal("10.00")
    )
    btc = instrument("BTCUSD", asset_class="CRYPTO")
    snapshot = build_portfolio_snapshot(
        profile(),
        [
            holding(1, voo, quantity="10", average_cost="80"),
            holding(2, btc, quantity="0.5", average_cost="1500"),
        ],
        {voo.id: price(voo, "100"), btc.id: price(btc, "2000")},
    )

    result = compute_weighted_average_return(
        snapshot.holdings, snapshot.summary.base_currency
    )

    assert result == Decimal("11.00")


def test_weighted_average_excludes_unpriced_and_non_base_currency_holdings() -> None:
    voo = instrument(
        "VOO", asset_class="ETF", historical_annual_return=Decimal("9.00")
    )
    unpriced = instrument("ZZZ", asset_class="ETF")
    foreign = instrument("EFA", currency="EUR", asset_class="ETF")
    snapshot = build_portfolio_snapshot(
        profile(base_currency="USD"),
        [
            holding(1, voo, quantity="10", average_cost="80"),
            holding(2, unpriced, quantity="5", average_cost="50"),
            holding(3, foreign, quantity="4", average_cost="60"),
        ],
        {voo.id: price(voo, "100"), foreign.id: price(foreign, "70")},
    )

    result = compute_weighted_average_return(
        snapshot.holdings, snapshot.summary.base_currency
    )

    assert result == Decimal("9.00")


def test_weighted_average_returns_none_when_no_holdings_qualify() -> None:
    unpriced = instrument("ZZZ", asset_class="ETF")
    snapshot = build_portfolio_snapshot(
        profile(),
        [holding(1, unpriced, quantity="5", average_cost="50")],
        {},
    )

    result = compute_weighted_average_return(
        snapshot.holdings, snapshot.summary.base_currency
    )

    assert result is None


def test_weighted_average_returns_none_for_empty_portfolio() -> None:
    result = compute_weighted_average_return([], "USD")

    assert result is None
```

- [ ] **Step 8: Run the tests to verify they fail**

Run: `cd backend && pytest tests/test_portfolio_math.py -v`
Expected: FAIL — `ImportError: cannot import name 'compute_weighted_average_return'`.

- [ ] **Step 9: Implement `compute_weighted_average_return`**

In `backend/app/domain/portfolio_math.py`, find the import line:

```python
from decimal import Decimal

from app.data.models import Holding, Price, Profile
```

Replace with:

```python
from decimal import ROUND_HALF_UP, Decimal

from app.data.models import Holding, Price, Profile
```

Right after the imports (before `def build_portfolio_snapshot`), add:

```python
# Fallback assumed long-run annual returns (%) by asset_class, used only
# when an instrument has no computed `historical_annual_return` yet (see
# app/domain/historical_return_refresh.py). Keys are matched
# case/whitespace-insensitively against `Instrument.asset_class`.
ASSET_CLASS_DEFAULT_RETURN: dict[str, Decimal] = {
    "CRYPTO": Decimal("12"),
    "COMMODITY": Decimal("5"),
    "CASH": Decimal("2"),
    "MONEY MARKET": Decimal("2"),
}
# STOCK/ETF/FUND/ADR and any unrecognized/missing asset_class label.
EQUITY_LIKE_RETURN = Decimal("8")

RETURN_QUANTIZE = Decimal("0.01")
```

At the end of the file, add:

```python
def compute_weighted_average_return(
    holdings: list[PortfolioHoldingSnapshot], base_currency: str
) -> Decimal | None:
    qualifying = [
        held
        for held in holdings
        if held.market_value is not None
        and held.instrument.currency == base_currency
    ]
    if not qualifying:
        return None

    total_value = sum((held.market_value for held in qualifying), Decimal("0"))
    if total_value <= 0:
        return None

    weighted_sum = Decimal("0")
    for held in qualifying:
        rate = held.instrument.historical_annual_return
        if rate is None:
            normalized_class = (
                held.instrument.asset_class.strip().upper()
                if held.instrument.asset_class
                else None
            )
            rate = ASSET_CLASS_DEFAULT_RETURN.get(normalized_class, EQUITY_LIKE_RETURN)
        weighted_sum += (held.market_value / total_value) * rate

    return weighted_sum.quantize(RETURN_QUANTIZE, rounding=ROUND_HALF_UP)
```

- [ ] **Step 10: Run the tests to verify they pass**

Run: `cd backend && pytest tests/test_portfolio_math.py -v`
Expected: PASS (all tests in the file).

- [ ] **Step 11: Run the full backend suite and lint**

Run: `cd backend && pytest && ruff check .`
Expected: both clean/passing.

- [ ] **Step 12: Commit**

```bash
git add backend/app/data/models.py backend/alembic/versions/20260716_0010_add_instrument_historical_return.py backend/app/schemas/holdings.py backend/app/domain/portfolio_math.py backend/tests/test_portfolio_math.py backend/tests/test_m3_schema.py
git commit -m "feat: store per-instrument historical returns and compute a weighted portfolio average"
```

---

### Task 3: Wire the computed return into the projection

**Files:**
- Modify: `backend/app/domain/portfolio_service.py`
- Modify: `backend/tests/test_projection_api.py`

**Interfaces:**
- Consumes: Task 2's `compute_weighted_average_return(holdings, base_currency) -> Decimal | None`.
- Produces: nothing new — `build_projection_for_user`'s public signature is unchanged, only its internal resolution of `resolved_annual_return` changes.

- [ ] **Step 1: Update the test that currently relies on the manual field taking precedence**

In `backend/tests/test_projection_api.py`, find:

```python
def test_projection_uses_profile_stored_values_by_default(
    authenticated_user: AuthenticatedUser,
    db_session: Session,
) -> None:
    add_profile(
        db_session,
        authenticated_user.user_id,
        time_horizon="10+ years",
        investment_frequency="monthly",
        goal_target_amount="50000",
        contribution_amount="200",
        expected_annual_return="7",
    )
    add_holding(db_session, authenticated_user.user_id, "VOO")

    response = read_portfolio_projection(authenticated_user, db_session)

    assert response.start_value == Decimal("1000")
    assert response.target_amount == Decimal("50000")
    assert response.contribution_amount == Decimal("200")
    assert response.contribution_frequency == "monthly"
    assert response.annual_return_expected == Decimal("7")
    assert response.horizon_years == 15
```

Replace with (the profile's manual `expected_annual_return` will no longer take precedence once Step 3 lands — `VOO`'s default `asset_class="ETF"` has no stored historical return, so it resolves to the `EQUITY_LIKE_RETURN` bucket, `8`):

```python
def test_projection_uses_profile_stored_values_by_default(
    authenticated_user: AuthenticatedUser,
    db_session: Session,
) -> None:
    add_profile(
        db_session,
        authenticated_user.user_id,
        time_horizon="10+ years",
        investment_frequency="monthly",
        goal_target_amount="50000",
        contribution_amount="200",
    )
    add_holding(db_session, authenticated_user.user_id, "VOO")

    response = read_portfolio_projection(authenticated_user, db_session)

    assert response.start_value == Decimal("1000")
    assert response.target_amount == Decimal("50000")
    assert response.contribution_amount == Decimal("200")
    assert response.contribution_frequency == "monthly"
    assert response.annual_return_expected == Decimal("8")
    assert response.horizon_years == 15
```

Then add a new test right after it, proving the computed value is actually used when available:

```python
def test_projection_uses_computed_weighted_average_return(
    authenticated_user: AuthenticatedUser,
    db_session: Session,
) -> None:
    add_profile(db_session, authenticated_user.user_id, risk_tolerance="conservative")
    voo = add_holding(db_session, authenticated_user.user_id, "VOO")
    voo.instrument.historical_annual_return = Decimal("11.50")
    db_session.commit()

    response = read_portfolio_projection(authenticated_user, db_session)

    assert response.annual_return_expected == Decimal("11.50")
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && pytest tests/test_projection_api.py -v`
Expected: FAIL — `test_projection_uses_profile_stored_values_by_default` still gets `7` (the old manual-field precedence), and `test_projection_uses_computed_weighted_average_return` gets the risk-tolerance default (`4`) instead of `11.50`.

- [ ] **Step 3: Update the resolution logic**

In `backend/app/domain/portfolio_service.py`, find the import line:

```python
from app.domain.portfolio_math import build_portfolio_snapshot
```

Replace with:

```python
from app.domain.portfolio_math import (
    build_portfolio_snapshot,
    compute_weighted_average_return,
)
```

Find:

```python
    if annual_return is not None:
        resolved_annual_return = annual_return
    elif profile.expected_annual_return is not None:
        resolved_annual_return = profile.expected_annual_return
    else:
        resolved_annual_return = RISK_TOLERANCE_DEFAULT_RETURN.get(
            profile.risk_tolerance, DEFAULT_ANNUAL_RETURN
        )
```

Replace with:

```python
    if annual_return is not None:
        resolved_annual_return = annual_return
    else:
        resolved_annual_return = compute_weighted_average_return(
            snapshot.holdings, snapshot.summary.base_currency
        ) or RISK_TOLERANCE_DEFAULT_RETURN.get(
            profile.risk_tolerance, DEFAULT_ANNUAL_RETURN
        )
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && pytest tests/test_projection_api.py -v`
Expected: PASS (all tests in the file).

- [ ] **Step 5: Run the full backend suite and lint**

Run: `cd backend && pytest && ruff check .`
Expected: both clean/passing.

- [ ] **Step 6: Commit**

```bash
git add backend/app/domain/portfolio_service.py backend/tests/test_projection_api.py
git commit -m "feat: use the computed weighted-average return in the goal projection"
```

---

### Task 4: Monthly historical-return refresh job

**Files:**
- Create: `backend/app/domain/historical_return_refresh.py`
- Modify: `backend/app/schemas/jobs.py`
- Modify: `backend/app/api/v1/jobs.py`
- Create: `.github/workflows/refresh-historical-returns.yml`
- Create: `backend/tests/test_historical_return_refresh.py`
- Modify: `backend/tests/test_portfolio_api.py`

**Interfaces:**
- Consumes: Task 1's `MarketDataClient.get_historical_annualized_return`; Task 2's `Instrument.historical_annual_return`/`historical_return_updated_at`.
- Produces: `refresh_historical_returns_for_all_instruments(db: Session, market_data_client: MarketDataClient) -> HistoricalReturnRefreshResult` and endpoint `POST /api/v1/jobs/refresh-historical-returns`. Task 5 calls `refresh_historical_returns_for_all_instruments` directly.

- [ ] **Step 1: Write the failing domain-function tests**

Create `backend/tests/test_historical_return_refresh.py`:

```python
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from app.data.models import Instrument
from app.domain.historical_return_refresh import (
    refresh_historical_returns_for_all_instruments,
)


class ScriptedHistoricalReturnClient:
    def __init__(
        self,
        returns: dict[str, Decimal | None],
        failing_symbols: set[str] | None = None,
    ) -> None:
        self.returns = returns
        self.failing_symbols = failing_symbols or set()
        self.requests: list[tuple[str, str, str | None]] = []

    def get_historical_annualized_return(
        self,
        symbol: str,
        exchange: str,
        currency_hint: str | None,
    ) -> Decimal | None:
        self.requests.append((symbol, exchange, currency_hint))
        if symbol in self.failing_symbols:
            raise RuntimeError("provider down")
        return self.returns.get(symbol)


def instrument(symbol: str, currency: str | None = "USD") -> Instrument:
    return Instrument(
        symbol=symbol,
        name=f"{symbol} Fund",
        exchange="NYSEARCA",
        currency=currency,
        asset_class="ETF",
    )


def test_refresh_stores_computed_return_and_stamps_updated_at(
    db_session: Session,
) -> None:
    voo = instrument("VOO")
    db_session.add(voo)
    db_session.commit()
    client = ScriptedHistoricalReturnClient({"VOO": Decimal("14.89")})
    before = datetime.now(UTC)

    result = refresh_historical_returns_for_all_instruments(db_session, client)

    db_session.refresh(voo)
    assert result.requested == 1
    assert result.updated == 1
    assert result.skipped == 0
    assert result.failed == 0
    assert voo.historical_annual_return == Decimal("14.89")
    assert voo.historical_return_updated_at is not None
    assert voo.historical_return_updated_at >= before
    assert client.requests == [("VOO", "NYSEARCA", "USD")]


def test_refresh_skips_instruments_the_client_returns_none_for(
    db_session: Session,
) -> None:
    btc = instrument("BTC-USD", currency=None)
    db_session.add(btc)
    db_session.commit()
    client = ScriptedHistoricalReturnClient({"BTC-USD": None})

    result = refresh_historical_returns_for_all_instruments(db_session, client)

    db_session.refresh(btc)
    assert result.requested == 1
    assert result.updated == 0
    assert result.skipped == 1
    assert result.failed == 0
    assert btc.historical_annual_return is None
    assert btc.historical_return_updated_at is None


def test_refresh_counts_failures_without_stopping_the_batch(
    db_session: Session,
) -> None:
    voo = instrument("VOO")
    bnd = instrument("BND")
    db_session.add_all([voo, bnd])
    db_session.commit()
    client = ScriptedHistoricalReturnClient(
        {"BND": Decimal("3.50")},
        failing_symbols={"VOO"},
    )

    result = refresh_historical_returns_for_all_instruments(db_session, client)

    db_session.refresh(voo)
    db_session.refresh(bnd)
    assert result.requested == 2
    assert result.updated == 1
    assert result.skipped == 0
    assert result.failed == 1
    assert voo.historical_annual_return is None
    assert bnd.historical_annual_return == Decimal("3.50")
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && pytest tests/test_historical_return_refresh.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.domain.historical_return_refresh'`.

- [ ] **Step 3: Add the result schema**

In `backend/app/schemas/jobs.py`, find:

```python
from pydantic import BaseModel


class MetadataRefreshResult(BaseModel):
    requested: int
    updated: int
    skipped: int
    failed: int
```

Replace with:

```python
from pydantic import BaseModel


class MetadataRefreshResult(BaseModel):
    requested: int
    updated: int
    skipped: int
    failed: int


class HistoricalReturnRefreshResult(BaseModel):
    requested: int
    updated: int
    skipped: int
    failed: int
```

- [ ] **Step 4: Implement the domain function**

Create `backend/app/domain/historical_return_refresh.py`:

```python
import logging
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.data.models import Instrument
from app.data.repositories.instruments import list_all_instruments
from app.integrations.market_data import MarketDataClient
from app.schemas.jobs import HistoricalReturnRefreshResult

logger = logging.getLogger(__name__)


def refresh_historical_returns_for_all_instruments(
    db: Session,
    market_data_client: MarketDataClient,
) -> HistoricalReturnRefreshResult:
    instruments = list_all_instruments(db)
    updated = 0
    skipped = 0
    failed = 0

    for instrument in instruments:
        try:
            annualized_return = market_data_client.get_historical_annualized_return(
                instrument.symbol,
                instrument.exchange,
                instrument.currency,
            )
        except Exception:
            logger.exception(
                "Historical return refresh failed for %s", instrument.symbol
            )
            failed += 1
            continue

        if annualized_return is None:
            skipped += 1
            continue

        instrument.historical_annual_return = annualized_return
        instrument.historical_return_updated_at = datetime.now(UTC)
        updated += 1

    db.commit()
    logger.info(
        "Historical return refresh complete: "
        "requested=%d updated=%d skipped=%d failed=%d",
        len(instruments),
        updated,
        skipped,
        failed,
    )
    return HistoricalReturnRefreshResult(
        requested=len(instruments),
        updated=updated,
        skipped=skipped,
        failed=failed,
    )


def historical_returns_never_computed(db: Session) -> bool:
    return (
        db.scalar(
            select(Instrument.id).where(
                Instrument.historical_return_updated_at.is_not(None)
            )
        )
        is None
    )


def bootstrap_historical_returns_if_never_run(
    db: Session,
    market_data_client: MarketDataClient,
) -> HistoricalReturnRefreshResult | None:
    if not historical_returns_never_computed(db):
        return None
    return refresh_historical_returns_for_all_instruments(db, market_data_client)
```

(`historical_returns_never_computed`/`bootstrap_historical_returns_if_never_run` are used by Task 5 — they live here alongside the refresh function they wrap.)

- [ ] **Step 5: Run the domain-function tests to verify they pass**

Run: `cd backend && pytest tests/test_historical_return_refresh.py -v`
Expected: PASS (all 3 tests).

- [ ] **Step 6: Write the failing endpoint tests**

In `backend/tests/test_portfolio_api.py`, find the import line:

```python
from app.api.v1.jobs import refresh_etf_metadata, refresh_prices
```

Replace with:

```python
from app.api.v1.jobs import (
    refresh_etf_metadata,
    refresh_historical_returns,
    refresh_prices,
)
```

Right after the `FakeMarketDataClient` class definition, add:

```python
class FakeHistoricalReturnClient:
    def __init__(self, returns: dict[str, Decimal | None]) -> None:
        self.returns = returns

    def get_historical_annualized_return(
        self,
        symbol: str,
        exchange: str,
        currency_hint: str | None,
    ) -> Decimal | None:
        return self.returns.get(symbol)
```

Append these test functions at the end of the file:

```python
def test_historical_returns_refresh_route_is_registered_as_migration_job() -> None:
    routes = [
        route
        for route in app.routes
        if getattr(route, "path", None) == "/api/v1/jobs/refresh-historical-returns"
    ]

    assert len(routes) == 1
    dependency_calls = {
        dependency.call for dependency in routes[0].dependant.dependencies
    }
    assert get_current_user not in dependency_calls


def test_historical_returns_refresh_computes_for_all_instruments(
    authenticated_user: AuthenticatedUser,
    db_session: Session,
) -> None:
    add_profile(db_session, authenticated_user.user_id)
    ixc_holding = add_holding(db_session, authenticated_user.user_id, "IXC")
    market_data_client = FakeHistoricalReturnClient({"IXC": Decimal("9.42")})

    response = refresh_historical_returns(
        db_session,
        market_data_client,
        settings=Settings(scheduler_secret="secret"),
        scheduler_secret="secret",
    )

    db_session.refresh(ixc_holding.instrument)
    assert response.requested == 1
    assert response.updated == 1
    assert response.skipped == 0
    assert response.failed == 0
    assert ixc_holding.instrument.historical_annual_return == Decimal("9.42")


def test_historical_returns_refresh_requires_scheduler_secret(
    db_session: Session,
) -> None:
    with pytest.raises(HTTPException) as exc_info:
        refresh_historical_returns(
            db_session,
            FakeHistoricalReturnClient({}),
            settings=Settings(scheduler_secret="secret"),
        )

    assert exc_info.value.status_code == 401
```

- [ ] **Step 7: Run the endpoint tests to verify they fail**

Run: `cd backend && pytest tests/test_portfolio_api.py -v`
Expected: FAIL — `ImportError: cannot import name 'refresh_historical_returns' from 'app.api.v1.jobs'`.

- [ ] **Step 8: Add the endpoint**

In `backend/app/api/v1/jobs.py`, find the import line:

```python
from app.domain.metadata_refresh import refresh_instrument_metadata_for_all_instruments
from app.domain.price_refresh import (
    PriceRefreshResult,
    refresh_prices_for_all_users,
    refresh_prices_for_user,
)
from app.integrations.fmp import FmpInstrumentLookupClient
from app.integrations.instrument_lookup import CompositeInstrumentLookupClient
from app.integrations.market_data import MarketDataClient
from app.integrations.yfinance_client import YFinanceMarketDataClient
from app.integrations.yfinance_etf_profile import YFinanceEtfProfileClient
from app.schemas.jobs import MetadataRefreshResult
```

Replace with:

```python
from app.domain.historical_return_refresh import (
    refresh_historical_returns_for_all_instruments,
)
from app.domain.metadata_refresh import refresh_instrument_metadata_for_all_instruments
from app.domain.price_refresh import (
    PriceRefreshResult,
    refresh_prices_for_all_users,
    refresh_prices_for_user,
)
from app.integrations.fmp import FmpInstrumentLookupClient
from app.integrations.instrument_lookup import CompositeInstrumentLookupClient
from app.integrations.market_data import MarketDataClient
from app.integrations.yfinance_client import YFinanceMarketDataClient
from app.integrations.yfinance_etf_profile import YFinanceEtfProfileClient
from app.schemas.jobs import HistoricalReturnRefreshResult, MetadataRefreshResult
```

Find:

```python
@router.post(
    "/api/v1/jobs/refresh-etf-metadata",
    response_model=MetadataRefreshResult,
)
def refresh_etf_metadata(
    db: Annotated[Session, Depends(get_db)],
    lookup_client: Annotated[
        CompositeInstrumentLookupClient,
        Depends(get_instrument_lookup_client),
    ],
    settings: Annotated[Settings, Depends(get_settings)],
    scheduler_secret: Annotated[str | None, Header(alias="X-Scheduler-Secret")] = None,
) -> MetadataRefreshResult:
    if not validate_scheduler_secret(settings, scheduler_secret):
        raise unauthorized()
    return refresh_instrument_metadata_for_all_instruments(db, lookup_client)


def validate_scheduler_secret(
```

Replace with:

```python
@router.post(
    "/api/v1/jobs/refresh-etf-metadata",
    response_model=MetadataRefreshResult,
)
def refresh_etf_metadata(
    db: Annotated[Session, Depends(get_db)],
    lookup_client: Annotated[
        CompositeInstrumentLookupClient,
        Depends(get_instrument_lookup_client),
    ],
    settings: Annotated[Settings, Depends(get_settings)],
    scheduler_secret: Annotated[str | None, Header(alias="X-Scheduler-Secret")] = None,
) -> MetadataRefreshResult:
    if not validate_scheduler_secret(settings, scheduler_secret):
        raise unauthorized()
    return refresh_instrument_metadata_for_all_instruments(db, lookup_client)


@router.post(
    "/api/v1/jobs/refresh-historical-returns",
    response_model=HistoricalReturnRefreshResult,
)
def refresh_historical_returns(
    db: Annotated[Session, Depends(get_db)],
    market_data_client: Annotated[MarketDataClient, Depends(get_market_data_client)],
    settings: Annotated[Settings, Depends(get_settings)],
    scheduler_secret: Annotated[str | None, Header(alias="X-Scheduler-Secret")] = None,
) -> HistoricalReturnRefreshResult:
    if not validate_scheduler_secret(settings, scheduler_secret):
        raise unauthorized()
    return refresh_historical_returns_for_all_instruments(db, market_data_client)


def validate_scheduler_secret(
```

- [ ] **Step 9: Run the endpoint tests to verify they pass**

Run: `cd backend && pytest tests/test_portfolio_api.py -v`
Expected: PASS (all tests in the file).

- [ ] **Step 10: Add the scheduled GitHub Actions workflow**

Create `.github/workflows/refresh-historical-returns.yml`:

```yaml
name: Refresh Historical Returns

on:
  schedule:
    - cron: "0 6 1 * *"
  workflow_dispatch:

jobs:
  refresh-historical-returns:
    runs-on: ubuntu-latest
    steps:
      - name: Refresh instrument historical returns
        run: |
          if [ -z "${PORTFOLIUS_API_URL:-}" ] || [ -z "${PORTFOLIUS_SCHEDULER_SECRET:-}" ]; then
            echo "Missing PORTFOLIUS_API_URL or PORTFOLIUS_SCHEDULER_SECRET"
            exit 1
          fi

          refresh_url="${PORTFOLIUS_API_URL%/}/api/v1/jobs/refresh-historical-returns"

          curl --fail-with-body \
            --request POST \
            --header "X-Scheduler-Secret: $PORTFOLIUS_SCHEDULER_SECRET" \
            "$refresh_url"
        env:
          PORTFOLIUS_API_URL: ${{ secrets.PORTFOLIUS_API_URL }}
          PORTFOLIUS_SCHEDULER_SECRET: ${{ secrets.PORTFOLIUS_SCHEDULER_SECRET }}
```

- [ ] **Step 11: Run the full backend suite and lint**

Run: `cd backend && pytest && ruff check .`
Expected: both clean/passing.

- [ ] **Step 12: Commit**

```bash
git add backend/app/domain/historical_return_refresh.py backend/app/schemas/jobs.py backend/app/api/v1/jobs.py .github/workflows/refresh-historical-returns.yml backend/tests/test_historical_return_refresh.py backend/tests/test_portfolio_api.py
git commit -m "feat: add monthly historical-return refresh job and endpoint"
```

---

### Task 5: Startup-hook bootstrap

**Files:**
- Modify: `backend/app/main.py`
- Modify: `backend/tests/test_historical_return_refresh.py`

**Interfaces:**
- Consumes: Task 4's `historical_returns_never_computed`, `bootstrap_historical_returns_if_never_run`, `refresh_historical_returns_for_all_instruments`.
- Produces: nothing new for later tasks — this is the last piece of the historical-return mechanism.

- [ ] **Step 1: Write the failing tests**

In `backend/tests/test_historical_return_refresh.py`, find the existing import:

```python
from app.domain.historical_return_refresh import (
    refresh_historical_returns_for_all_instruments,
)
```

Replace with:

```python
from app.domain.historical_return_refresh import (
    bootstrap_historical_returns_if_never_run,
    historical_returns_never_computed,
    refresh_historical_returns_for_all_instruments,
)
```

Then append these test functions at the end of the file:

```python
def test_never_computed_is_true_for_an_empty_instruments_table(
    db_session: Session,
) -> None:
    assert historical_returns_never_computed(db_session) is True


def test_never_computed_is_true_when_every_instrument_is_null(
    db_session: Session,
) -> None:
    db_session.add(instrument("VOO"))
    db_session.commit()

    assert historical_returns_never_computed(db_session) is True


def test_never_computed_is_false_once_any_instrument_has_a_value(
    db_session: Session,
) -> None:
    voo = instrument("VOO")
    voo.historical_annual_return = Decimal("8.00")
    voo.historical_return_updated_at = datetime.now(UTC)
    db_session.add(voo)
    db_session.add(instrument("BND"))
    db_session.commit()

    assert historical_returns_never_computed(db_session) is False


def test_bootstrap_runs_the_refresh_when_never_computed(
    db_session: Session,
) -> None:
    voo = instrument("VOO")
    db_session.add(voo)
    db_session.commit()
    client = ScriptedHistoricalReturnClient({"VOO": Decimal("14.89")})

    result = bootstrap_historical_returns_if_never_run(db_session, client)

    db_session.refresh(voo)
    assert result is not None
    assert result.updated == 1
    assert voo.historical_annual_return == Decimal("14.89")


def test_bootstrap_is_a_no_op_once_already_computed(
    db_session: Session,
) -> None:
    voo = instrument("VOO")
    voo.historical_annual_return = Decimal("8.00")
    voo.historical_return_updated_at = datetime.now(UTC)
    db_session.add(voo)
    db_session.commit()
    client = ScriptedHistoricalReturnClient({"VOO": Decimal("14.89")})

    result = bootstrap_historical_returns_if_never_run(db_session, client)

    db_session.refresh(voo)
    assert result is None
    assert client.requests == []
    assert voo.historical_annual_return == Decimal("8.00")
```

- [ ] **Step 2: Run the tests to verify they pass**

These exercise functions Task 4 already implemented, so no production code changes are needed yet.

Run: `cd backend && pytest tests/test_historical_return_refresh.py -v`
Expected: PASS (all 8 tests — the 3 from Task 4 plus these 5).

- [ ] **Step 3: Wire the bootstrap into app startup**

In `backend/app/main.py`, find:

```python
import logging
import warnings

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.assistant import router as assistant_router
from app.api.v1.db_ping import router as db_ping_router
from app.api.v1.health import router as health_router
from app.api.v1.holdings import router as holdings_router
from app.api.v1.instruments import router as instruments_router
from app.api.v1.jobs import router as jobs_router
from app.api.v1.portfolio import router as portfolio_router
from app.api.v1.profile import router as profile_router
from app.api.v1.transactions import router as transactions_router
from app.core.config import get_settings
```

Replace with:

```python
import asyncio
import logging
import warnings
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.assistant import router as assistant_router
from app.api.v1.db_ping import router as db_ping_router
from app.api.v1.health import router as health_router
from app.api.v1.holdings import router as holdings_router
from app.api.v1.instruments import router as instruments_router
from app.api.v1.jobs import get_market_data_client, router as jobs_router
from app.api.v1.portfolio import router as portfolio_router
from app.api.v1.profile import router as profile_router
from app.api.v1.transactions import router as transactions_router
from app.core.config import get_settings
from app.data.database import SessionLocal
from app.domain.historical_return_refresh import (
    bootstrap_historical_returns_if_never_run,
)
```

Find:

```python
def suppress_third_party_warnings() -> None:
    # yfinance uses pd.Timestamp.utcnow() which is deprecated in pandas 2.x;
    # nothing we can do until yfinance fixes it upstream.
    warnings.filterwarnings("ignore", message=".*utcnow.*", module="yfinance")


def create_app() -> FastAPI:
    suppress_third_party_warnings()
    configure_logging()
    settings = get_settings()
    app = FastAPI(title="Portfolius API")
```

Replace with:

```python
def suppress_third_party_warnings() -> None:
    # yfinance uses pd.Timestamp.utcnow() which is deprecated in pandas 2.x;
    # nothing we can do until yfinance fixes it upstream.
    warnings.filterwarnings("ignore", message=".*utcnow.*", module="yfinance")


def run_startup_historical_return_bootstrap() -> None:
    db = SessionLocal()
    try:
        result = bootstrap_historical_returns_if_never_run(
            db, get_market_data_client()
        )
        if result is not None:
            logging.getLogger("app").info(
                "Historical return bootstrap complete: "
                "requested=%d updated=%d skipped=%d failed=%d",
                result.requested,
                result.updated,
                result.skipped,
                result.failed,
            )
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Dispatched to a thread so the (synchronous, potentially slow)
    # yfinance/DB work never blocks the event loop or delays the app
    # becoming ready. `bootstrap_historical_returns_if_never_run` itself is
    # a no-op after the very first successful run, so this is safe to fire
    # unconditionally on every restart.
    asyncio.create_task(asyncio.to_thread(run_startup_historical_return_bootstrap))
    yield


def create_app() -> FastAPI:
    suppress_third_party_warnings()
    configure_logging()
    settings = get_settings()
    app = FastAPI(title="Portfolius API", lifespan=lifespan)
```

- [ ] **Step 4: Verify the app still starts cleanly**

Run: `cd backend && python -c "from app.main import app; print('app created OK')"`
Expected: prints `app created OK` with no exceptions.

- [ ] **Step 5: Run the full backend suite and lint**

Run: `cd backend && pytest && ruff check .`
Expected: both clean/passing.

- [ ] **Step 6: Commit**

```bash
git add backend/app/main.py backend/tests/test_historical_return_refresh.py
git commit -m "feat: bootstrap historical returns on first startup"
```

---

### Task 6: Remove the manual field (backend)

**Files:**
- Create: `backend/alembic/versions/20260716_0011_drop_profile_expected_annual_return.py`
- Modify: `backend/app/data/models.py`
- Modify: `backend/app/schemas/profile.py`
- Modify: `backend/app/data/repositories/profiles.py`
- Modify: `backend/tests/test_m3_schema.py`
- Modify: `backend/tests/test_profile_goals.py`
- Modify: `backend/tests/test_projection_api.py`

**Interfaces:**
- Consumes: nothing — independent of Tasks 1-5 other than following them so `build_projection_for_user` no longer reads `profile.expected_annual_return` before the column disappears (already done in Task 3).
- Produces: nothing for later tasks — Task 7 (frontend) doesn't depend on backend timing, but is sequenced after this for a clean end state.

- [ ] **Step 1: Update the migration upgrade/downgrade test**

In `backend/tests/test_m3_schema.py`, find:

```python
def test_projection_profile_fields_upgrade_and_downgrade(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'projection_fields_schema.db'}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    get_settings.cache_clear()
    config = alembic_config(database_url)

    command.upgrade(config, "head")

    engine = create_engine(database_url)
    columns = {column["name"] for column in inspect(engine).get_columns("profiles")}
    assert {
        "goal_target_amount",
        "contribution_amount",
        "expected_annual_return",
    }.issubset(columns)

    command.downgrade(config, "20260707_0008")

    downgraded_columns = {
        column["name"] for column in inspect(engine).get_columns("profiles")
    }
    assert "goal_target_amount" not in downgraded_columns
    assert "contribution_amount" not in downgraded_columns
    assert "expected_annual_return" not in downgraded_columns
    get_settings.cache_clear()
```

Replace with (upgrading to `head` no longer has `expected_annual_return` at all, since it's dropped by a later migration):

```python
def test_projection_profile_fields_upgrade_and_downgrade(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'projection_fields_schema.db'}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    get_settings.cache_clear()
    config = alembic_config(database_url)

    command.upgrade(config, "head")

    engine = create_engine(database_url)
    columns = {column["name"] for column in inspect(engine).get_columns("profiles")}
    assert {"goal_target_amount", "contribution_amount"}.issubset(columns)
    assert "expected_annual_return" not in columns

    command.downgrade(config, "20260707_0008")

    downgraded_columns = {
        column["name"] for column in inspect(engine).get_columns("profiles")
    }
    assert "goal_target_amount" not in downgraded_columns
    assert "contribution_amount" not in downgraded_columns
    assert "expected_annual_return" not in downgraded_columns
    get_settings.cache_clear()
```

Then add a new test right after it, verifying the drop migration specifically:

```python
def test_profile_expected_annual_return_dropped_at_head(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_url = (
        f"sqlite+pysqlite:///{tmp_path / 'expected_annual_return_removed_schema.db'}"
    )
    monkeypatch.setenv("DATABASE_URL", database_url)
    get_settings.cache_clear()
    config = alembic_config(database_url)

    command.upgrade(config, "head")

    engine = create_engine(database_url)
    columns = {column["name"] for column in inspect(engine).get_columns("profiles")}
    assert "expected_annual_return" not in columns

    command.downgrade(config, "20260716_0010")

    downgraded_columns = {
        column["name"] for column in inspect(engine).get_columns("profiles")
    }
    assert "expected_annual_return" in downgraded_columns
    get_settings.cache_clear()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && pytest tests/test_m3_schema.py -v`
Expected: FAIL — `head` still has `expected_annual_return` on `profiles`.

- [ ] **Step 3: Add the migration**

Create `backend/alembic/versions/20260716_0011_drop_profile_expected_annual_return.py`:

```python
"""drop profile expected annual return

Revision ID: 20260716_0011
Revises: 20260716_0010
Create Date: 2026-07-16

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260716_0011"
down_revision: str | None = "20260716_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_column("profiles", "expected_annual_return")


def downgrade() -> None:
    op.add_column(
        "profiles",
        sa.Column("expected_annual_return", sa.Numeric(20, 8), nullable=True),
    )
```

- [ ] **Step 4: Remove the field from the `Profile` model**

In `backend/app/data/models.py`, find:

```python
    contribution_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(20, 8),
        nullable=True,
    )
    expected_annual_return: Mapped[Decimal | None] = mapped_column(
        Numeric(20, 8),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
```

Replace with:

```python
    contribution_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(20, 8),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
```

- [ ] **Step 5: Remove the field from `ProfileRequest`/`ProfileResponse`**

In `backend/app/schemas/profile.py`, find:

```python
    goal_target_amount: Decimal | None = None
    contribution_amount: Decimal | None = None
    expected_annual_return: Decimal | None = None

    @field_validator("display_name", "time_horizon", "investment_frequency")
```

Replace with:

```python
    goal_target_amount: Decimal | None = None
    contribution_amount: Decimal | None = None

    @field_validator("display_name", "time_horizon", "investment_frequency")
```

Find:

```python
    goal_target_amount: Decimal | None = None
    contribution_amount: Decimal | None = None
    expected_annual_return: Decimal | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_serializer(
        "goal_target_amount",
        "contribution_amount",
        "expected_annual_return",
    )
    def serialize_decimal(self, value: Decimal | None) -> str | None:
        if value is None:
            return None
        return str(value)
```

Replace with:

```python
    goal_target_amount: Decimal | None = None
    contribution_amount: Decimal | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_serializer("goal_target_amount", "contribution_amount")
    def serialize_decimal(self, value: Decimal | None) -> str | None:
        if value is None:
            return None
        return str(value)
```

- [ ] **Step 6: Remove the field from `upsert_profile`**

In `backend/app/data/repositories/profiles.py`, find:

```python
            goal_target_amount=payload.goal_target_amount,
            contribution_amount=payload.contribution_amount,
            expected_annual_return=payload.expected_annual_return,
        )
        db.add(profile)
```

Replace with:

```python
            goal_target_amount=payload.goal_target_amount,
            contribution_amount=payload.contribution_amount,
        )
        db.add(profile)
```

Find:

```python
        if "goal_target_amount" in payload.model_fields_set:
            profile.goal_target_amount = payload.goal_target_amount
        if "contribution_amount" in payload.model_fields_set:
            profile.contribution_amount = payload.contribution_amount
        if "expected_annual_return" in payload.model_fields_set:
            profile.expected_annual_return = payload.expected_annual_return

    db.commit()
```

Replace with:

```python
        if "goal_target_amount" in payload.model_fields_set:
            profile.goal_target_amount = payload.goal_target_amount
        if "contribution_amount" in payload.model_fields_set:
            profile.contribution_amount = payload.contribution_amount

    db.commit()
```

- [ ] **Step 7: Update `test_profile_goals.py`**

In `backend/tests/test_profile_goals.py`, find:

```python
def test_creating_profile_with_projection_fields_persists_them(
    authenticated_user: AuthenticatedUser,
    db_session: Session,
) -> None:
    response = save_profile(
        profile_payload(
            goal_target_amount="100000",
            contribution_amount="500",
            expected_annual_return="7.5",
        ),
        authenticated_user,
        db_session,
    )

    assert response.goal_target_amount == Decimal("100000")
    assert response.contribution_amount == Decimal("500")
    assert response.expected_annual_return == Decimal("7.5")

    reloaded = read_profile(authenticated_user, db_session)
    assert reloaded.goal_target_amount == Decimal("100000")
    assert reloaded.contribution_amount == Decimal("500")
    assert reloaded.expected_annual_return == Decimal("7.5")


def test_creating_profile_without_projection_fields_leaves_them_none(
    authenticated_user: AuthenticatedUser,
    db_session: Session,
) -> None:
    response = save_profile(
        profile_payload(),
        authenticated_user,
        db_session,
    )

    assert response.goal_target_amount is None
    assert response.contribution_amount is None
    assert response.expected_annual_return is None


def test_updating_profile_without_projection_fields_preserves_existing_values(
    authenticated_user: AuthenticatedUser,
    db_session: Session,
) -> None:
    first_response = save_profile(
        profile_payload(
            goal_target_amount="100000",
            contribution_amount="500",
            expected_annual_return="7.5",
        ),
        authenticated_user,
        db_session,
    )

    second_response = save_profile(
        profile_payload(display_name="Ron"),
        authenticated_user,
        db_session,
    )

    assert second_response.id == first_response.id
    assert second_response.display_name == "Ron"
    assert second_response.goal_target_amount == Decimal("100000")
    assert second_response.contribution_amount == Decimal("500")
    assert second_response.expected_annual_return == Decimal("7.5")

    saved_profile = db_session.scalar(select(Profile))
    assert saved_profile is not None
    assert saved_profile.goal_target_amount == Decimal("100000")
    assert saved_profile.contribution_amount == Decimal("500")
    assert saved_profile.expected_annual_return == Decimal("7.5")


def test_updating_profile_with_new_projection_fields_updates_them(
    authenticated_user: AuthenticatedUser,
    db_session: Session,
) -> None:
    save_profile(
        profile_payload(
            goal_target_amount="100000",
            contribution_amount="500",
            expected_annual_return="7.5",
        ),
        authenticated_user,
        db_session,
    )

    second_response = save_profile(
        profile_payload(
            goal_target_amount="200000",
            contribution_amount="750",
            expected_annual_return="6.0",
        ),
        authenticated_user,
        db_session,
    )

    assert second_response.goal_target_amount == Decimal("200000")
    assert second_response.contribution_amount == Decimal("750")
    assert second_response.expected_annual_return == Decimal("6.0")


def test_negative_goal_target_amount_is_rejected() -> None:
    with pytest.raises(ValidationError):
        profile_payload(goal_target_amount="-1")


def test_negative_contribution_amount_is_rejected() -> None:
    with pytest.raises(ValidationError):
        profile_payload(contribution_amount="-1")


def test_negative_expected_annual_return_is_accepted() -> None:
    payload = profile_payload(expected_annual_return="-2.5")

    assert payload.expected_annual_return == Decimal("-2.5")
```

Replace with (drops `expected_annual_return` from every payload/assertion, and removes the now-meaningless `test_negative_expected_annual_return_is_accepted`):

```python
def test_creating_profile_with_projection_fields_persists_them(
    authenticated_user: AuthenticatedUser,
    db_session: Session,
) -> None:
    response = save_profile(
        profile_payload(
            goal_target_amount="100000",
            contribution_amount="500",
        ),
        authenticated_user,
        db_session,
    )

    assert response.goal_target_amount == Decimal("100000")
    assert response.contribution_amount == Decimal("500")

    reloaded = read_profile(authenticated_user, db_session)
    assert reloaded.goal_target_amount == Decimal("100000")
    assert reloaded.contribution_amount == Decimal("500")


def test_creating_profile_without_projection_fields_leaves_them_none(
    authenticated_user: AuthenticatedUser,
    db_session: Session,
) -> None:
    response = save_profile(
        profile_payload(),
        authenticated_user,
        db_session,
    )

    assert response.goal_target_amount is None
    assert response.contribution_amount is None


def test_updating_profile_without_projection_fields_preserves_existing_values(
    authenticated_user: AuthenticatedUser,
    db_session: Session,
) -> None:
    first_response = save_profile(
        profile_payload(
            goal_target_amount="100000",
            contribution_amount="500",
        ),
        authenticated_user,
        db_session,
    )

    second_response = save_profile(
        profile_payload(display_name="Ron"),
        authenticated_user,
        db_session,
    )

    assert second_response.id == first_response.id
    assert second_response.display_name == "Ron"
    assert second_response.goal_target_amount == Decimal("100000")
    assert second_response.contribution_amount == Decimal("500")

    saved_profile = db_session.scalar(select(Profile))
    assert saved_profile is not None
    assert saved_profile.goal_target_amount == Decimal("100000")
    assert saved_profile.contribution_amount == Decimal("500")


def test_updating_profile_with_new_projection_fields_updates_them(
    authenticated_user: AuthenticatedUser,
    db_session: Session,
) -> None:
    save_profile(
        profile_payload(
            goal_target_amount="100000",
            contribution_amount="500",
        ),
        authenticated_user,
        db_session,
    )

    second_response = save_profile(
        profile_payload(
            goal_target_amount="200000",
            contribution_amount="750",
        ),
        authenticated_user,
        db_session,
    )

    assert second_response.goal_target_amount == Decimal("200000")
    assert second_response.contribution_amount == Decimal("750")


def test_negative_goal_target_amount_is_rejected() -> None:
    with pytest.raises(ValidationError):
        profile_payload(goal_target_amount="-1")


def test_negative_contribution_amount_is_rejected() -> None:
    with pytest.raises(ValidationError):
        profile_payload(contribution_amount="-1")
```

- [ ] **Step 8: Remove the remaining `expected_annual_return=None` kwargs in `test_projection_api.py`**

In `backend/tests/test_projection_api.py`, find:

```python
def add_profile(
    db_session: Session,
    user_id: str = "user-123",
    *,
    time_horizon: str = "10+ years",
    investment_frequency: str = "monthly",
    risk_tolerance: str | None = None,
    goal_target_amount: str | None = None,
    contribution_amount: str | None = None,
    expected_annual_return: str | None = None,
) -> Profile:
    profile = Profile(
        user_id=user_id,
        display_name="Ronen",
        base_currency="USD",
        time_horizon=time_horizon,
        investment_frequency=investment_frequency,
        risk_tolerance=risk_tolerance,
        goal_target_amount=(
            Decimal(goal_target_amount) if goal_target_amount is not None else None
        ),
        contribution_amount=(
            Decimal(contribution_amount) if contribution_amount is not None else None
        ),
        expected_annual_return=(
            Decimal(expected_annual_return)
            if expected_annual_return is not None
            else None
        ),
    )
    db_session.add(profile)
    db_session.commit()
    return profile
```

Replace with:

```python
def add_profile(
    db_session: Session,
    user_id: str = "user-123",
    *,
    time_horizon: str = "10+ years",
    investment_frequency: str = "monthly",
    risk_tolerance: str | None = None,
    goal_target_amount: str | None = None,
    contribution_amount: str | None = None,
) -> Profile:
    profile = Profile(
        user_id=user_id,
        display_name="Ronen",
        base_currency="USD",
        time_horizon=time_horizon,
        investment_frequency=investment_frequency,
        risk_tolerance=risk_tolerance,
        goal_target_amount=(
            Decimal(goal_target_amount) if goal_target_amount is not None else None
        ),
        contribution_amount=(
            Decimal(contribution_amount) if contribution_amount is not None else None
        ),
    )
    db_session.add(profile)
    db_session.commit()
    return profile
```

Find:

```python
    add_profile(
        db_session,
        authenticated_user.user_id,
        risk_tolerance="aggressive",
        expected_annual_return=None,
    )
```

Replace with:

```python
    add_profile(
        db_session,
        authenticated_user.user_id,
        risk_tolerance="aggressive",
    )
```

Find:

```python
    add_profile(
        db_session,
        authenticated_user.user_id,
        risk_tolerance=None,
        expected_annual_return=None,
    )
```

Replace with:

```python
    add_profile(
        db_session,
        authenticated_user.user_id,
        risk_tolerance=None,
    )
```

Find:

```python
    add_profile(
        db_session,
        authenticated_user.user_id,
        time_horizon="10+ years",
        goal_target_amount="50000",
        contribution_amount="200",
        expected_annual_return="7",
    )

    response = read_portfolio_projection(
        authenticated_user,
        db_session,
        target=Decimal("90000"),
        contribution=Decimal("500"),
        annual_return=Decimal("10"),
        years=20,
    )
```

Replace with:

```python
    add_profile(
        db_session,
        authenticated_user.user_id,
        time_horizon="10+ years",
        goal_target_amount="50000",
        contribution_amount="200",
    )

    response = read_portfolio_projection(
        authenticated_user,
        db_session,
        target=Decimal("90000"),
        contribution=Decimal("500"),
        annual_return=Decimal("10"),
        years=20,
    )
```

- [ ] **Step 9: Run the full backend suite and lint**

Run: `cd backend && pytest && ruff check .`
Expected: both clean/passing.

- [ ] **Step 10: Commit**

```bash
git add backend/alembic/versions/20260716_0011_drop_profile_expected_annual_return.py backend/app/data/models.py backend/app/schemas/profile.py backend/app/data/repositories/profiles.py backend/tests/test_m3_schema.py backend/tests/test_profile_goals.py backend/tests/test_projection_api.py
git commit -m "feat: remove the manual expected_annual_return profile field"
```

---

### Task 7: Remove the manual field (frontend)

**Files:**
- Modify: `frontend/src/features/profile/profile-api.ts`
- Modify: `frontend/src/features/profile/ProfileEditPage.tsx`
- Modify: `frontend/src/features/profile/ProfileWizardPage.tsx`
- Modify: `frontend/src/features/profile/profile.test.tsx`

**Interfaces:**
- Consumes: nothing — the backend no longer accepts or returns this field as of Task 6.
- Produces: nothing — this is the final task.

- [ ] **Step 1: Update the failing/obsolete tests first**

In `frontend/src/features/profile/profile.test.tsx`, find:

```tsx
  goals_note: null,
  goal_target_amount: null,
  contribution_amount: null,
  expected_annual_return: null,
  created_at: "2026-06-04T00:00:00Z",
```

Replace with:

```tsx
  goals_note: null,
  goal_target_amount: null,
  contribution_amount: null,
  created_at: "2026-06-04T00:00:00Z",
```

Find:

```tsx
        goal_target_amount: null,
        contribution_amount: null,
        expected_annual_return: null,
      });
    });
  });

  it("renders optional interests and goals controls", async () => {
```

Replace with:

```tsx
        goal_target_amount: null,
        contribution_amount: null,
      });
    });
  });

  it("renders optional interests and goals controls", async () => {
```

Find:

```tsx
        goal_target_amount: null,
        contribution_amount: null,
        expected_annual_return: null,
      });
    });
  });

  it("routes to dashboard after a successful save", async () => {
```

Replace with:

```tsx
        goal_target_amount: null,
        contribution_amount: null,
      });
    });
  });

  it("routes to dashboard after a successful save", async () => {
```

Find:

```tsx
  it("persists goal projection fields as strings when filled in", async () => {
    vi.mocked(getProfile).mockRejectedValue(new ApiError(404, "Profile not found"));
    vi.mocked(saveProfile).mockResolvedValue(savedProfile);
    renderRoute("/profile/setup");

    await fillProfileForm();
    await userEvent.type(screen.getByLabelText("Goal target amount"), "50000");
    await userEvent.type(screen.getByLabelText("Contribution amount"), "500");
    await userEvent.type(screen.getByLabelText("Expected annual return (%)"), "6");
    await userEvent.click(screen.getByRole("button", { name: "Save profile" }));

    await waitFor(() => {
      expect(saveProfile).toHaveBeenCalledWith("access-token", {
        display_name: "Ronen",
        base_currency: "USD",
        time_horizon: "10+ years",
        investment_frequency: "monthly",
        risk_tolerance: null,
        interest_tags: [],
        excluded_sectors: [],
        goals_note: null,
        goal_target_amount: "50000",
        contribution_amount: "500",
        expected_annual_return: "6",
      });
    });
  });

  it("shows a validation error for a negative goal target amount", async () => {
```

Replace with:

```tsx
  it("persists goal projection fields as strings when filled in", async () => {
    vi.mocked(getProfile).mockRejectedValue(new ApiError(404, "Profile not found"));
    vi.mocked(saveProfile).mockResolvedValue(savedProfile);
    renderRoute("/profile/setup");

    await fillProfileForm();
    await userEvent.type(screen.getByLabelText("Goal target amount"), "50000");
    await userEvent.type(screen.getByLabelText("Contribution amount"), "500");
    await userEvent.click(screen.getByRole("button", { name: "Save profile" }));

    await waitFor(() => {
      expect(saveProfile).toHaveBeenCalledWith("access-token", {
        display_name: "Ronen",
        base_currency: "USD",
        time_horizon: "10+ years",
        investment_frequency: "monthly",
        risk_tolerance: null,
        interest_tags: [],
        excluded_sectors: [],
        goals_note: null,
        goal_target_amount: "50000",
        contribution_amount: "500",
      });
    });
  });

  it("shows a validation error for a negative goal target amount", async () => {
```

Find:

```tsx
  it("shows a validation error for a non-numeric expected annual return", async () => {
    vi.mocked(getProfile).mockRejectedValue(new ApiError(404, "Profile not found"));
    renderRoute("/profile/setup");

    await fillProfileForm();
    await userEvent.type(screen.getByLabelText("Expected annual return (%)"), "abc");
    await userEvent.click(screen.getByRole("button", { name: "Save profile" }));

    expect(saveProfile).not.toHaveBeenCalled();
    expect(screen.getByText("Must be a number")).toBeInTheDocument();
  });
});
```

Replace with:

```tsx
});
```

Find:

```tsx
  it("formats stored decimal values without the database's trailing zeros", async () => {
    vi.mocked(getProfile).mockResolvedValue({
      ...savedProfile,
      goal_target_amount: "1000000.00000000",
      contribution_amount: "362.30000000",
      expected_annual_return: "6.00000000",
    });
    renderRoute("/profile");

    expect(await screen.findByLabelText("Goal target amount")).toHaveValue(
      "1000000"
    );
    expect(screen.getByLabelText("Contribution amount")).toHaveValue("362.3");
    expect(screen.getByLabelText("Expected annual return (%)")).toHaveValue(
      "6"
    );
  });
});
```

Replace with:

```tsx
  it("formats stored decimal values without the database's trailing zeros", async () => {
    vi.mocked(getProfile).mockResolvedValue({
      ...savedProfile,
      goal_target_amount: "1000000.00000000",
      contribution_amount: "362.30000000",
    });
    renderRoute("/profile");

    expect(await screen.findByLabelText("Goal target amount")).toHaveValue(
      "1000000"
    );
    expect(screen.getByLabelText("Contribution amount")).toHaveValue("362.3");
  });
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd frontend && npm test -- profile -v`
Expected: FAIL — `saveProfile` is still called with an `expected_annual_return` key the assertions no longer expect, and `getByLabelText("Expected annual return (%)")` still exists.

- [ ] **Step 3: Remove the field from the shared type**

In `frontend/src/features/profile/profile-api.ts`, find:

```ts
  goal_target_amount: string | null;
  contribution_amount: string | null;
  expected_annual_return: string | null;
};
```

Replace with:

```ts
  goal_target_amount: string | null;
  contribution_amount: string | null;
};
```

- [ ] **Step 4: Remove the field from `ProfileEditPage.tsx`**

Find:

```tsx
  if (payload.expected_annual_return !== null) {
    const numericValue = Number(payload.expected_annual_return);
    if (!Number.isFinite(numericValue)) {
      errors.expected_annual_return = "Must be a number";
    }
  }

  return errors;
}
```

Replace with:

```tsx
  return errors;
}
```

Find:

```tsx
      goal_target_amount: form.goal_target_amount?.trim() || null,
      contribution_amount: form.contribution_amount?.trim() || null,
      expected_annual_return: form.expected_annual_return?.trim() || null,
    };
```

Replace with:

```tsx
      goal_target_amount: form.goal_target_amount?.trim() || null,
      contribution_amount: form.contribution_amount?.trim() || null,
    };
```

Find:

```tsx
    goal_target_amount: formatDecimalForInput(initial.goal_target_amount),
    contribution_amount: formatDecimalForInput(initial.contribution_amount),
    expected_annual_return: formatDecimalForInput(initial.expected_annual_return),
  };
```

Replace with:

```tsx
    goal_target_amount: formatDecimalForInput(initial.goal_target_amount),
    contribution_amount: formatDecimalForInput(initial.contribution_amount),
  };
```

Find:

```tsx
              {errors.contribution_amount ? (
                <span className="field-error">{errors.contribution_amount}</span>
              ) : null}
            </div>

            <div className="field">
              <label htmlFor="expected-annual-return">
                Expected annual return (%)
              </label>
              <input
                id="expected-annual-return"
                inputMode="decimal"
                value={form.expected_annual_return ?? ""}
                onChange={(event) =>
                  updateField("expected_annual_return", event.target.value)
                }
              />
              {errors.expected_annual_return ? (
                <span className="field-error">{errors.expected_annual_return}</span>
              ) : null}
            </div>
          </div>
        </section>
      </div>
```

Replace with:

```tsx
              {errors.contribution_amount ? (
                <span className="field-error">{errors.contribution_amount}</span>
              ) : null}
            </div>
          </div>
        </section>
      </div>
```

- [ ] **Step 5: Remove the field from `ProfileWizardPage.tsx`**

Find:

```tsx
  if (payload.expected_annual_return !== null) {
    const numericValue = Number(payload.expected_annual_return);
    if (!Number.isFinite(numericValue)) {
      errors.expected_annual_return = "Must be a number";
    }
  }

  return errors;
}
```

Replace with:

```tsx
  return errors;
}
```

Find:

```tsx
    goal_target_amount: "",
    contribution_amount: "",
    expected_annual_return: "",
  });
```

Replace with:

```tsx
    goal_target_amount: "",
    contribution_amount: "",
  });
```

Find:

```tsx
      goal_target_amount: form.goal_target_amount?.trim() || null,
      contribution_amount: form.contribution_amount?.trim() || null,
      expected_annual_return: form.expected_annual_return?.trim() || null,
    };
```

Replace with:

```tsx
      goal_target_amount: form.goal_target_amount?.trim() || null,
      contribution_amount: form.contribution_amount?.trim() || null,
    };
```

Find:

```tsx
                {errors.contribution_amount ? (
                  <span className="field-error">{errors.contribution_amount}</span>
                ) : null}
              </div>

              <div className="field">
                <label htmlFor="expected-annual-return">
                  Expected annual return (%)
                </label>
                <input
                  id="expected-annual-return"
                  inputMode="decimal"
                  value={form.expected_annual_return ?? ""}
                  onChange={(event) =>
                    updateField("expected_annual_return", event.target.value)
                  }
                />
                {errors.expected_annual_return ? (
                  <span className="field-error">{errors.expected_annual_return}</span>
                ) : null}
              </div>
            </div>
          </section>
        </div>
```

Replace with:

```tsx
                {errors.contribution_amount ? (
                  <span className="field-error">{errors.contribution_amount}</span>
                ) : null}
              </div>
            </div>
          </section>
        </div>
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `cd frontend && npm test -- profile -v`
Expected: PASS (all tests in the file).

- [ ] **Step 7: Run the full frontend suite, lint, and type-check**

Run: `cd frontend && npm test && npm run lint && npm run build`
Expected: all clean/passing.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/features/profile/profile-api.ts frontend/src/features/profile/ProfileEditPage.tsx frontend/src/features/profile/ProfileWizardPage.tsx frontend/src/features/profile/profile.test.tsx
git commit -m "feat: remove the manual expected annual return field from both profile forms"
```
