# Auto-Computed Expected Annual Return Design Spec

**M5 Step 7b.** Replace the manually-entered `expected_annual_return`
profile field with a value computed from the user's current portfolio
composition, so the goal projection starts from a real, portfolio-derived
number instead of a guess.

## Background: why not a true asset-class breakdown

`asset_class` is not a clean equity/bond/cash/commodity taxonomy today — it's
a free-text label sourced from external data providers (`"STOCK"`, `"ETF"`,
`"FUND"`, `"ADR"`, inconsistently cased), and nothing in the codebase knows
what's actually *inside* an ETF or fund (it could hold equities, bonds, or
commodities). A fully accurate weighted return would require fetching each
ETF/fund's true underlying composition from a data provider — a
significantly larger, separate effort. This spec instead maps the coarse
labels we already have to assumed long-run returns, accepting that
ETF/fund/ADR holdings are treated as equity-like by default. Descoping to
"fetch real composition data first" was considered and explicitly rejected
in favor of shipping the approximation now.

## Architecture

A new pure function computes a weighted-average expected return from a
portfolio snapshot's holdings — each priced, base-currency holding's
`market_value` weighted against an assumed-return table keyed by its
`asset_class` label. `build_projection_for_user` calls it in place of
reading `profile.expected_annual_return` (removed entirely — schema, DB
column, and both profile forms). The existing risk-tolerance default and the
`annual_return` what-if query override (used by the projection panel's
slider) are unchanged.

## A. Computation (`backend/app/domain/portfolio_math.py`)

New module-level constants, alongside the existing snapshot-building code in
this file:

```python
ASSET_CLASS_DEFAULT_RETURN: dict[str, Decimal] = {
    "CRYPTO": Decimal("12"),
    "COMMODITY": Decimal("5"),
    "CASH": Decimal("2"),
    "MONEY MARKET": Decimal("2"),
}

# STOCK/ETF/FUND/ADR and any unrecognized asset_class label default here.
EQUITY_LIKE_RETURN = Decimal("8")
```

New function:

```python
def compute_weighted_average_return(
    holdings: list[PortfolioHoldingSnapshot], base_currency: str
) -> Decimal | None:
```

- Filters `holdings` to those where `market_value is not None` and
  `holding.instrument.currency == base_currency` — the same subset
  `build_portfolio_snapshot` already uses to accumulate `total_market_value`,
  so the weights are consistent with the denominator they're derived from. A
  holding priced in a different currency is excluded here exactly as it's
  already excluded from `total_market_value` today — not a new
  inconsistency.
- For each included holding, normalizes `instrument.asset_class` via
  `.strip().upper()` (existing values are inconsistently cased — e.g.
  `"Stock"`, `"STOCK"`, `" ETF "` — and must resolve identically) and looks
  it up in `ASSET_CLASS_DEFAULT_RETURN`, falling back to `EQUITY_LIKE_RETURN`
  for `None`, empty, or unrecognized labels.
- Returns the market-value-weighted average of those per-holding rates,
  quantized to the same precision convention as the rest of the projection
  math (`Decimal.quantize` to 2 places, `ROUND_HALF_UP`).
- Returns `None` when there are no qualifying holdings (empty portfolio, or
  all holdings unpriced/non-base-currency) — signals "nothing to compute
  from," triggering the existing risk-tolerance fallback.

## B. Wiring into the projection (`backend/app/domain/portfolio_service.py`)

`build_projection_for_user`'s existing resolution:

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

becomes:

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

The `annual_return` what-if override (the projection panel's slider) is
untouched — it still wins over everything, exactly as today.

## C. Removing the manual field

**Backend:**
- Migration drops `expected_annual_return` from the `profiles` table.
- `expected_annual_return` removed from `ProfileRequest`/`ProfileResponse`
  (`backend/app/schemas/profile.py`) and the `Profile` model
  (`backend/app/data/models.py`).

**Frontend:**
- "Expected annual return (%)" removed from both `ProfileEditPage.tsx` and
  `ProfileWizardPage.tsx` — input, label, `validateProfile` check, and the
  submitted payload.
- `expected_annual_return` dropped from `ProfilePayload`/`Profile` types in
  `profile-api.ts`.
- `ProjectionPanel`'s existing "Expected annual return" slider is untouched
  — it already just reflects `data.annual_return_expected` from the
  projection response and lets the user drag it for what-if exploration; the
  only change is that the *starting* value it displays now comes from the
  auto-computation instead of a stored manual value.

## D. Testing

**Backend:**
- `compute_weighted_average_return`: weighted average across a mix of asset
  classes (e.g. STOCK + CRYPTO + COMMODITY) matches a hand-computed expected
  value; case/whitespace-insensitive matching (`"Stock"`, `"STOCK"`,
  `" ETF "` all resolve identically); unrecognized/`None` asset_class falls
  back to `EQUITY_LIKE_RETURN`; holdings with `market_value is None` or a
  non-base-currency `instrument.currency` are excluded from both numerator
  and denominator; an empty/all-excluded holdings list returns `None`.
- `test_projection_api.py`: the profile-driven precedence chain (no
  override → auto-computed → falls back to risk-tolerance default when no
  qualifying holdings exist) resolves correctly end-to-end. Existing tests
  that pass `expected_annual_return` in the request payload are updated to
  drop that field.

**Frontend:** existing profile-form tests referencing "Expected annual
return (%)" as an input are removed/updated (`profile.test.tsx`), since the
field no longer exists in the form. `ProjectionPanel`'s tests are unaffected
— they never referenced the profile's manual field directly, only the
projection response.

## Out of scope

- Fetching true underlying ETF/fund composition (equity/bond/cash split)
  from a data provider — a separate, larger effort (see Background).
- Any change to `RISK_TOLERANCE_DEFAULT_RETURN` or its role as the fallback
  for portfolios with no qualifying holdings.
- Any change to `ProjectionPanel`'s slider UI or behavior.
