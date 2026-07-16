# Auto-Computed Expected Annual Return Design Spec

**M5 Step 7b.** Replace the manually-entered `expected_annual_return`
profile field with a value computed from the user's current portfolio
composition, so the goal projection starts from a real, portfolio-derived
number instead of a guess.

## Background: grounding this in real data

An earlier draft of this spec proposed a purely asset-class-bucket
assumed-return table (STOCK/ETF/FUND/ADR → 8%, CRYPTO → 12%, etc.) with no
real data behind the numbers. That was revisited: `YFinanceMarketDataClient`
(already a dependency, used today for latest-close prices) can fetch much
longer price history via `ticker.history(period=...)` — we don't need a new
data provider integration to get real historical performance per
instrument, just a longer lookback on an API we already call.

This spec is a **hybrid**: each instrument's own trailing 5-year annualized
return (computed from real yfinance history, when at least 3 years of it is
available) is used first; the original asset-class bucket table becomes the
fallback for instruments where real history is missing or too thin (crypto,
newly-listed instruments, fetch failures) — not the primary source.

## Architecture

- A new `MarketDataClient` method fetches an instrument's trailing 5-year
  price history and computes its annualized return (CAGR), returning `None`
  if fewer than 3 years of history is available.
- This is precomputed by a new **monthly** scheduled job (not the existing
  daily price-refresh job — a 5-year annualized return barely moves day to
  day, so recomputing it daily would add avoidable yfinance load) and stored
  on the `Instrument` row, mirroring how `asset_class`/`sector`/etc. are
  already stored directly on the instrument rather than recomputed per
  request. A one-time startup-hook bootstrap covers the gap between
  shipping this and the first monthly cron tick (see Section C).
- `compute_weighted_average_return` (the portfolio-level weighting function)
  reads each holding's stored historical return first, falling back to the
  asset-class bucket table only when it's absent.
- `build_projection_for_user` calls this in place of reading
  `profile.expected_annual_return`, which is removed entirely (schema, DB
  column, both profile forms). The existing risk-tolerance default and the
  `annual_return` what-if query override (used by the projection panel's
  slider) are unchanged.

## A. Historical return computation (`backend/app/integrations/yfinance_client.py`)

New method on `YFinanceMarketDataClient`, and a matching addition to the
`MarketDataClient` `Protocol` (`app/integrations/market_data.py`):

```python
def get_historical_annualized_return(
    self,
    symbol: str,
    exchange: str,
    currency_hint: str | None,
) -> Decimal | None:
```

- Fetches `ticker.history(period="5y")`.
- Finds the earliest and latest valid (non-null, finite) closing prices in
  that range — reusing the existing `latest_non_null_close` helper for the
  latest one, and a new mirror-image `first_non_null_close` for the
  earliest.
- Computes the actual elapsed span between those two dates in years
  (`days / 365.25`). If that span is under 3 years, or there are fewer than
  two valid closes, or the earliest price isn't positive, returns `None` —
  "not enough real data to trust" is decided once, here, at the source.
- Otherwise computes `CAGR = (end_price / start_price) ** (1 / years) - 1`
  in `Decimal` (Python's `Decimal` supports fractional-exponent `**`
  natively via its context, so this stays in `Decimal` throughout, no float
  round-tripping), expressed as a quantized percentage (e.g. `Decimal("9.42")`
  for 9.42%/year).

## B. Storage (`backend/app/data/models.py` + migration)

Two new nullable columns on `Instrument`, next to the existing
`metadata_updated_at`:

```python
historical_annual_return: Mapped[Decimal | None] = mapped_column(
    Numeric(20, 8), nullable=True
)
historical_return_updated_at: Mapped[datetime | None] = mapped_column(
    DateTime(timezone=True), nullable=True
)
```

A migration adds both columns (nullable, no backfill — existing instruments
simply have `None` until the first monthly job run). `historical_annual_return`
is also added to `InstrumentResponse` (`backend/app/schemas/holdings.py`),
the same schema `PortfolioHoldingSnapshot.instrument` already uses, so it's
available wherever a holding snapshot is — including inside
`build_projection_for_user`.

## C. Monthly refresh job

Mirrors the existing `refresh_instrument_metadata_for_all_instruments`
pattern exactly (a scheduler-only job with no per-user variant — there's no
user-facing reason to trigger a slow 5-year history fetch on demand):

- New `backend/app/domain/historical_return_refresh.py`, with
  `refresh_historical_returns_for_all_instruments(db, market_data_client)`:
  iterates every instrument (`list_all_instruments`), calls
  `get_historical_annualized_return` for each, and either stores the result
  + a fresh `historical_return_updated_at` timestamp (success), leaves the
  instrument untouched (returned `None` — "skipped"), or counts it as
  "failed" (an exception was raised). Returns a result dataclass/schema
  shaped like the existing `PriceRefreshResult`/`MetadataRefreshResult`
  (`requested`/`updated`/`skipped`/`failed`).
- New endpoint `POST /api/v1/jobs/refresh-historical-returns`
  (`backend/app/api/v1/jobs.py`), gated by the same `X-Scheduler-Secret`
  header check as `refresh-etf-metadata` (scheduler-secret-only, no
  authenticated-user path).
- New `.github/workflows/refresh-historical-returns.yml`, structurally
  identical to the existing `refresh-prices.yml` (same
  `PORTFOLIUS_API_URL`/`PORTFOLIUS_SCHEDULER_SECRET` secrets, same curl
  call against the new endpoint), but on a monthly `cron` schedule instead
  of a weekday/market-hours one.

**Bootstrap on first deploy:** the monthly cron alone would leave every
instrument's `historical_annual_return` at `None` (falling back to the
asset-class bucket) for up to a month after this ships. To avoid that gap,
a FastAPI startup hook in `backend/app/main.py` checks once, on process
start, whether the job has ever run at all — i.e. whether every instrument
row still has `historical_return_updated_at IS NULL` (a single cheap
`SELECT EXISTS`-style query, not a full table scan of computed values). If
so, it kicks off `refresh_historical_returns_for_all_instruments` as a
non-blocking background task (`asyncio.create_task`, not awaited during
startup) so it doesn't delay the app becoming ready/passing health checks.
Once that first run completes, every processed instrument has a non-null
timestamp, so the check is a no-op on every subsequent restart — this is a
one-time bootstrap, not a replacement for the monthly cadence. This is a new
pattern for the app (no existing startup/lifespan hook exists yet in
`main.py`); confirmed safe because the backend runs as a single instance
(no risk of two concurrent instances both racing to bootstrap at once).

## D. Weighted-average computation (`backend/app/domain/portfolio_math.py`)

Same constants as the original draft, now serving purely as the fallback
tier:

```python
ASSET_CLASS_DEFAULT_RETURN: dict[str, Decimal] = {
    "CRYPTO": Decimal("12"),
    "COMMODITY": Decimal("5"),
    "CASH": Decimal("2"),
    "MONEY MARKET": Decimal("2"),
}
EQUITY_LIKE_RETURN = Decimal("8")  # STOCK/ETF/FUND/ADR and any unrecognized label
```

```python
def compute_weighted_average_return(
    holdings: list[PortfolioHoldingSnapshot], base_currency: str
) -> Decimal | None:
```

- Filters `holdings` to those where `market_value is not None` and
  `instrument.currency == base_currency` — the same subset already used to
  accumulate `total_market_value`, so the weights are consistent with the
  denominator they're derived from.
- Returns `None` if nothing qualifies (nothing to compute from — empty
  portfolio, or everything unpriced/non-base-currency).
- For each qualifying holding, the rate is `instrument.historical_annual_return`
  if it's set; otherwise the asset-class bucket lookup (`asset_class`
  normalized via `.strip().upper()`, defaulting to `EQUITY_LIKE_RETURN` for
  `None`/unrecognized labels) — exactly the original draft's bucket logic,
  demoted to a fallback.
- Returns the market-value-weighted average of those per-holding rates,
  quantized to 2 places.

## E. Wiring into the projection (`backend/app/domain/portfolio_service.py`)

Unchanged from the original draft — `build_projection_for_user`'s
resolution becomes:

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

The `annual_return` what-if override (the projection panel's slider) still
wins over everything, exactly as today.

## F. Removing the manual field

Unchanged from the original draft:

**Backend:** migration drops `expected_annual_return` from the `profiles`
table; removed from `ProfileRequest`/`ProfileResponse`
(`backend/app/schemas/profile.py`) and the `Profile` model.

**Frontend:** "Expected annual return (%)" removed from both
`ProfileEditPage.tsx` and `ProfileWizardPage.tsx` (input, label,
`validateProfile` check, submitted payload), and dropped from
`ProfilePayload`/`Profile` types in `profile-api.ts`. `ProjectionPanel`'s
existing "Expected annual return" slider is untouched — it already just
reflects `data.annual_return_expected` from the projection response; only
the starting value's source changes.

## G. Testing

**`yfinance_client.py`:** `get_historical_annualized_return` — full 5-year
history produces a CAGR matching a hand-computed value; fewer than 3 years
of span returns `None`; empty/no-data history returns `None`; a
non-positive earliest price returns `None` defensively.

**`historical_return_refresh.py`:** refreshing updates
`historical_annual_return` + `historical_return_updated_at` on a successful
fetch; leaves both untouched when the client returns `None`; counts an
exception as "failed" without stopping the rest of the batch (matching the
existing `refresh_instrument_metadata_for_all_instruments` resilience
pattern); the result counts (`requested`/`updated`/`skipped`/`failed`) add
up correctly.

**`app/api/v1/jobs.py`:** the new endpoint rejects requests without a valid
`X-Scheduler-Secret` and calls through to the refresh function on success —
mirroring the existing `refresh-etf-metadata` endpoint test.

**Startup-hook bootstrap (`main.py`):** the "has this ever run" check
returns true when every instrument has `historical_return_updated_at IS
NULL` (including the empty-instruments-table case) and false as soon as any
one instrument has a non-null timestamp; the background task is only
scheduled in the true case.

**`portfolio_math.py`:** `compute_weighted_average_return` — a holding with
a stored `historical_annual_return` uses it directly (ignoring its
`asset_class`, even if one is set); a holding with `historical_annual_return
= None` falls back to the asset-class bucket; a portfolio mixing both kinds
of holdings weights each correctly by its own rate; case/whitespace
-insensitive bucket matching, non-base-currency/unpriced exclusion, and the
empty-portfolio `None` case all carry over from the original draft's test
list.

**`test_projection_api.py`:** the end-to-end precedence chain (no override
→ auto-computed → risk-tolerance fallback when nothing qualifies) resolves
correctly. Existing tests passing `expected_annual_return` in the request
payload are updated to drop that field.

**Frontend:** existing profile-form tests referencing "Expected annual
return (%)" as an input are removed/updated (`profile.test.tsx`).
`ProjectionPanel`'s tests are unaffected.

## Out of scope

- Any change to `RISK_TOLERANCE_DEFAULT_RETURN` or its role as the final
  fallback for portfolios with no qualifying holdings.
- Any change to `ProjectionPanel`'s slider UI or behavior.
- Backfilling `historical_annual_return` for existing instruments outside
  the normal monthly job cadence (it populates naturally on the first run
  after this ships).
- A user-facing "refresh my historical returns now" trigger — the monthly
  job is scheduler-only, matching the existing ETF-metadata refresh's
  precedent.
