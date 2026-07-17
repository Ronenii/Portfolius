# Holdings/Transactions UX Cleanup Design

## Goal

Make the relationship between Holdings and Transactions unambiguous, and
eliminate the ability to silently destroy transaction history through the
Holdings UI. Holdings becomes a pure, read-only summary of the transaction
ledger; Transactions becomes the only place a user records or edits activity.

## Problem

Since the transactions migration (M5 Steps 1-3), `holdings` is a derived
read-model recomputed from `transactions`. The Holdings page and its API,
however, still expose a full create/edit/delete form identical in shape to
the Transactions page. Editing or deleting a holding through this form does
not adjust a balance — it deletes **all** transaction history for that
instrument and replaces it with a single synthetic "Opening balance" buy
(`update_holding`/`delete_holding` in `data/repositories/holdings.py`). A
user who built up real trade history via Transactions and then tweaked a
number on the Holdings page would silently lose that history. Independently
of the data-loss risk, having two near-identical forms with overlapping
purpose is confusing on its own.

## Behavior

**Holdings** (`GET /api/v1/holdings`, `GET /api/v1/holdings/{id}`) remains
exactly as-is: a read-only list/detail view of current derived positions.
No create, update, or delete route exists for holdings anymore.

**Transactions** remains the sole write path for positions: buys, sells, and
opening balances (a buy transaction dated whenever the user's history
starts, or today if unknown) are all just transactions.

**Cross-navigation:** each row on the Holdings page links to the
Transactions page pre-filtered to that instrument's symbol, so a user
looking at "why is my AAPL position what it is" can see the ledger that
produced it in one click.

## Architecture

### Backend

- `app/api/v1/holdings.py`: remove the `POST`/`PUT`/`DELETE` routes
  (`add_holding`, `edit_holding`, `remove_holding`) and the helpers that only
  existed to support them (`enrich_holding_payload`,
  `merge_profile_into_payload`, `value_or_fallback`). Keep `list_holdings`
  and `read_holding` and their imports.
- `app/data/repositories/holdings.py`: remove `create_holding`,
  `update_holding`, `delete_holding`, `_opening_balance_transaction`. Keep
  `get_or_create_instrument` and `fill_missing_instrument_metadata` — these
  are still imported by the transactions instrument-resolution path
  (`app/api/v1/transactions.py`). Keep all `list_*`/`get_holding_for_user`
  read helpers.
- `app/schemas/holdings.py`: remove `HoldingRequest` (only consumer was the
  removed routes). Keep `HoldingResponse`/`InstrumentResponse`.
- No migration needed — no schema change, only route/function removal.

### Frontend

- `HoldingsPage.tsx`: remove the "Add holding" form panel and the per-row
  Edit/Delete actions and their supporting state
  (`editingHolding`/`confirmDeleteId`/mutations). Table remains, showing
  current positions read-only. Each row gains a "View transactions" link to
  `/transactions?symbol=<SYMBOL>`. Empty state copy changes from "Add a
  manual position to start building this portfolio" to something pointing
  at Transactions instead (e.g. "No holdings yet — record a transaction to
  get started"), with a link/button to `/transactions`.
- `holdings-api.ts`: remove `createHolding`/`updateHolding`/`deleteHolding`
  and `HoldingPayload`. Keep `listHoldings`/`Holding`.
- `TransactionsPage.tsx`: read an optional `symbol` query param
  (`useSearchParams` or equivalent) on mount and pass it through to
  `listTransactions` as a filter. The backend already supports a `symbol`
  filter on `GET /api/v1/transactions` (`list_transactions_for_user`) — this
  is a frontend wiring change only, no backend change needed. Add a short
  inline hint near the transaction form for onboarding an existing position
  without full history (e.g. "Don't have your full trade history? Log a
  single buy for your current quantity and average cost — you can backdate
  it."). This is copy only; no new field, toggle, or schema change.
- `transactions-api.ts`: extend `listTransactions` to accept an optional
  `symbol` parameter and include it as a query string param.

### Docs

- `docs/implementation/m5.md`'s "Definition of Done" currently states "the
  existing holdings API still behaves per its contract
  (create/list/update/delete)... " — this line is rewritten to describe the
  new contract: holdings API is list/get only; all writes happen through
  Transactions.
- This work is inserted as a new **Step 6: Holdings/Transactions UX
  cleanup**, before the current Step 6 (Goal projection frontend). Steps
  formerly numbered 6-11 shift to 7-12.

## Testing

Backend:
- `tests/test_holdings_api.py`: remove create/edit/delete test cases; keep
  list/get coverage.
- Full backend suite run for regressions — confirm nothing else references
  the removed functions/schema (a codebase-wide grep prior to this design
  found no other callers).

Frontend:
- Update the Holdings page test file: remove form-submission assertions,
  add a case for the empty-state copy/link and the per-row "View
  transactions" link.
- Add a Transactions page test case verifying a `?symbol=` param filters the
  list via `listTransactions`.

Both full backend and frontend verification commands must remain green.
