# Projection Chart Cost-Basis Line — Design Spec

**M5 Step 7a.** Show the portfolio's cost basis (invested capital) alongside
the goal projection so users can see how much of the projected value is
money they put in versus investment growth — not just the growth curve.

## Architecture

The cost-basis line is a fourth data series computed by the existing pure
projection math (`backend/app/domain/projection.py`), returned as an
additional field on each `ProjectionYearPoint`, and rendered on the existing
`ProjectionChart` as a plain `Line` (not a filled `Area`) with its own toggle
chip. No new endpoints, no new queries, no schema versioning — this is
additive to the existing `GET /portfolio/projection` response.

## A. Backend: cost-basis series data

- `build_projection` (`backend/app/domain/projection.py`) gains a new
  optional parameter `start_cost_basis: Decimal = Decimal("0")`.
- `build_projection_for_user` (`backend/app/domain/portfolio_service.py`)
  passes `snapshot.summary.total_cost_basis` as `start_cost_basis` — this
  value is already computed by `build_snapshot_for_user`, which
  `build_projection_for_user` already calls; no new query is introduced.
- `ProjectionYearPoint` (`backend/app/schemas/portfolio.py`) gains a new
  required field `cost_basis: Decimal`.
- For each year `year` in `range(years + 1)`, `cost_basis` is computed as:

  ```python
  cost_basis = _quantize(
      start_cost_basis + contribution_per_period * periods_per_year * year
  )
  ```

  This is pure linear accumulation of contributions on top of the starting
  cost basis — no market growth or compounding is assumed, since cost basis
  represents money put in, not money it grew into. It automatically respects
  the same `contribution`/`years` overrides the rest of the series already
  respects, since it's computed inside the same function using the already
  -resolved `contribution_per_period`, `periods_per_year`, and loop.
- When `contribution_per_period` is `0` (the existing default when no
  contribution is set/overridden), `cost_basis` stays flat at
  `start_cost_basis` for every year — expected behavior, not a special case.

## B. Frontend: rendering the cost-basis line

`frontend/src/features/portfolio/portfolio-api.ts`:
- `ProjectionYearPoint` type gains `cost_basis: string` (matches the existing
  string-typed money fields on this type).

`frontend/src/components/charts/ProjectionChart.tsx`:
- The root chart switches from Recharts' `AreaChart` to `ComposedChart` (the
  supported way to mix `Area` and `Line` series in one chart) — the import
  changes from `AreaChart` to `ComposedChart` and `Line` is added to the
  Recharts import. The three existing `Area` elements
  (conservative/expected/optimistic) are otherwise unchanged.
- `chartRows` gains `numericCostBasis: Number(point.cost_basis)`, alongside
  the three existing `numeric*` fields.
- `BandKey` becomes `"conservative" | "expected" | "optimistic" | "costBasis"`
  and `BAND_KEYS`/`BAND_LABELS` gain the fourth entry (label `"Cost basis"`).
  This means the existing toggle-chip row, the existing
  "refuse to hide the last visible band" rule in `toggleBand`, and the
  existing chip-rendering `.map(BAND_KEYS...)` all cover the new band with no
  new logic — only the data extends.
- Because the swatch/line color for each chip is currently looked up
  positionally as `chartColors[index]` (index 0/1/2 for the three growth
  bands), and `chartColors[3]` is already used by the `target` `ReferenceLine`,
  a plain 4th positional lookup would collide colors between "Cost basis" and
  "Target". The lookup changes from positional (`chartColors[index]`) to an
  explicit map:

  ```tsx
  const BAND_COLORS: Record<BandKey, string> = {
    conservative: chartColors[0],
    expected: chartColors[1],
    optimistic: chartColors[2],
    costBasis: chartColors[4],
  };
  ```

  Both the toggle-chip swatch and the new `Line`'s `stroke` read from
  `BAND_COLORS[band]` / `BAND_COLORS.costBasis` instead of `chartColors[index]`.
- New chart element, placed after the three `Area`s and before the `target`
  `ReferenceLine`:

  ```tsx
  <Line
    dataKey="numericCostBasis"
    stroke={BAND_COLORS.costBasis}
    strokeDasharray="2 2"
    strokeWidth={2}
    dot={false}
    type="monotone"
    hide={hiddenBands.has("costBasis")}
    isAnimationActive={animationsEnabled}
    animationDuration={800}
    animationEasing="ease-out"
  />
  ```

  `strokeDasharray="2 2"` (tighter dashes than the target line's `"4 4"`) and
  no fill keep it visually distinct from both the filled growth bands and the
  dashed target reference line.
- The tooltip content function gains a fourth row, placed after Optimistic:

  ```tsx
  <div>
    <dt>Cost basis</dt>
    <dd>{formatValue(row.cost_basis, currency)}</dd>
  </div>
  ```

## C. Testing

**Backend** (`backend/tests/test_projection.py`, extending the existing pure
-function test suite for `build_projection`):
- `cost_basis` starts at `start_cost_basis` in year 0.
- `cost_basis` increases by exactly `contribution_per_period *
  periods_per_year` per year (annual frequency case, for simple arithmetic).
- `cost_basis` stays flat across all years when `contribution` is `None`
  (uses the existing zero-contribution default).
- `cost_basis` reflects overridden `years`/`contribution` values (already
  covered implicitly by being computed from the same resolved values as the
  rest of the series, but assert it explicitly for one case).
- Existing 12 tests in this file are unaffected, since `start_cost_basis`
  defaults to `Decimal("0")` and none of them assert on `cost_basis`.

**Frontend** (`frontend/src/components/charts/ProjectionChart.tsx`, extending
the existing test file):
- A fourth "Cost basis" toggle chip renders pressed by default alongside the
  existing three.
- Clicking "Cost basis" hides it (`aria-pressed="false"`).
- The "refuse to hide the last visible band" rule extends to 4 bands: hiding
  three of the four disables the fourth remaining chip, regardless of which
  three (extend the existing single-combination test to also cover ending on
  "Cost basis" as the last visible one, not just "Optimistic").

## Out of scope

- Adding cost basis to the `ReferenceDot` milestone marker — that marker
  specifically marks reaching the *target*, unrelated to cost basis.
- Any change to the `/portfolio` snapshot endpoint or the existing
  `total_cost_basis` display on `DashboardPage` — this is additive only to
  the projection response.
- Step 7b (auto-computed expected annual return) — separate step, separate
  spec.
