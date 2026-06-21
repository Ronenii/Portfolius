# Allocation Units Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show summed owned units for instrument allocation rows and distinct instrument positions for broader allocation rows.

**Architecture:** Replace the ambiguous allocation-row lot count with `position_count` and optional `unit_quantity`. The allocation domain will aggregate instrument IDs and quantities while preserving existing market-value math; frontend tables, chart tooltips, simulations, and assistant summaries will consume the explicit fields.

**Tech Stack:** Python 3.11, FastAPI, Pydantic, pytest, React, TypeScript, Vitest, Testing Library, Recharts

---

### Task 1: Backend allocation contract and aggregation

**Files:**
- Modify: `backend/tests/test_allocation.py`
- Modify: `backend/tests/test_composition_api.py`
- Modify: `backend/app/schemas/portfolio.py`
- Modify: `backend/app/domain/allocation.py`

- [x] **Step 1: Write failing aggregation tests**

Add a regression test with three VOO lots whose quantities are `10`, `14`, and
`20`, plus a second ETF instrument. Assert that the VOO instrument row has
`unit_quantity == Decimal("44")` and `position_count == 1`, while the ETF asset
class row has `position_count == 2` and `unit_quantity is None`. Update the
response-shape assertion to require `position_count` and `unit_quantity` instead
of `holding_count`.

- [x] **Step 2: Run backend tests and verify RED**

Run from `backend/`:

```bash
source .venv/bin/activate
pytest tests/test_allocation.py tests/test_composition_api.py -q
```

Expected: FAIL because `AllocationRow` does not expose `position_count` or
`unit_quantity`.

- [x] **Step 3: Implement explicit row fields**

Change `AllocationRow` to:

```python
class AllocationRow(BaseModel):
    dimension: str
    label: str
    currency: str
    market_value: Decimal
    percent: Decimal
    position_count: int
    unit_quantity: Decimal | None = None

    @field_serializer("market_value", "percent", "unit_quantity")
    def serialize_decimal(self, value: Decimal | None) -> str | None:
        if value is None:
            return None
        return str(value)
```

In `build_dimension_rows`, group market value, a set of instrument IDs, and
quantity. Populate `position_count` from the set size and populate
`unit_quantity` only for the `instrument` dimension. In `build_currency_rows`,
track distinct instrument IDs and return `unit_quantity=None`.

- [x] **Step 4: Run backend tests and verify GREEN**

Run:

```bash
pytest tests/test_allocation.py tests/test_composition_api.py -q
```

Expected: all selected tests pass.

- [x] **Step 5: Commit backend contract**

```bash
git add backend/app/domain/allocation.py backend/app/schemas/portfolio.py \
  backend/tests/test_allocation.py backend/tests/test_composition_api.py
git commit -m "fix: distinguish allocation units from positions"
```

### Task 2: Backend contract consumers

**Files:**
- Modify: `backend/tests/test_assistant_context.py`
- Modify: `backend/app/domain/assistant.py`

- [x] **Step 1: Write failing assistant-context expectations**

Update allocation fixture rows to use:

```python
position_count=1,
unit_quantity=Decimal("44"),
```

Assert compact instrument rows contain `position_count: 1` and
`unit_quantity: "44"`; broader rows contain `position_count` and a null
`unit_quantity`.

- [x] **Step 2: Run assistant tests and verify RED**

Run:

```bash
pytest tests/test_assistant_context.py -q
```

Expected: FAIL while compact serialization still reads `row.holding_count`.

- [x] **Step 3: Update compact allocation serialization**

Replace the ambiguous field in the serialized row:

```python
"position_count": row.position_count,
"unit_quantity": (
    compact_decimal(row.unit_quantity) if row.unit_quantity is not None else None
),
```

Use the module's existing decimal-compaction convention.

- [x] **Step 4: Run assistant tests and verify GREEN**

Run:

```bash
pytest tests/test_assistant_context.py -q
```

Expected: all selected tests pass.

- [ ] **Step 5: Commit backend consumers**

```bash
git add backend/app/domain/assistant.py backend/tests/test_assistant_context.py
git commit -m "fix: expose allocation units to assistant context"
```

### Task 3: Frontend allocation display

**Files:**
- Modify: `frontend/src/pages/DashboardPage.test.tsx`
- Modify: `frontend/src/features/portfolio/portfolio-api.ts`
- Create: `frontend/src/features/portfolio/allocation-display.ts`
- Modify: `frontend/src/pages/DashboardPage.tsx`
- Modify: `frontend/src/components/charts/AllocationChart.tsx`
- Modify: `frontend/src/components/charts/AllocationDonut.tsx`

- [ ] **Step 1: Write failing dashboard tests**

Update breakdown fixtures to the new fields. Give the instrument row
`position_count: 1` and `unit_quantity: "44"`. Verify the default asset-class
view has a `Positions` heading and value `1`; after selecting Instrument, verify
the heading is `Units`, the value is `44`, and no allocation heading named
`Holdings` remains.

- [ ] **Step 2: Run dashboard tests and verify RED**

Run from `frontend/`:

```bash
npm run test -- src/pages/DashboardPage.test.tsx
```

Expected: FAIL because the table and chart tooltip still read `holding_count`.

- [ ] **Step 3: Implement frontend row semantics**

Change the TypeScript type to:

```typescript
export type AllocationRow = {
  dimension: string;
  label: string;
  currency: string;
  market_value: string;
  percent: string;
  position_count: number;
  unit_quantity: string | null;
};
```

Add helpers shared by the dashboard and charts:

```typescript
function formatQuantity(value: string | null) {
  const quantity = Number(value ?? 0);
  return new Intl.NumberFormat("en", {
    maximumFractionDigits: 12,
  }).format(Number.isFinite(quantity) ? quantity : 0);
}

export function allocationQuantityLabel(row: AllocationRow) {
  return row.dimension === "instrument" ? "Units" : "Positions";
}

export function allocationQuantityValue(row: AllocationRow) {
  return row.dimension === "instrument"
    ? formatQuantity(row.unit_quantity)
    : String(row.position_count);
}
```

Use locale formatting with a generous fractional-digit limit and no forced
trailing zeroes. Render the selected dimension's heading and value in the table,
and apply the same helpers in bar and donut tooltips.

- [ ] **Step 4: Run dashboard tests and verify GREEN**

Run:

```bash
npm run test -- src/pages/DashboardPage.test.tsx
```

Expected: all selected tests pass.

- [ ] **Step 5: Commit frontend display**

```bash
git add frontend/src/features/portfolio/portfolio-api.ts \
  frontend/src/features/portfolio/allocation-display.ts \
  frontend/src/pages/DashboardPage.tsx frontend/src/pages/DashboardPage.test.tsx \
  frontend/src/components/charts/AllocationChart.tsx \
  frontend/src/components/charts/AllocationDonut.tsx
git commit -m "fix: show units in instrument allocation"
```

### Task 4: Simulation fixtures and full verification

**Files:**
- Modify: `frontend/src/features/portfolio/simulation.test.tsx`

- [ ] **Step 1: Update remaining allocation fixtures**

Replace allocation-row `holding_count` values with `position_count` and
`unit_quantity`, using a quantity string only for instrument rows and `null`
elsewhere. Do not alter composition-row `holding_count`.

- [ ] **Step 2: Run targeted backend verification**

Run from `backend/`:

```bash
source .venv/bin/activate
ruff check .
pytest
```

Expected: lint clean and all backend tests pass.

- [ ] **Step 3: Run targeted frontend verification**

Run from `frontend/`:

```bash
npm run lint
npm run test
npm run build
```

Expected: lint clean, all Vitest tests pass, and TypeScript/Vite build succeeds.

- [ ] **Step 4: Review contract and diff**

Run from the repository root:

```bash
rg -n "holding_count" backend frontend --glob '!**/node_modules/**'
git diff --check
git status --short
```

Expected: remaining `holding_count` references belong only to holding CRUD,
composition rows, and unpriced holding counts; no whitespace errors; the
untracked `PR_DESCRIPTION.md` remains untouched.

- [ ] **Step 5: Commit verification updates**

```bash
git add frontend/src/features/portfolio/simulation.test.tsx
git add -u
git commit -m "test: verify allocation unit semantics"
```
