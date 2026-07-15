# Interactive Goal Projection Chart Controls Design

## Goal

Make the goal-projection chart (`ProjectionPanel`/`ProjectionChart`, shipped
in M5 Step 7) customizable and more engaging: pick the projection horizon,
show/hide individual growth bands, explore "what if I contributed more / got
a better return" scenarios live, and see a clear, animated signal of whether
and when the goal is reached.

## Problem

The current `ProjectionChart` renders one fixed view: whatever horizon,
contribution, and return the profile resolves to, with all three bands
always shown, no animation, and no way to explore alternatives without
editing the profile form and reloading. Users asked for more control over
the timeframe, the ability to focus on one band at a time, and a more
engaging way to see progress toward their goal.

## Architecture Decision: how what-if changes reach the chart

`GET /api/v1/portfolio/projection` already accepts optional `years`,
`contribution`, and `annual_return` query overrides (`api/v1/portfolio.py`,
`read_portfolio_projection` -> `build_projection_for_user`), backed by the
pure `domain/projection.py::build_projection`. This feature reuses that
endpoint as-is — **no backend changes** — by having the frontend send
debounced override requests instead of computing projections client-side.

Rejected alternative: porting `build_projection`'s compounding math to
TypeScript for zero-latency slider feedback. This would duplicate the
periodic-rate formula, the `BAND_SPREAD_PERCENT` constant, and the
risk-tolerance default-return table in two languages — a direct violation of
this codebase's stated principle that the backend is the single source of
truth for portfolio math (`docs/implementation/m5.md`'s Architecture
section). A few hundred milliseconds of debounce latency on a slider drag is
an acceptable trade-off to avoid that drift risk.

## Behavior

### Horizon selector

A segmented control with fixed options `3 / 5 / 10 / 15 / 20 / 30` years.
Clicking an option immediately refetches the projection with that `years`
override. The option matching the horizon from the initial (no-override)
fetch is marked active by default.

### What-if sliders

Two range inputs, each paired with a live numeric readout:

- **Contribution amount** — range `0` to `max(seededContribution * 4, 1000)`
  in the profile's base currency, so the scale adapts to the user's own
  numbers instead of one fixed range for everyone. Step `10`.
- **Expected annual return** — range `-5` to `20` (percent), step `0.5`.

Both start at the values from the initial no-override fetch
(`data.contribution_amount`, `data.annual_return_expected`). Dragging a
slider updates its own displayed value immediately (no lag on the thumb),
but the value that reaches the network is debounced by ~350ms of no further
movement — implemented as a "draft" state (updates on every `onChange`) and
a "committed" state (updates via a `useEffect`-driven timer watching the
draft, reset on every change), with the committed values feeding the
query key/args. This is a local pattern, not a new shared hook — consistent
with this codebase not having a debounce utility today.

While a debounced refetch is in flight (`isFetching && !isLoading`), an
inline "Updating…" label appears next to the chart so the delay doesn't read
as unresponsive.

### Reset control

A text-button, "Reset to my profile values", rendered only when at least one
override (horizon, contribution, or return) differs from the seeded
initial values. Clicking clears all override/draft state, reverting the
query to the original no-override fetch and re-seeding displayed values from
its response.

### Band visibility toggles

Three small clickable chips below the chart — Conservative / Expected /
Optimistic — each with that band's color swatch. Clicking toggles that
band's `Area` on/off. This is pure client-side view state inside
`ProjectionChart` (a `Set` of visible band keys); it never triggers a
network request. At least one band must stay visible: clicking the last
active chip is a no-op. Default: all three visible.

### Milestone marker

When the response has `on_track: true` and `target_reached_year` falls
within the currently-displayed series, render a `ReferenceDot` at that point
— a small filled circle with a checkmark and a "Target reached" label.
Understated by design (no confetti/celebration animation, no new
dependency), per product decision during design review.

### Draw-in animation

The three `Area` series animate in on data change (Recharts'
`isAnimationActive`/`animationDuration` ~800ms, ease-out), gated off when
`window.matchMedia("(prefers-reduced-motion: reduce)").matches` — the same
per-component `prefersReducedMotion()` check `TrendLoader` already uses
locally (this codebase duplicates that check per component rather than
sharing a hook; this feature follows the existing convention rather than
introducing a new one).

## Non-Goals (explicitly out of scope)

- Saving what-if slider values back to the profile. Sliders are purely
  exploratory/ephemeral; a "Reset" clears them, nothing here writes to
  `PUT /api/v1/profile`.
- A chart-type switcher (area/line/bar).
- Confetti or other celebration effects.
- Zoom/pan into a sub-range of years (the horizon selector covers "choose a
  timeframe" instead).
- Comparing two different what-if scenarios side by side.

## Architecture

### Frontend only — no backend changes

`backend/app/domain/projection.py` and
`backend/app/api/v1/portfolio.py::read_portfolio_projection` are unchanged;
their existing `years`/`contribution`/`annual_return` query overrides are
sufficient.

### `frontend/src/features/portfolio/ProjectionPanel.tsx`

- New local state: `years: number | null`, `contributionDraft`/`contribution:
  string | null`, `annualReturnDraft`/`annualReturn: string | null`.
- Query becomes `useQuery({ queryKey: ["portfolio-projection", accessToken,
  years, contribution, annualReturn], queryFn: () => getProjection(accessToken,
  overridesFrom(years, contribution, annualReturn)) })`, where `overridesFrom`
  omits any key that's still `null` (so the very first render — all null —
  behaves exactly as it does today).
- A ref-guarded effect seeds `years`/`contribution`/`annualReturn`'s
  *displayed* values (not the override state itself, which stays `null`
  until the user actually moves a control) from the first successful
  response's `horizon_years`/`contribution_amount`/`annual_return_expected`.
- Renders (only in the existing "data" branch, alongside the current chart/
  progress-bar/verdict — loading/404/generic-error/empty-goal states are
  unchanged): the horizon segmented control, the two what-if sliders with
  readouts, the "Updating…" label, and the "Reset" button.
- Passes two new props to `ProjectionChart` alongside the existing
  `currency`/`formatValue`/`series`/`targetAmount`: `onTrack: boolean | null`
  and `targetReachedYear: number | null` (straight from the response), so
  the chart can render the milestone marker itself.

### `frontend/src/components/charts/ProjectionChart.tsx`

- New local state: `hiddenBands: Set<"conservative" | "expected" |
  "optimistic">`, default empty (all visible).
- New band-toggle legend row (three chips) below the chart, wired to that
  state; refuses to hide the last visible band.
- Each `Area`'s `hide` prop (or conditional render) driven by
  `hiddenBands.has(bandKey)`.
- `isAnimationActive`/`animationDuration` on each `Area`, computed once from
  a local `prefersReducedMotion()` check (mirroring `TrendLoader`).
- A `ReferenceDot` rendered conditionally when the milestone conditions
  (above) are met.

### CSS (`frontend/src/index.css`)

New rules for the band-toggle chips (reusing `.segmented-button`-style
conventions already established for other toggle UIs in this app, plus
per-band color swatches), the horizon segmented control (reuses the
existing `.segmented-control`/`.segmented-button` classes as-is — no new
CSS needed there), the slider inputs (native `<input type="range">` styled
minimally to match the app's `--accent-500`/`--rule` tokens, with
`.mode-terminal` overrides), and the milestone marker's label styling. All
new rules follow the existing pattern: base styles plus a `.mode-terminal`
override block, reusing existing design tokens — no new tokens introduced.

## Testing

Backend: no changes, no new tests needed (existing `test_projection_api.py`
already covers the `years`/`contribution`/`annual_return` overrides this
feature relies on).

Frontend:
- `ProjectionPanel`: clicking a horizon option refetches with the right
  `years` override; dragging a slider (simulate via `fireEvent.change` +
  `vi.useFakeTimers()`/`vi.advanceTimersByTime` past the debounce window)
  triggers a refetch with the right `contribution`/`annual_return` override;
  "Reset" clears all overrides and reverts to the original (no-override)
  query; the "Updating…" label appears during a background refetch
  (`isFetching`) and not during the initial load (`isLoading`).
- `ProjectionChart`: clicking a band chip hides that series (assert via the
  chip's pressed/active state and/or the chart's accessible structure, not
  Recharts' internal SVG); the last remaining active chip cannot be toggled
  off; the milestone `ReferenceDot` renders only when `on_track` is true and
  `target_reached_year` is within the displayed series, and does not render
  otherwise; the animation props reflect the mocked
  `prefers-reduced-motion` media query state (this test setup already
  stubs `matchMedia`, see `frontend/src/test/setup.ts`).

Both full backend and frontend verification commands (`pytest`, `npm test`,
`npm run lint`, `npm run build`) must remain green.
