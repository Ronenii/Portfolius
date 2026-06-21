# First Holding Price Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fetch and store a best-effort latest price when an instrument receives its first holding, and keep portfolio query caches consistent after holding mutations.

**Architecture:** Add a focused domain helper that checks the shared instrument price table before calling the existing market-data client and upserting a finite latest close. Inject that client into the holding-create endpoint after the holding transaction succeeds. On the frontend, centralize invalidation of holdings, snapshot, and breakdown query families after successful create, update, and delete operations.

**Tech Stack:** FastAPI dependency injection, SQLAlchemy, yfinance market-data adapter, pytest, React, TanStack Query, Vitest, TypeScript, Ruff, ESLint.

---

### Task 1: Fetch the First Stored Instrument Price

**Files:**
- Modify: `backend/app/domain/price_refresh.py`
- Modify: `backend/tests/test_price_refresh.py`

- [x] **Step 1: Write failing helper tests**

Add tests for a new function:

```python
from app.domain.price_refresh import ensure_instrument_has_price


def test_ensure_instrument_price_fetches_and_stores_first_price(
    db_session: Session,
) -> None:
    held_instrument = instrument("INDA")
    db_session.add(held_instrument)
    db_session.commit()
    client = ScriptedMarketDataClient({"INDA": market_price("INDA", "44.50")})

    updated = ensure_instrument_has_price(db_session, held_instrument, client)

    saved = get_latest_prices_for_instruments(
        db_session,
        [held_instrument.id],
    )[held_instrument.id]
    assert updated is True
    assert saved.close_price == Decimal("44.50")
    assert client.requests == [("INDA", "NYSEARCA", "USD")]


def test_ensure_instrument_price_reuses_existing_price(
    db_session: Session,
) -> None:
    held_instrument = instrument("INDA")
    db_session.add(held_instrument)
    db_session.flush()
    existing = Price(
        instrument=held_instrument,
        price_date=date(2026, 6, 4),
        close_price=Decimal("43.00"),
        currency="USD",
        source="fake",
    )
    db_session.add(existing)
    db_session.commit()
    client = ScriptedMarketDataClient({"INDA": market_price("INDA", "44.50")})

    updated = ensure_instrument_has_price(db_session, held_instrument, client)

    assert updated is False
    assert client.requests == []
```

Add parameterized non-blocking tests for provider exception, `None`, and a
`NaN` close. Each must assert `False` and no stored price.

- [x] **Step 2: Run tests and verify RED**

Run:

```bash
cd backend
source .venv/bin/activate
pytest tests/test_price_refresh.py -q
```

Expected: import failure because `ensure_instrument_has_price` does not exist.

- [x] **Step 3: Implement the focused helper**

In `backend/app/domain/price_refresh.py`, implement:

```python
def ensure_instrument_has_price(
    db: Session,
    instrument: Instrument,
    market_data_client: MarketDataClient,
) -> bool:
    if get_latest_prices_for_instruments(db, [instrument.id]):
        return False

    try:
        market_price = market_data_client.get_latest_close(
            instrument.symbol,
            instrument.exchange,
            instrument.currency,
        )
    except Exception:
        return False

    if market_price is None or not market_price.close_price.is_finite():
        return False

    upsert_price(db, instrument, market_price)
    db.commit()
    return True
```

Import `Instrument` and `get_latest_prices_for_instruments`.

- [x] **Step 4: Run tests and verify GREEN**

Run:

```bash
cd backend
source .venv/bin/activate
pytest tests/test_price_refresh.py -q
```

Expected: all price-refresh tests pass.

- [x] **Step 5: Commit**

```bash
git add backend/app/domain/price_refresh.py backend/tests/test_price_refresh.py
git commit -m "feat: fetch first instrument price"
```

### Task 2: Price Newly Added Holdings

**Files:**
- Modify: `backend/app/api/v1/holdings.py`
- Modify: `backend/tests/test_holdings_api.py`

- [ ] **Step 1: Write failing endpoint tests**

Add a fake market-data client and update the `save_holding` test helper to pass
it into `add_holding`. Add tests asserting:

```python
def test_creating_first_holding_fetches_instrument_price(...) -> None:
    client = FakeMarketDataClient(market_price("VOO", "500.25"))

    response = save_holding(
        holding_payload(),
        authenticated_user,
        db_session,
        market_data_client=client,
    )

    saved = get_latest_prices_for_instruments(
        db_session,
        [response.instrument.id],
    )
    assert saved[response.instrument.id].close_price == Decimal("500.25")
    assert client.requests == [("VOO", "NYSEARCA", "USD")]
```

Also test that adding a second holding for the same instrument makes only one
market-data request, and that a raising client still returns the created
holding.

- [ ] **Step 2: Run endpoint tests and verify RED**

Run:

```bash
cd backend
source .venv/bin/activate
pytest tests/test_holdings_api.py -q
```

Expected: tests fail because `add_holding` has no market-data dependency and
does not store a price.

- [ ] **Step 3: Inject and call the existing market-data client**

In `backend/app/api/v1/holdings.py`:

- import `get_market_data_client` from `app.api.v1.portfolio`;
- import `ensure_instrument_has_price`;
- import `MarketDataClient`;
- add `market_data_client` as a dependency of `add_holding`;
- after `create_holding`, call:

```python
ensure_instrument_has_price(
    db,
    holding.instrument,
    market_data_client,
)
```

Return the holding response regardless of the helper result.

- [ ] **Step 4: Run endpoint tests and verify GREEN**

Run:

```bash
cd backend
source .venv/bin/activate
pytest tests/test_holdings_api.py tests/test_price_refresh.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/v1/holdings.py backend/tests/test_holdings_api.py
git commit -m "feat: price newly added holdings"
```

### Task 3: Invalidate Portfolio Queries After Holding Mutations

**Files:**
- Modify: `frontend/src/features/holdings/HoldingsPage.tsx`
- Modify: `frontend/src/features/holdings/holdings.test.tsx`

- [ ] **Step 1: Write failing frontend tests**

Change `renderHoldingsRoute` to return its query client. Add one test for each
create, update, and delete success path that spies on `invalidateQueries` and
asserts:

```typescript
expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["holdings"] });
expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["portfolio-snapshot"] });
expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["portfolio-breakdowns"] });
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
cd frontend
npm run test -- src/features/holdings/holdings.test.tsx
```

Expected: snapshot and breakdown invalidation assertions fail.

- [ ] **Step 3: Centralize mutation invalidation**

Add inside `HoldingsPage`:

```typescript
async function invalidateHoldingQueries() {
  await Promise.all([
    queryClient.invalidateQueries({ queryKey: ["holdings"] }),
    queryClient.invalidateQueries({ queryKey: ["portfolio-snapshot"] }),
    queryClient.invalidateQueries({ queryKey: ["portfolio-breakdowns"] }),
  ]);
}
```

Call it from successful create, update, and delete handlers.

- [ ] **Step 4: Run tests and verify GREEN**

Run:

```bash
cd frontend
npm run test -- src/features/holdings/holdings.test.tsx
```

Expected: all holdings frontend tests pass.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/holdings/HoldingsPage.tsx \
  frontend/src/features/holdings/holdings.test.tsx
git commit -m "fix: refresh portfolio after holding changes"
```

### Task 4: Full Verification

**Files:**
- Review all files changed in Tasks 1-3.

- [ ] **Step 1: Run backend verification**

```bash
cd backend
source .venv/bin/activate
ruff check .
pytest
```

Expected: lint clean and zero test failures.

- [ ] **Step 2: Run frontend verification**

```bash
cd frontend
npm run lint
npm run test
npm run build
```

Expected: lint, tests, and production build succeed.

- [ ] **Step 3: Verify diff and tracking**

```bash
git diff --check
git status --short
```

Expected: no whitespace errors and only planned files are changed.

- [ ] **Step 4: Commit final cleanup if needed**

If verification requires formatting-only changes:

```bash
git add backend frontend docs/superpowers/plans/2026-06-21-first-holding-price.md
git commit -m "test: verify first holding price workflow"
```

Do not create an empty commit.
