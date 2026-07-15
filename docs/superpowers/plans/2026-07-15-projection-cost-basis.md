# Projection Chart Cost-Basis Line Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a fourth "Cost basis" series to the goal projection chart, showing the portfolio's invested capital (today's cost basis plus projected future contributions, no market growth) alongside the existing conservative/expected/optimistic growth bands.

**Architecture:** The backend's pure projection math (`build_projection`) gains one new input (`start_cost_basis`) and computes a linear `cost_basis` value per year, returned as a new field on `ProjectionYearPoint`. The frontend's `ProjectionChart` renders it as a plain `Line` (not a filled `Area`), reusing the chart's existing band-toggle-chip mechanism so it gets a working show/hide chip "for free."

**Tech Stack:** FastAPI + Pydantic + `Decimal` (backend), React + TypeScript + Recharts `ComposedChart` (frontend), pytest / vitest + Testing Library.

## Global Constraints

- Cost basis grows linearly: `cost_basis = start_cost_basis + contribution_per_period * periods_per_year * year` — no compounding, no market growth.
- `start_cost_basis` defaults to `Decimal("0")` in `build_projection` so all 12 existing tests in `backend/tests/test_projection.py` keep passing unchanged.
- The cost-basis `Line`'s color must not collide with the target `ReferenceLine`'s color (`chartColors[3]`) — use `chartColors[4]`.
- The existing "refuse to hide the last visible band" toggle rule must cover all four bands, not just the original three.

---

### Task 1: Backend — cost-basis series data

**Files:**
- Modify: `backend/app/domain/projection.py`
- Modify: `backend/app/schemas/portfolio.py`
- Modify: `backend/app/domain/portfolio_service.py`
- Modify: `backend/tests/test_projection.py`

**Interfaces:**
- Consumes: nothing new — `snapshot.summary.total_cost_basis` (a `Decimal`, already computed by `build_snapshot_for_user`, which `build_projection_for_user` already calls).
- Produces: `build_projection(..., start_cost_basis: Decimal = Decimal("0"), ...)` and `ProjectionYearPoint.cost_basis: Decimal` (serialized to a `str` in JSON, matching `conservative`/`expected`/`optimistic`). Task 2's frontend type change depends on this JSON field being present and named `cost_basis`.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_projection.py` (after the last test, `test_series_covers_year_zero_through_years_inclusive`):

```python
def test_cost_basis_starts_at_start_cost_basis() -> None:
    response = build_projection(
        base_currency="USD",
        start_value=Decimal("10000"),
        start_cost_basis=Decimal("8000"),
        target=None,
        contribution=None,
        annual_return=Decimal("10"),
        years=2,
        frequency="annually",
    )

    points = series_by_year(response)
    assert points[0].cost_basis == Decimal("8000.00")


def test_cost_basis_accumulates_contributions_without_growth() -> None:
    response = build_projection(
        base_currency="USD",
        start_value=Decimal("10000"),
        start_cost_basis=Decimal("8000"),
        target=None,
        contribution=Decimal("1000"),
        annual_return=Decimal("10"),
        years=3,
        frequency="annually",
    )

    points = series_by_year(response)
    assert points[0].cost_basis == Decimal("8000.00")
    assert points[1].cost_basis == Decimal("9000.00")
    assert points[2].cost_basis == Decimal("10000.00")
    assert points[3].cost_basis == Decimal("11000.00")


def test_cost_basis_flat_when_no_contribution() -> None:
    response = build_projection(
        base_currency="USD",
        start_value=Decimal("10000"),
        start_cost_basis=Decimal("8000"),
        target=None,
        contribution=None,
        annual_return=Decimal("10"),
        years=2,
        frequency="annually",
    )

    points = series_by_year(response)
    assert (
        points[0].cost_basis
        == points[1].cost_basis
        == points[2].cost_basis
        == Decimal("8000.00")
    )


def test_cost_basis_defaults_to_zero_when_not_provided() -> None:
    response = build_projection(
        base_currency="USD",
        start_value=Decimal("10000"),
        target=None,
        contribution=Decimal("500"),
        annual_return=Decimal("10"),
        years=1,
        frequency="annually",
    )

    points = series_by_year(response)
    assert points[0].cost_basis == Decimal("0.00")
    assert points[1].cost_basis == Decimal("500.00")
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && pytest tests/test_projection.py -v`
Expected: FAIL — `TypeError: build_projection() got an unexpected keyword argument 'start_cost_basis'` (first two new tests pass it explicitly; the other two also fail once `ProjectionYearPoint` has no `cost_basis` attribute to read).

- [ ] **Step 3: Add `cost_basis` to the schema**

In `backend/app/schemas/portfolio.py`, find:

```python
class ProjectionYearPoint(BaseModel):
    year: int
    conservative: Decimal
    expected: Decimal
    optimistic: Decimal

    @field_serializer("conservative", "expected", "optimistic")
    def serialize_decimal(self, value: Decimal) -> str:
        return str(value)
```

Replace with:

```python
class ProjectionYearPoint(BaseModel):
    year: int
    conservative: Decimal
    expected: Decimal
    optimistic: Decimal
    cost_basis: Decimal

    @field_serializer("conservative", "expected", "optimistic", "cost_basis")
    def serialize_decimal(self, value: Decimal) -> str:
        return str(value)
```

- [ ] **Step 4: Compute `cost_basis` in `build_projection`**

In `backend/app/domain/projection.py`, find the function signature:

```python
def build_projection(
    *,
    base_currency: str,
    start_value: Decimal,
    target: Decimal | None,
    contribution: Decimal | None,
    annual_return: Decimal,
    years: int,
    frequency: str,
) -> ProjectionResponse:
```

Replace with:

```python
def build_projection(
    *,
    base_currency: str,
    start_value: Decimal,
    start_cost_basis: Decimal = Decimal("0"),
    target: Decimal | None,
    contribution: Decimal | None,
    annual_return: Decimal,
    years: int,
    frequency: str,
) -> ProjectionResponse:
```

Then find the per-year loop:

```python
    series: list[ProjectionYearPoint] = []
    expected_by_year: dict[int, Decimal] = {}
    for year in range(years + 1):
        n = periods_per_year * year
        conservative = _quantize(
            _future_value(
                start_value, contribution_per_period, conservative_rate, n
            )
        )
        expected = _quantize(
            _future_value(start_value, contribution_per_period, expected_rate, n)
        )
        optimistic = _quantize(
            _future_value(
                start_value, contribution_per_period, optimistic_rate, n
            )
        )
        expected_by_year[year] = expected
        series.append(
            ProjectionYearPoint(
                year=year,
                conservative=conservative,
                expected=expected,
                optimistic=optimistic,
            )
        )
```

Replace with:

```python
    series: list[ProjectionYearPoint] = []
    expected_by_year: dict[int, Decimal] = {}
    for year in range(years + 1):
        n = periods_per_year * year
        conservative = _quantize(
            _future_value(
                start_value, contribution_per_period, conservative_rate, n
            )
        )
        expected = _quantize(
            _future_value(start_value, contribution_per_period, expected_rate, n)
        )
        optimistic = _quantize(
            _future_value(
                start_value, contribution_per_period, optimistic_rate, n
            )
        )
        cost_basis = _quantize(
            start_cost_basis + contribution_per_period * periods_per_year * year
        )
        expected_by_year[year] = expected
        series.append(
            ProjectionYearPoint(
                year=year,
                conservative=conservative,
                expected=expected,
                optimistic=optimistic,
                cost_basis=cost_basis,
            )
        )
```

- [ ] **Step 5: Pass the portfolio's cost basis in from `build_projection_for_user`**

In `backend/app/domain/portfolio_service.py`, find:

```python
    return build_projection(
        base_currency=snapshot.summary.base_currency,
        start_value=snapshot.summary.total_market_value,
        target=resolved_target,
        contribution=resolved_contribution,
        annual_return=resolved_annual_return,
        years=resolved_years,
        frequency=profile.investment_frequency,
    )
```

Replace with:

```python
    return build_projection(
        base_currency=snapshot.summary.base_currency,
        start_value=snapshot.summary.total_market_value,
        start_cost_basis=snapshot.summary.total_cost_basis,
        target=resolved_target,
        contribution=resolved_contribution,
        annual_return=resolved_annual_return,
        years=resolved_years,
        frequency=profile.investment_frequency,
    )
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `cd backend && pytest tests/test_projection.py tests/test_projection_api.py -v`
Expected: PASS (16/16 in `test_projection.py`, all of `test_projection_api.py` unaffected).

- [ ] **Step 7: Run the full backend test suite and lint**

Run: `cd backend && pytest && ruff check .`
Expected: both clean/passing — this confirms no other test (e.g. any snapshot/route test asserting on the full `ProjectionResponse` JSON shape) broke from the new required `cost_basis` field.

- [ ] **Step 8: Commit**

```bash
git add backend/app/domain/projection.py backend/app/schemas/portfolio.py backend/app/domain/portfolio_service.py backend/tests/test_projection.py
git commit -m "feat: compute cost-basis series for the goal projection"
```

---

### Task 2: Frontend — render the cost-basis line and toggle chip

**Files:**
- Modify: `frontend/src/features/portfolio/portfolio-api.ts`
- Modify: `frontend/src/components/charts/ProjectionChart.tsx`
- Modify: `frontend/src/components/charts/ProjectionChart.test.tsx`
- Modify: `frontend/src/features/portfolio/projection.test.tsx`

**Interfaces:**
- Consumes: Task 1's JSON field `cost_basis` (a numeric string) on each projection series point.
- Produces: `ProjectionYearPoint` (frontend type) gains `cost_basis: string`. `ProjectionChart`'s `BandKey` union gains `"costBasis"`, and the chip labeled "Cost basis" is queryable via `screen.getByRole("button", { name: "Cost basis" })` — no other task depends on this, it's the end of the chain.

- [ ] **Step 1: Add `cost_basis` to the `ProjectionYearPoint` type**

In `frontend/src/features/portfolio/portfolio-api.ts`, find:

```ts
export type ProjectionYearPoint = {
  year: number;
  conservative: string;
  expected: string;
  optimistic: string;
};
```

Replace with:

```ts
export type ProjectionYearPoint = {
  year: number;
  conservative: string;
  expected: string;
  optimistic: string;
  cost_basis: string;
};
```

- [ ] **Step 2: Update existing test fixtures to satisfy the new required field**

In `frontend/src/features/portfolio/projection.test.tsx`, find:

```tsx
  series: [
    { year: 0, conservative: "10000", expected: "10000", optimistic: "10000" },
    { year: 1, conservative: "11000", expected: "11600", optimistic: "12200" },
  ],
```

Replace with:

```tsx
  series: [
    {
      year: 0,
      conservative: "10000",
      expected: "10000",
      optimistic: "10000",
      cost_basis: "9000",
    },
    {
      year: 1,
      conservative: "11000",
      expected: "11600",
      optimistic: "12200",
      cost_basis: "9500",
    },
  ],
```

(`portfolio.test.tsx`'s two projection fixtures use `series: []` and need no change.)

- [ ] **Step 3: Write the failing chart tests**

In `frontend/src/components/charts/ProjectionChart.test.tsx`, find the `series` fixture:

```tsx
const series: ProjectionYearPoint[] = [
  { year: 0, conservative: "10000", expected: "10000", optimistic: "10000" },
  { year: 1, conservative: "10800", expected: "11000", optimistic: "11200" },
];
```

Replace with:

```tsx
const series: ProjectionYearPoint[] = [
  {
    year: 0,
    conservative: "10000",
    expected: "10000",
    optimistic: "10000",
    cost_basis: "8000",
  },
  {
    year: 1,
    conservative: "10800",
    expected: "11000",
    optimistic: "11200",
    cost_basis: "9000",
  },
];
```

Find the "renders a toggle chip for each band" test:

```tsx
  it("renders a toggle chip for each band, all pressed by default", () => {
    renderChart();

    expect(
      screen.getByRole("button", { name: "Conservative" })
    ).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "Expected" })).toHaveAttribute(
      "aria-pressed",
      "true"
    );
    expect(
      screen.getByRole("button", { name: "Optimistic" })
    ).toHaveAttribute("aria-pressed", "true");
  });
```

Replace with:

```tsx
  it("renders a toggle chip for each band, all pressed by default", () => {
    renderChart();

    expect(
      screen.getByRole("button", { name: "Conservative" })
    ).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "Expected" })).toHaveAttribute(
      "aria-pressed",
      "true"
    );
    expect(
      screen.getByRole("button", { name: "Optimistic" })
    ).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "Cost basis" })).toHaveAttribute(
      "aria-pressed",
      "true"
    );
  });

  it("toggles the cost-basis chip off when clicked", async () => {
    renderChart();

    await userEvent.click(screen.getByRole("button", { name: "Cost basis" }));

    expect(screen.getByRole("button", { name: "Cost basis" })).toHaveAttribute(
      "aria-pressed",
      "false"
    );
  });
```

Find the "refuses to hide the last visible band" test:

```tsx
  it("refuses to hide the last visible band", async () => {
    renderChart();

    await userEvent.click(screen.getByRole("button", { name: "Conservative" }));
    await userEvent.click(screen.getByRole("button", { name: "Expected" }));

    expect(screen.getByRole("button", { name: "Optimistic" })).toBeDisabled();

    await userEvent.click(screen.getByRole("button", { name: "Optimistic" }));
    expect(
      screen.getByRole("button", { name: "Optimistic" })
    ).toHaveAttribute("aria-pressed", "true");
  });
```

Replace with (now hides 3 of the 4 bands before checking the 4th, and adds a second case ending on Cost basis specifically):

```tsx
  it("refuses to hide the last visible band", async () => {
    renderChart();

    await userEvent.click(screen.getByRole("button", { name: "Conservative" }));
    await userEvent.click(screen.getByRole("button", { name: "Expected" }));
    await userEvent.click(screen.getByRole("button", { name: "Cost basis" }));

    expect(screen.getByRole("button", { name: "Optimistic" })).toBeDisabled();

    await userEvent.click(screen.getByRole("button", { name: "Optimistic" }));
    expect(
      screen.getByRole("button", { name: "Optimistic" })
    ).toHaveAttribute("aria-pressed", "true");
  });

  it("refuses to hide the last visible band, even when it's cost basis", async () => {
    renderChart();

    await userEvent.click(screen.getByRole("button", { name: "Conservative" }));
    await userEvent.click(screen.getByRole("button", { name: "Expected" }));
    await userEvent.click(screen.getByRole("button", { name: "Optimistic" }));

    expect(screen.getByRole("button", { name: "Cost basis" })).toBeDisabled();

    await userEvent.click(screen.getByRole("button", { name: "Cost basis" }));
    expect(screen.getByRole("button", { name: "Cost basis" })).toHaveAttribute(
      "aria-pressed",
      "true"
    );
  });
```

- [ ] **Step 4: Run the tests to verify they fail**

Run: `cd frontend && npm test -- ProjectionChart -v`
Expected: FAIL — no button named "Cost basis" exists yet.

- [ ] **Step 5: Read the current file**

Read `frontend/src/components/charts/ProjectionChart.tsx` in full before editing — the steps below are targeted diffs against its current content, not the whole file.

- [ ] **Step 6: Update the Recharts import**

Find:

```tsx
import {
  Area,
  AreaChart,
  ReferenceDot,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
```

Replace with:

```tsx
import {
  Area,
  ComposedChart,
  Line,
  ReferenceDot,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
```

- [ ] **Step 7: Add the `costBasis` band and a color map**

Find:

```tsx
type BandKey = "conservative" | "expected" | "optimistic";

const BAND_KEYS: BandKey[] = ["conservative", "expected", "optimistic"];

const BAND_LABELS: Record<BandKey, string> = {
  conservative: "Conservative",
  expected: "Expected",
  optimistic: "Optimistic",
};
```

Replace with:

```tsx
type BandKey = "conservative" | "expected" | "optimistic" | "costBasis";

const BAND_KEYS: BandKey[] = [
  "conservative",
  "expected",
  "optimistic",
  "costBasis",
];

const BAND_LABELS: Record<BandKey, string> = {
  conservative: "Conservative",
  expected: "Expected",
  optimistic: "Optimistic",
  costBasis: "Cost basis",
};

// chartColors[3] is reserved for the target ReferenceLine (below) - band
// colors are looked up explicitly here rather than positionally by index so
// the two can never collide.
const BAND_COLORS: Record<BandKey, string> = {
  conservative: chartColors[0],
  expected: chartColors[1],
  optimistic: chartColors[2],
  costBasis: chartColors[4],
};
```

- [ ] **Step 8: Add `numericCostBasis` to `chartRows`**

Find:

```tsx
  const chartRows = series.map((point) => ({
    ...point,
    numericConservative: Number(point.conservative),
    numericExpected: Number(point.expected),
    numericOptimistic: Number(point.optimistic),
  }));
```

Replace with:

```tsx
  const chartRows = series.map((point) => ({
    ...point,
    numericConservative: Number(point.conservative),
    numericExpected: Number(point.expected),
    numericOptimistic: Number(point.optimistic),
    numericCostBasis: Number(point.cost_basis),
  }));
```

- [ ] **Step 9: Switch the chart root from `AreaChart` to `ComposedChart`**

Find:

```tsx
      <div className="projection-chart" role="img" aria-label="Goal projection chart">
        <ResponsiveContainer width="100%" height={260}>
        <AreaChart
          data={chartRows}
          margin={{ bottom: 4, left: 8, right: 12, top: 4 }}
        >
```

Replace with:

```tsx
      <div className="projection-chart" role="img" aria-label="Goal projection chart">
        <ResponsiveContainer width="100%" height={260}>
        <ComposedChart
          data={chartRows}
          margin={{ bottom: 4, left: 8, right: 12, top: 4 }}
        >
```

Find the closing tag:

```tsx
        </AreaChart>
        </ResponsiveContainer>
      </div>
```

Replace with:

```tsx
        </ComposedChart>
        </ResponsiveContainer>
      </div>
```

- [ ] **Step 10: Add the cost-basis tooltip row**

Find:

```tsx
                    <div>
                      <dt>Optimistic</dt>
                      <dd>{formatValue(row.optimistic, currency)}</dd>
                    </div>
                  </dl>
```

Replace with:

```tsx
                    <div>
                      <dt>Optimistic</dt>
                      <dd>{formatValue(row.optimistic, currency)}</dd>
                    </div>
                    <div>
                      <dt>Cost basis</dt>
                      <dd>{formatValue(row.cost_basis, currency)}</dd>
                    </div>
                  </dl>
```

- [ ] **Step 11: Add the cost-basis `Line`**

Find the third `Area` element followed by the target `ReferenceLine`:

```tsx
          <Area
            dataKey="numericOptimistic"
            fill={chartColors[2]}
            fillOpacity={0.15}
            stroke={chartColors[2]}
            type="monotone"
            hide={hiddenBands.has("optimistic")}
            isAnimationActive={animationsEnabled}
            animationDuration={800}
            animationEasing="ease-out"
          />
          {numericTarget != null && (
```

Replace with:

```tsx
          <Area
            dataKey="numericOptimistic"
            fill={chartColors[2]}
            fillOpacity={0.15}
            stroke={chartColors[2]}
            type="monotone"
            hide={hiddenBands.has("optimistic")}
            isAnimationActive={animationsEnabled}
            animationDuration={800}
            animationEasing="ease-out"
          />
          <Line
            dataKey="numericCostBasis"
            dot={false}
            hide={hiddenBands.has("costBasis")}
            stroke={BAND_COLORS.costBasis}
            strokeDasharray="2 2"
            strokeWidth={2}
            type="monotone"
            isAnimationActive={animationsEnabled}
            animationDuration={800}
            animationEasing="ease-out"
          />
          {numericTarget != null && (
```

- [ ] **Step 12: Point the toggle-chip swatch color at `BAND_COLORS`**

Find:

```tsx
        {BAND_KEYS.map((band, index) => {
          const isVisible = !hiddenBands.has(band);
          return (
            <button
              key={band}
              type="button"
              className={
                isVisible
                  ? "projection-band-toggle"
                  : "projection-band-toggle projection-band-toggle--muted"
              }
              aria-pressed={isVisible}
              disabled={isVisible && visibleCount === 1}
              onClick={() => toggleBand(band)}
            >
              <span
                aria-hidden="true"
                className="projection-band-swatch"
                style={{ backgroundColor: chartColors[index] }}
              />
              {BAND_LABELS[band]}
            </button>
          );
        })}
```

Replace with (drops the now-unused `index` param — the color no longer comes from position):

```tsx
        {BAND_KEYS.map((band) => {
          const isVisible = !hiddenBands.has(band);
          return (
            <button
              key={band}
              type="button"
              className={
                isVisible
                  ? "projection-band-toggle"
                  : "projection-band-toggle projection-band-toggle--muted"
              }
              aria-pressed={isVisible}
              disabled={isVisible && visibleCount === 1}
              onClick={() => toggleBand(band)}
            >
              <span
                aria-hidden="true"
                className="projection-band-swatch"
                style={{ backgroundColor: BAND_COLORS[band] }}
              />
              {BAND_LABELS[band]}
            </button>
          );
        })}
```

- [ ] **Step 13: Run the tests to verify they pass**

Run: `cd frontend && npm test -- ProjectionChart projection -v`
Expected: PASS — all `ProjectionChart.test.tsx` tests (7 total: the original 5 plus the 2 new ones from Step 3, with the "refuses to hide" test now covering 2 cases) and all `projection.test.tsx` (`ProjectionPanel`) tests.

- [ ] **Step 14: Run the full frontend test suite, lint, and type-check**

Run: `cd frontend && npm test && npm run lint && npm run build`
Expected: all clean/passing — `npm run build` runs `tsc -b`, which catches any remaining place a `ProjectionYearPoint` literal is missing the new required `cost_basis` field.

- [ ] **Step 15: Commit**

```bash
git add frontend/src/features/portfolio/portfolio-api.ts frontend/src/components/charts/ProjectionChart.tsx frontend/src/components/charts/ProjectionChart.test.tsx frontend/src/features/portfolio/projection.test.tsx
git commit -m "feat: render a cost-basis line and toggle chip on the projection chart"
```
