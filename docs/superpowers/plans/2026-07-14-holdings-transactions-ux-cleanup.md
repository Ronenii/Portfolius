# Holdings/Transactions UX Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the destructive Holdings create/edit/delete path (which silently wipes transaction history) and make Holdings a pure read-only summary, with Transactions as the sole way to write a position — plus a cross-link between the two pages so the relationship is obvious.

**Architecture:** Delete the holdings-write routes, repository functions, and `HoldingRequest` schema entirely (no migration needed — no schema change, pure code removal). Rewrite `HoldingsPage.tsx` as read-only with a per-row link into a symbol-filtered `TransactionsPage.tsx` (which gains `?symbol=` support). Fold in a one-line onboarding hint on Transactions for users without full trade history.

**Tech Stack:** FastAPI, SQLAlchemy 2.0, pytest (backend). React, TanStack Query, react-router-dom v6, Vitest (frontend). No new dependencies, no new migrations.

## Global Constraints

- No DB schema or migration change — this is route/function/schema removal plus frontend rewiring only.
- Decimals stay serialized as strings in all API responses (unchanged — `HoldingResponse` already does this and is untouched).
- Follow existing test file conventions exactly: backend tests use the `authenticated_user`/`second_user`/`db_session` fixtures already defined in conftest; frontend tests mock `../../lib/supabase` and `../profile/profile-api` the same way every existing page test does.
- Do not touch `backend/app/domain/projection.py`, `backend/app/domain/portfolio_service.py`, `backend/app/api/v1/portfolio.py`, or anything under `backend/app/data/repositories/transactions.py` — those belong to the (separately reviewed) Step 5c work and are out of scope here.
- Do not modify `backend/app/data/repositories/instruments.py`'s `refresh_instrument_metadata` / `MANAGED_METADATA_FIELDS` — they are still used by `backend/app/domain/metadata_refresh.py` (an unrelated background job) and must stay.

---

## Task 1: Backend — Remove Holdings Write Routes, Repository Functions, and Schema

**Files:**
- Modify: `backend/app/api/v1/holdings.py`
- Modify: `backend/app/data/repositories/holdings.py`
- Modify: `backend/app/data/repositories/instruments.py`
- Modify: `backend/app/schemas/holdings.py`
- Modify: `backend/tests/test_holdings_api.py`

**Interfaces:**
- Produces: `list_holdings(current_user, db) -> list[HoldingResponse]` and `read_holding(holding_id, current_user, db) -> HoldingResponse`, both in `app.api.v1.holdings`, unchanged in behavior — later tasks do not depend on anything new here.
- Consumes: nothing from other tasks in this plan.

This is a removal task, not new-feature work, so there's no "write a failing test for new behavior" step — instead: delete the code, run the suite to see what breaks, then fix the tests to match the new (smaller) contract.

- [ ] **Step 1: Delete the write routes and helpers from `backend/app/api/v1/holdings.py`**

Replace the entire file with:

```python
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.auth import AuthenticatedUser, get_current_user
from app.data.database import get_db
from app.data.repositories.holdings import get_holding_for_user, list_holdings_for_user
from app.schemas.holdings import HoldingResponse

router = APIRouter(tags=["holdings"])


def not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Holding not found",
    )


@router.get("/api/v1/holdings", response_model=list[HoldingResponse])
def list_holdings(
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[HoldingResponse]:
    holdings = list_holdings_for_user(db, current_user.user_id)
    return [HoldingResponse.model_validate(holding) for holding in holdings]


@router.get("/api/v1/holdings/{holding_id}", response_model=HoldingResponse)
def read_holding(
    holding_id: int,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> HoldingResponse:
    holding = get_holding_for_user(db, current_user.user_id, holding_id)
    if holding is None:
        raise not_found()
    return HoldingResponse.model_validate(holding)
```

This removes `add_holding`, `edit_holding`, `remove_holding`, `enrich_holding_payload`, `merge_profile_into_payload`, `value_or_fallback`, and the now-unused imports (`logging`, `Response`, `Instrument`, `InstrumentLookupClient`/`get_instrument_lookup_client`, `get_market_data_client`, `create_holding`/`delete_holding`/`update_holding`, `get_instrument_for_payload`/`instrument_has_useful_metadata`/`instrument_to_search_result`/`refresh_instrument_metadata`, `ensure_instrument_has_price`, `is_etf`, `MarketDataClient`, `HoldingRequest`, `InstrumentSearchResult`).

- [ ] **Step 2: Delete the write functions from `backend/app/data/repositories/holdings.py`**

Replace the entire file with:

```python
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.data.models import Holding, Instrument
from app.data.repositories.instruments import get_instrument_for_payload
from app.schemas.transactions import TransactionRequest


def fill_missing_instrument_metadata(
    instrument: Instrument,
    payload: TransactionRequest,
) -> None:
    for field in (
        "name",
        "currency",
        "asset_class",
        "sector",
        "country",
        "region",
    ):
        if getattr(instrument, field) is None and getattr(payload, field) is not None:
            setattr(instrument, field, getattr(payload, field))


def get_or_create_instrument(db: Session, payload: TransactionRequest) -> Instrument:
    instrument = get_instrument_for_payload(db, payload)
    if instrument is None:
        instrument = Instrument(
            symbol=payload.symbol,
            name=payload.name,
            exchange=payload.exchange,
            currency=payload.currency,
            asset_class=payload.asset_class,
            sector=payload.sector,
            country=payload.country,
            region=payload.region,
        )
        db.add(instrument)
        db.flush()
    else:
        fill_missing_instrument_metadata(instrument, payload)

    return instrument


def list_holdings_for_user(db: Session, user_id: str) -> list[Holding]:
    # Eager-load the instrument: the snapshot reads holding.instrument per row,
    # so a lazy-load would issue an N+1 query per holding.
    return list(
        db.scalars(
            select(Holding)
            .where(Holding.user_id == user_id)
            .options(selectinload(Holding.instrument))
        )
    )


def list_instruments_for_user_holdings(
    db: Session,
    user_id: str,
) -> list[Instrument]:
    return list(
        db.scalars(
            select(Instrument)
            .join(Holding)
            .where(Holding.user_id == user_id)
            .distinct()
            .order_by(Instrument.symbol, Instrument.exchange)
        )
    )


def list_etf_instruments_for_user_holdings(
    db: Session,
    user_id: str,
) -> list[Instrument]:
    return list(
        db.scalars(
            select(Instrument)
            .join(Holding)
            .where(
                Holding.user_id == user_id,
                func.lower(Instrument.asset_class) == "etf",
            )
            .distinct()
            .order_by(Instrument.symbol, Instrument.exchange)
        )
    )


def list_all_instruments_with_holdings(db: Session) -> list[Instrument]:
    return list(
        db.scalars(
            select(Instrument)
            .join(Holding)
            .distinct()
            .order_by(Instrument.symbol, Instrument.exchange)
        )
    )


def get_holding_for_user(
    db: Session,
    user_id: str,
    holding_id: int,
) -> Holding | None:
    return db.scalar(
        select(Holding).where(
            Holding.id == holding_id,
            Holding.user_id == user_id,
        )
    )
```

This removes `create_holding`, `update_holding`, `delete_holding`, `_opening_balance_transaction`, and the now-unused imports (`date`, `Decimal`, `delete`, `Transaction`, `recompute_holding`, `InsufficientQuantityError`). Note the type hints on `fill_missing_instrument_metadata`/`get_or_create_instrument` change from `HoldingRequest` to `TransactionRequest` — `get_or_create_instrument` is called today only from `app/api/v1/transactions.py`'s `resolve_transaction_instrument` with a `TransactionRequest`, so this corrects an existing stale annotation rather than introducing a new dependency direction (schemas do not import repositories, so this does not create a cycle).

- [ ] **Step 3: Update `backend/app/data/repositories/instruments.py`**

In `get_instrument_for_payload`, change the type hint and import:

```python
from app.schemas.transactions import TransactionRequest
```

(replacing `from app.schemas.holdings import HoldingRequest`), and:

```python
def get_instrument_for_payload(
    db: Session,
    payload: TransactionRequest,
) -> Instrument | None:
```

(replacing the `HoldingRequest` parameter type). Delete the now-unused `instrument_has_useful_metadata` function entirely (its only caller was `enrich_holding_payload`, deleted in Step 1) — confirm first with `rg -n "instrument_has_useful_metadata" backend` that no other file references it. Leave `refresh_instrument_metadata`, `MANAGED_METADATA_FIELDS`, `instrument_to_search_result`, `list_all_instruments`, and `search_local_instruments` untouched — they're used elsewhere (`app/domain/metadata_refresh.py`, `search_local_instruments` itself).

- [ ] **Step 4: Delete `HoldingRequest` from `backend/app/schemas/holdings.py`**

Remove the `HoldingRequest` class (and its now-unused `field_validator` import if nothing else in the file needs it — check: `HoldingResponse` only needs `field_serializer`, so the import line becomes `from pydantic import BaseModel, ConfigDict, field_serializer`). Keep `normalize_optional_text`, `InstrumentResponse`, and `HoldingResponse` exactly as they are — `normalize_optional_text` is still imported by `app/schemas/transactions.py`.

- [ ] **Step 5: Run the full backend test suite to see what breaks**

Run: `cd backend && pytest -v 2>&1 | tail -60`
Expected: `tests/test_holdings_api.py` fails at collection (`ImportError: cannot import name 'add_holding' from 'app.api.v1.holdings'`), confirming exactly which file needs rewriting next. All other test files should still collect and pass — if anything outside `test_holdings_api.py` fails, stop and investigate before continuing (it means something depends on the removed code that this plan didn't account for).

- [ ] **Step 6: Rewrite `backend/tests/test_holdings_api.py` for the read-only contract**

Replace the entire file with:

```python
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.api.v1.holdings import list_holdings, read_holding, router
from app.core.auth import AuthenticatedUser, get_current_user
from app.data.models import Holding, Instrument
from app.main import app


def make_holding(
    db_session: Session,
    user_id: str,
    **overrides: object,
) -> Holding:
    instrument_fields: dict[str, object] = {
        "symbol": "VOO",
        "name": "Vanguard S&P 500 ETF",
        "exchange": "NYSEARCA",
        "currency": "USD",
        "asset_class": "ETF",
        "sector": "Broad Market",
        "country": "United States",
        "region": "North America",
    }
    for field in list(instrument_fields):
        if field in overrides:
            instrument_fields[field] = overrides.pop(field)
    instrument = Instrument(**instrument_fields)
    db_session.add(instrument)
    db_session.flush()

    holding_fields: dict[str, object] = {
        "user_id": user_id,
        "instrument_id": instrument.id,
        "quantity": Decimal("12.5"),
        "average_cost": Decimal("145.20"),
    }
    holding_fields.update(overrides)
    holding = Holding(**holding_fields)
    db_session.add(holding)
    db_session.commit()
    db_session.refresh(holding)
    return holding


def test_holdings_routes_require_auth() -> None:
    route_paths = {getattr(route, "path", None) for route in app.routes}

    assert {"/api/v1/holdings", "/api/v1/holdings/{holding_id}"}.issubset(
        route_paths
    )
    for route in router.routes:
        dependency_calls = {
            dependency.call for dependency in route.dependant.dependencies
        }
        assert get_current_user in dependency_calls


def test_listing_holdings_returns_only_authenticated_users_holdings(
    authenticated_user: AuthenticatedUser,
    second_user: AuthenticatedUser,
    db_session: Session,
) -> None:
    own_holding = make_holding(db_session, authenticated_user.user_id, symbol="VOO")
    make_holding(db_session, second_user.user_id, symbol="VXUS")

    holdings = list_holdings(authenticated_user, db_session)

    assert [holding.id for holding in holdings] == [own_holding.id]


def test_getting_own_holding_returns_it(
    authenticated_user: AuthenticatedUser,
    db_session: Session,
) -> None:
    holding = make_holding(db_session, authenticated_user.user_id)

    response = read_holding(holding.id, authenticated_user, db_session)

    assert response.id == holding.id
    assert response.instrument.symbol == "VOO"
    assert response.quantity == Decimal("12.5")


def test_getting_another_users_holding_returns_404(
    authenticated_user: AuthenticatedUser,
    second_user: AuthenticatedUser,
    db_session: Session,
) -> None:
    other_holding = make_holding(db_session, second_user.user_id)

    with pytest.raises(HTTPException) as exc_info:
        read_holding(other_holding.id, authenticated_user, db_session)

    assert exc_info.value.status_code == 404
```

This drops every create/update/delete test (they tested `HoldingRequest` validation and the enrichment/price-lookup behavior of `add_holding`/`edit_holding`, all deleted) and replaces the list/get fixture setup with direct `Instrument`/`Holding` row construction — since holdings are a pure read-model now, there's no API-level "create" step to use as test setup.

- [ ] **Step 7: Run the full backend suite and lint**

Run: `cd backend && pytest -v && ruff check app tests`
Expected: all tests PASS, ruff reports no errors. Pay particular attention to `tests/test_portfolio_api.py`, `tests/test_simulation.py`, and any assistant-tool tests — they read `holdings` via `list_holdings_for_user`/`build_snapshot_for_user`, both untouched, so they should be unaffected; confirm they still pass as a regression check.

- [ ] **Step 8: Commit**

```bash
cd /home/roneng/Portfolius
git add backend/app/api/v1/holdings.py backend/app/data/repositories/holdings.py backend/app/data/repositories/instruments.py backend/app/schemas/holdings.py backend/tests/test_holdings_api.py
git commit -m "$(cat <<'EOF'
refactor: remove destructive holdings write API

Editing or deleting a holding used to silently delete all transaction
history for that instrument and replace it with a synthetic opening-balance
row. Holdings is now list/get only; Transactions is the sole write path.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Frontend — Holdings Page Becomes Read-Only With a Transactions Cross-Link

**Files:**
- Modify: `frontend/src/features/holdings/holdings-api.ts`
- Modify: `frontend/src/features/holdings/HoldingsPage.tsx`
- Modify: `frontend/src/features/holdings/holdings.test.tsx`

**Interfaces:**
- Consumes: `GET /api/v1/holdings` (unchanged, from Task 1).
- Produces: the row-level link shape `/transactions?symbol=<SYMBOL>` (Task 3 makes that query param actually filter the list — the two tasks can still be implemented in either order since Task 3 only depends on the URL shape, not on Task 2's exact markup).

**Depends on:** Task 1 must be committed first (the backend no longer serves the write routes this page used to call).

- [ ] **Step 1: Trim `frontend/src/features/holdings/holdings-api.ts`**

Replace the entire file with:

```ts
import { apiRequest } from "../../lib/api";

export type Instrument = {
  id: number;
  symbol: string;
  name: string | null;
  exchange: string;
  currency: string | null;
  asset_class: string | null;
  sector: string | null;
  country: string | null;
  region: string | null;
};

export type Holding = {
  id: number;
  instrument: Instrument;
  quantity: string;
  average_cost: string;
  created_at: string;
  updated_at: string;
};

export function listHoldings(accessToken: string) {
  return apiRequest<Holding[]>("/api/v1/holdings", { accessToken });
}
```

This removes `HoldingPayload`, `createHolding`, `updateHolding`, `deleteHolding`.

- [ ] **Step 2: Rewrite `frontend/src/features/holdings/HoldingsPage.tsx` as read-only**

Replace the entire file with:

```tsx
import { useQuery } from "@tanstack/react-query";
import { ArrowLeftRight } from "lucide-react";
import { Link } from "react-router-dom";

import { TrendLoader } from "../../components/ui/TrendLoader";
import { useAuth } from "../auth/AuthContext";
import { listHoldings } from "./holdings-api";

function displayValue(value: string | null | undefined) {
  return value && value.trim() ? value : "-";
}

function formatDecimal(value: string) {
  const numericValue = Number(value);
  return new Intl.NumberFormat("en", {
    maximumFractionDigits: 8,
  }).format(Number.isFinite(numericValue) ? numericValue : 0);
}

function formatMoney(value: string, currency = "USD") {
  const numericValue = Number(value);
  return new Intl.NumberFormat("en", {
    currency,
    style: "currency",
  }).format(Number.isFinite(numericValue) ? numericValue : 0);
}

export default function HoldingsPage() {
  const { accessToken } = useAuth();

  const holdingsQuery = useQuery({
    enabled: Boolean(accessToken),
    queryKey: ["holdings", accessToken],
    queryFn: () => listHoldings(accessToken ?? ""),
  });

  const holdings = holdingsQuery.data ?? [];

  return (
    <section className="dashboard-page holdings-page" aria-labelledby="holdings-title">
      <header className="page-header">
        <div>
          <p className="eyebrow">Positions</p>
          <h1 id="holdings-title">Holdings</h1>
        </div>
      </header>

      <div className="holdings-workspace">
        <section className="holdings-panel" aria-labelledby="holdings-list-title">
          <div className="panel-heading">
            <div>
              <p className="panel-label">Read-only summary</p>
              <h2 id="holdings-list-title">Current positions</h2>
            </div>
          </div>

          {holdingsQuery.isLoading ? (
            <TrendLoader label="Loading holdings" />
          ) : null}

          {holdingsQuery.error ? (
            <p className="form-error">Holdings unavailable</p>
          ) : null}

          {!holdingsQuery.isLoading && !holdingsQuery.error && holdings.length === 0 ? (
            <div className="empty-state">
              <strong>No holdings yet</strong>
              <span>Record a transaction to start building this portfolio.</span>
              <Link className="button button--ghost" to="/transactions">
                Go to Transactions
              </Link>
            </div>
          ) : null}

          {holdings.length > 0 ? (
            <div className="holdings-table-wrap">
              <table className="holdings-table">
                <thead>
                  <tr>
                    <th>Symbol</th>
                    <th>Name</th>
                    <th>Exchange</th>
                    <th>Currency</th>
                    <th className="num-col">Quantity</th>
                    <th className="num-col">Purchase cost</th>
                    <th className="actions-col">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {holdings.map((holding) => (
                    <tr key={holding.id}>
                      <td data-label="Symbol">
                        <strong>{holding.instrument.symbol.toUpperCase()}</strong>
                      </td>
                      <td data-label="Name">{displayValue(holding.instrument.name)}</td>
                      <td data-label="Exchange">
                        {displayValue(holding.instrument.exchange)}
                      </td>
                      <td data-label="Currency">
                        {holding.instrument.currency?.toUpperCase() ?? "-"}
                      </td>
                      <td data-label="Quantity" className="num">
                        {formatDecimal(holding.quantity)}
                      </td>
                      <td data-label="Purchase cost" className="num">
                        {formatMoney(
                          holding.average_cost,
                          holding.instrument.currency ?? "USD"
                        )}
                      </td>
                      <td data-label="Actions">
                        <div className="row-actions">
                          <Link
                            aria-label={`View transactions for ${holding.instrument.symbol}`}
                            className="icon-button"
                            to={`/transactions?symbol=${encodeURIComponent(holding.instrument.symbol)}`}
                          >
                            <ArrowLeftRight aria-hidden="true" />
                          </Link>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}
        </section>
      </div>
    </section>
  );
}
```

This removes the entire create/edit form panel, `editingHolding`/`confirmDeleteId`/`errors` state, and all three mutations. Each row's `Actions` cell now contains one `Link` (styled with the existing `icon-button` class) to that symbol's filtered transaction history instead of Edit/Delete buttons.

- [ ] **Step 3: Rewrite `frontend/src/features/holdings/holdings.test.tsx`**

Replace the entire file with:

```tsx
import type { Session } from "@supabase/supabase-js";
import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, within } from "@testing-library/react";
import { RouterProvider } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { createQueryClient } from "../../app/query-client";
import { createAppRouter } from "../../app/router";
import { supabase } from "../../lib/supabase";
import { getProfile } from "../profile/profile-api";
import { listHoldings, type Holding } from "./holdings-api";

vi.mock("../../lib/supabase", () => ({
  supabase: {
    auth: {
      getSession: vi.fn(),
      onAuthStateChange: vi.fn(),
      signInWithOAuth: vi.fn(),
      signInWithOtp: vi.fn(),
      signOut: vi.fn(),
    },
  },
}));

vi.mock("../profile/profile-api", () => ({
  getProfile: vi.fn(),
  saveProfile: vi.fn(),
}));

vi.mock("./holdings-api", () => ({
  listHoldings: vi.fn(),
}));

const mockSession = {
  access_token: "access-token",
  refresh_token: "refresh-token",
  expires_in: 3600,
  token_type: "bearer",
  user: { id: "user-123", email: "investor@example.com" },
} as Session;

const mockProfile = {
  id: 1,
  user_id: "user-123",
  display_name: "Ronen",
  base_currency: "USD",
  time_horizon: "10+ years",
  investment_frequency: "monthly",
  risk_tolerance: null,
  interest_tags: [],
  excluded_sectors: [],
  goals_note: null,
  created_at: "2026-06-04T00:00:00Z",
  updated_at: "2026-06-04T00:00:00Z",
};

const appleHolding: Holding = {
  id: 1,
  instrument: {
    id: 10,
    symbol: "AAPL",
    name: "Apple Inc.",
    exchange: "NASDAQ",
    currency: "USD",
    asset_class: "Equity",
    sector: "Technology",
    country: "United States",
    region: "North America",
  },
  quantity: "12.5",
  average_cost: "145.20",
  created_at: "2026-06-04T00:00:00Z",
  updated_at: "2026-06-04T00:00:00Z",
};

function mockAuthState() {
  vi.mocked(supabase.auth.getSession).mockResolvedValue(
    {
      data: { session: mockSession },
      error: null,
    } as Awaited<ReturnType<typeof supabase.auth.getSession>>
  );
  vi.mocked(supabase.auth.onAuthStateChange).mockReturnValue({
    data: {
      subscription: {
        id: "subscription-id",
        callback: vi.fn(),
        unsubscribe: vi.fn(),
      },
    },
  });
}

function renderHoldingsRoute() {
  const queryClient = createQueryClient();
  const rendered = render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider
        router={createAppRouter(["/holdings"])}
        future={{ v7_startTransition: true }}
      />
    </QueryClientProvider>
  );
  return { ...rendered, queryClient };
}

describe("holdings page", () => {
  afterEach(() => {
    cleanup();
  });

  beforeEach(() => {
    vi.resetAllMocks();
    mockAuthState();
    vi.mocked(getProfile).mockResolvedValue(mockProfile);
    vi.mocked(listHoldings).mockResolvedValue([appleHolding]);
  });

  it("lists fetched holdings", async () => {
    renderHoldingsRoute();

    expect(await screen.findByRole("heading", { name: "Holdings" })).toBeInTheDocument();
    expect(await screen.findByText("AAPL")).toBeInTheDocument();
    expect(screen.getByText("Apple Inc.")).toBeInTheDocument();
    expect(screen.getByText("12.5")).toBeInTheDocument();
    expect(screen.getByText("$145.20")).toBeInTheDocument();
  });

  it("formats decimal fields in the holdings table without trailing zero noise", async () => {
    vi.mocked(listHoldings).mockResolvedValue([
      {
        ...appleHolding,
        quantity: "12.50000000",
        average_cost: "145.20000000",
      },
    ]);

    renderHoldingsRoute();

    const row = await screen.findByRole("row", { name: /AAPL/i });
    expect(within(row).getByText("12.5")).toBeInTheDocument();
    expect(within(row).getByText("$145.20")).toBeInTheDocument();
    expect(within(row).queryByText("12.50000000")).not.toBeInTheDocument();
    expect(within(row).queryByText("145.20000000")).not.toBeInTheDocument();
  });

  it("shows an empty state linking to Transactions when there are no holdings", async () => {
    vi.mocked(listHoldings).mockResolvedValue([]);

    renderHoldingsRoute();

    expect(await screen.findByText("No holdings yet")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Go to Transactions" })).toHaveAttribute(
      "href",
      "/transactions"
    );
  });

  it("links each row to its filtered transaction history", async () => {
    renderHoldingsRoute();

    const row = await screen.findByRole("row", { name: /AAPL/i });
    expect(
      within(row).getByRole("link", { name: "View transactions for AAPL" })
    ).toHaveAttribute("href", "/transactions?symbol=AAPL");
  });

  it("does not render create, edit, or delete controls", async () => {
    renderHoldingsRoute();

    await screen.findByRole("row", { name: /AAPL/i });

    expect(screen.queryByRole("button", { name: "Save holding" })).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Symbol")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Edit AAPL" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Delete AAPL" })).not.toBeInTheDocument();
  });
});
```

- [ ] **Step 4: Run the frontend Holdings test and lint**

Run: `cd frontend && npm test -- holdings && npm run lint`
Expected: all tests in `holdings.test.tsx` PASS, no lint errors. If `npm run lint` flags unused imports (e.g. leftover `Pencil`/`Trash2`/`Check`/`X` icon imports or `Button` import) anywhere, remove them — the rewritten `HoldingsPage.tsx` above only imports `ArrowLeftRight`, `Link`, `TrendLoader`, `useAuth`, `listHoldings`.

- [ ] **Step 5: Commit**

```bash
cd /home/roneng/Portfolius
git add frontend/src/features/holdings/holdings-api.ts frontend/src/features/holdings/HoldingsPage.tsx frontend/src/features/holdings/holdings.test.tsx
git commit -m "$(cat <<'EOF'
refactor: make Holdings page a read-only summary

Removes the create/edit/delete form (which silently rewrote transaction
history) and adds a per-row link into the filtered Transactions view instead.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Frontend — Transactions Page Symbol Filter and Onboarding Hint

**Files:**
- Modify: `frontend/src/features/transactions/transactions-api.ts`
- Modify: `frontend/src/features/transactions/TransactionsPage.tsx`
- Modify: `frontend/src/features/transactions/transactions.test.tsx`

**Interfaces:**
- Consumes: `Link` targets produced by Task 2 (`/transactions?symbol=AAPL`) — this task makes that query param actually filter the list.
- Produces: `listTransactions(accessToken: string, symbol?: string)` — the added second parameter is additive (existing single-argument calls keep working).

**Depends on:** Task 1 (backend `symbol` filter already exists and needs no changes) — this task can run independently of Task 2's exact link markup, since it only needs the URL shape `?symbol=<value>`.

- [ ] **Step 1: Write the failing test for the symbol filter**

Add this test inside the `describe("transactions page", ...)` block in `frontend/src/features/transactions/transactions.test.tsx`, after the `"lists fetched transactions"` test:

```tsx
  it("filters by the symbol query param when present", async () => {
    const queryClient = createQueryClient();
    render(
      <QueryClientProvider client={queryClient}>
        <RouterProvider
          router={createAppRouter(["/transactions?symbol=AAPL"])}
          future={{ v7_startTransition: true }}
        />
      </QueryClientProvider>
    );

    await screen.findByRole("heading", { name: "Transactions" });

    await waitFor(() => {
      expect(listTransactions).toHaveBeenCalledWith("access-token", "AAPL");
    });
  });
```

`waitFor`, `render`, `screen`, `QueryClientProvider`, `RouterProvider`, `createQueryClient`, and `createAppRouter` are all already imported at the top of `transactions.test.tsx` — no import changes needed for this test.

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd frontend && npm test -- transactions -t "filters by the symbol"`
Expected: FAIL — `listTransactions` is currently called with only one argument (`listTransactions(accessToken)`), so `toHaveBeenCalledWith("access-token", "AAPL")` does not match.

- [ ] **Step 3: Add the optional `symbol` parameter to `listTransactions`**

In `frontend/src/features/transactions/transactions-api.ts`, replace:

```ts
export function listTransactions(accessToken: string) {
  return apiRequest<Transaction[]>("/api/v1/transactions", { accessToken });
}
```

with:

```ts
export function listTransactions(accessToken: string, symbol?: string) {
  const query = symbol ? `?symbol=${encodeURIComponent(symbol)}` : "";
  return apiRequest<Transaction[]>(`/api/v1/transactions${query}`, { accessToken });
}
```

- [ ] **Step 4: Read the `symbol` query param in `TransactionsPage.tsx` and pass it through**

In `frontend/src/features/transactions/TransactionsPage.tsx`:

Add `useSearchParams` to the react-router-dom import:

```tsx
import { useSearchParams } from "react-router-dom";
```

Inside `TransactionsPage`, right after the `queryClient` line, add:

```tsx
  const [searchParams] = useSearchParams();
  const symbolFilter = searchParams.get("symbol");
```

Replace the `transactionsQuery` definition:

```tsx
  const transactionsQuery = useQuery({
    enabled: Boolean(accessToken),
    queryKey: ["transactions", accessToken],
    queryFn: () => listTransactions(accessToken ?? ""),
  });
```

with:

```tsx
  const transactionsQuery = useQuery({
    enabled: Boolean(accessToken),
    queryKey: ["transactions", accessToken, symbolFilter],
    queryFn: () => listTransactions(accessToken ?? "", symbolFilter ?? undefined),
  });
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `cd frontend && npm test -- transactions -t "filters by the symbol"`
Expected: PASS.

- [ ] **Step 6: Add the "filtered to" indicator and clear-filter link**

In `TransactionsPage.tsx`, inside the list panel's `panel-heading` div (the one containing `<h2 id="transactions-list-title">All transactions</h2>`), add right after the closing `</div>` of the `<p className="panel-label">Transaction log</p><h2>...</h2>` block:

```tsx
            {symbolFilter ? (
              <p className="panel-label">
                Filtered to {symbolFilter}. <Link to="/transactions">Clear filter</Link>
              </p>
            ) : null}
```

This requires `Link` in the same `react-router-dom` import as `useSearchParams`:

```tsx
import { Link, useSearchParams } from "react-router-dom";
```

- [ ] **Step 7: Add the onboarding hint for opening balances**

In `TransactionsPage.tsx`, inside the form panel's `panel-heading` div (the one with `<h2 id="transaction-form-title">`), add directly after that `</div>` and before the closing `</div>` of `panel-heading` (i.e. as a sibling, still inside `panel-heading`, only rendered for a new transaction, not while editing):

```tsx
          {!editingTransaction ? (
            <p className="field-hint">
              Don&apos;t have your full trade history? Log a single buy for your
              current quantity and average cost — you can backdate it.
            </p>
          ) : null}
```

Place this line right after the `panel-heading` div closes (i.e. between `</div>` (closing `panel-heading`) and the `<form className="holding-form" ...>` line), so it reads as a hint under the section heading rather than inside the heading's flex row.

- [ ] **Step 8: Write a test for the hint and the clear-filter link**

Add these two tests to `transactions.test.tsx`, after the `"filters by the symbol"` test added in Step 1:

```tsx
  it("shows an onboarding hint for logging an opening balance", async () => {
    renderTransactionsRoute();

    expect(
      await screen.findByText(/Log a single buy for your/)
    ).toBeInTheDocument();
  });

  it("shows a clear-filter link when a symbol filter is active", async () => {
    const queryClient = createQueryClient();
    render(
      <QueryClientProvider client={queryClient}>
        <RouterProvider
          router={createAppRouter(["/transactions?symbol=AAPL"])}
          future={{ v7_startTransition: true }}
        />
      </QueryClientProvider>
    );

    expect(await screen.findByText(/Filtered to AAPL/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Clear filter" })).toHaveAttribute(
      "href",
      "/transactions"
    );
  });
```

- [ ] **Step 9: Run the full Transactions test file and lint**

Run: `cd frontend && npm test -- transactions && npm run lint`
Expected: all tests PASS (including the pre-existing ones — the hint text must not collide with any existing `getByText`/`findByText` assertions in the file; skim the other tests' selectors to confirm none of them use an ambiguous substring match that the new hint text would also satisfy), no lint errors.

- [ ] **Step 10: Commit**

```bash
cd /home/roneng/Portfolius
git add frontend/src/features/transactions/transactions-api.ts frontend/src/features/transactions/TransactionsPage.tsx frontend/src/features/transactions/transactions.test.tsx
git commit -m "$(cat <<'EOF'
feat: filter transactions by symbol and hint at opening-balance entry

Supports the Holdings page's per-row cross-link (?symbol=) and gives new
users a way to onboard an existing position without needing full trade
history.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Documentation — Update the M5 Plan

**Files:**
- Modify: `docs/implementation/m5.md`

**Interfaces:** none — this is a documentation-only task with no code interfaces.

**Depends on:** Tasks 1-3 committed (so the doc describes what actually shipped).

- [ ] **Step 1: Insert the new Milestone Task List entry**

In the "## Milestone Task List" section, after the line `- [x] Step 5c: Goal projection endpoint`, insert:

```
- [ ] Step 6: Holdings/Transactions UX cleanup
```

Then renumber every subsequent entry by +1 (Step 6→7, 7→8, 8→9, 9→10, 10→11, 11→12), so the list reads:

```
- [x] Step 0: M5 repository baseline
- [x] Step 1: Transaction fold math (pure)
- [x] Step 2: Transactions table, migration, and recompute repository
- [x] Step 3: Holdings writes become transaction wrappers
- [x] Step 4a: Transactions API (backend half; split from Step 4 for smaller review units)
- [x] Step 4b: Transactions frontend page
- [x] Step 5a: Goal projection profile fields + migration (split from Step 5 for smaller review units)
- [x] Step 5b: Goal projection math (pure domain)
- [x] Step 5c: Goal projection endpoint
- [ ] Step 6: Holdings/Transactions UX cleanup
- [ ] Step 7: Goal projection frontend (dashboard panel + profile forms)
- [ ] Step 8: PWA install
- [ ] Step 9: CSV import
- [ ] Step 10: Skeleton loading states
- [ ] Step 11: Documentation updates
- [ ] Step 12: End-to-end M5 verification
```

- [ ] **Step 2: Update the two stray numeric cross-references**

Replace `(or a tiny dep only if justified during Step 8)` with `(or a tiny dep only if justified during Step 9)` (the Tech Stack paragraph near the top of the file — this references CSV import, now Step 9).

Replace `mark \`M5\` done in the roadmap only after Step 11 passes` with `mark \`M5\` done in the roadmap only after Step 12 passes` (in the "## Step 10: Documentation Updates" section body, which becomes "## Step 11" after renumbering — make this text edit either before or after the header rename, just make sure the final number is 12).

- [ ] **Step 3: Rewrite the Definition of Done bullet about the holdings API contract**

Replace:

```
- The existing holdings API still behaves per its contract (create/list/update/delete), with the one intentional change that two adds of the same instrument now collapse into a single derived holding (test updated).
```

with:

```
- The holdings API is list/get only (`GET /api/v1/holdings`, `GET /api/v1/holdings/{id}`); all writes happen through `/api/v1/transactions`. Two buys of the same instrument collapse into a single derived holding, same as before.
```

- [ ] **Step 4: Rename the six step headers (6 through 11) to 7 through 12**

In order, so no header temporarily collides with another during the edit:

- `## Step 11: End-to-End M5 Verification` → `## Step 12: End-to-End M5 Verification`
- `## Step 10: Documentation Updates` → `## Step 11: Documentation Updates`
- `## Step 9: Skeleton Loading States` → `## Step 10: Skeleton Loading States`
- `## Step 8: CSV Import` → `## Step 9: CSV Import`
- `## Step 7: PWA Install` → `## Step 8: PWA Install`
- `## Step 6: Goal Projection Frontend` → `## Step 7: Goal Projection Frontend`

- [ ] **Step 5: Insert the new "Step 6: Holdings/Transactions UX Cleanup" section**

Directly before the (now renamed) `## Step 7: Goal Projection Frontend` header, insert:

```markdown
## Step 6: Holdings/Transactions UX Cleanup

Goal: make Holdings a pure read-only summary and Transactions the only way to write a position, closing the destructive edit/delete-holding history-wipe trap.

Files: modify `backend/app/api/v1/holdings.py`, `backend/app/data/repositories/holdings.py`, `backend/app/data/repositories/instruments.py`, `backend/app/schemas/holdings.py`, `backend/tests/test_holdings_api.py`; modify `frontend/src/features/holdings/holdings-api.ts`, `frontend/src/features/holdings/HoldingsPage.tsx`, `frontend/src/features/holdings/holdings.test.tsx`, `frontend/src/features/transactions/transactions-api.ts`, `frontend/src/features/transactions/TransactionsPage.tsx`, `frontend/src/features/transactions/transactions.test.tsx`.

- Remove the holdings `POST`/`PUT`/`DELETE` routes and their supporting repository functions (`create_holding`, `update_holding`, `delete_holding`, `_opening_balance_transaction`) and the now-unused `HoldingRequest` schema. Keep `GET /api/v1/holdings` and `GET /api/v1/holdings/{id}` exactly as-is.
- Holdings page loses its create/edit/delete form and row actions; becomes a read-only table. Each row links to `/transactions?symbol=<SYMBOL>`. Empty state points at Transactions instead of a form.
- Transactions page reads an optional `?symbol=` filter and shows a one-line hint for onboarding an existing position without full history.
- Rewrite this doc's Definition of Done line about the holdings API contract to reflect the new list/get-only contract.

Test cases: backend — auth-required check kept, list/get scoped-to-user tests rewritten against direct model fixtures (no more create-holding path); frontend — Holdings renders read-only with a working empty-state and per-row links, no form/edit/delete controls render; Transactions filters by `?symbol=` and shows the onboarding hint.

Validation: `cd backend && pytest tests/test_holdings_api.py -v && ruff check app tests`; `cd frontend && npm test -- holdings transactions && npm run lint`; then each full suite for regressions.

Stop point: review this plan before Step 7 (Goal projection frontend).
```

- [ ] **Step 6: Verify the renumbering is consistent**

Run: `grep -n "^## Step\|^- \[.\] Step" docs/implementation/m5.md`
Expected output (order matters):

```
- [x] Step 0: M5 repository baseline
- [x] Step 1: Transaction fold math (pure)
- [x] Step 2: Transactions table, migration, and recompute repository
- [x] Step 3: Holdings writes become transaction wrappers
- [x] Step 4a: Transactions API (backend half; split from Step 4 for smaller review units)
- [x] Step 4b: Transactions frontend page
- [x] Step 5a: Goal projection profile fields + migration (split from Step 5 for smaller review units)
- [x] Step 5b: Goal projection math (pure domain)
- [x] Step 5c: Goal projection endpoint
- [ ] Step 6: Holdings/Transactions UX cleanup
- [ ] Step 7: Goal projection frontend (dashboard panel + profile forms)
- [ ] Step 8: PWA install
- [ ] Step 9: CSV import
- [ ] Step 10: Skeleton loading states
- [ ] Step 11: Documentation updates
- [ ] Step 12: End-to-end M5 verification
## Step 0: M5 Repository Baseline
## Step 1: Transaction Fold Math (pure)
## Step 2: Transactions Table, Migration, and Recompute Repository
## Step 3: Holdings Writes Become Transaction Wrappers
## Step 4: Transactions API + Frontend Transactions Page
## Step 5: Goal Projection Backend
## Step 6: Holdings/Transactions UX Cleanup
## Step 7: Goal Projection Frontend
## Step 8: PWA Install
## Step 9: CSV Import
## Step 10: Skeleton Loading States
## Step 11: Documentation Updates
## Step 12: End-to-End M5 Verification
```

If anything doesn't match, fix it before committing — a mismatch here means a step got renamed out of order or a reference was missed.

- [ ] **Step 7: Commit**

```bash
cd /home/roneng/Portfolius
git add docs/implementation/m5.md
git commit -m "$(cat <<'EOF'
docs: insert Step 6 (Holdings/Transactions UX cleanup) into M5 plan

Renumbers Steps 6-11 to 7-12 and updates the Definition of Done to reflect
the new list/get-only holdings API contract.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```
