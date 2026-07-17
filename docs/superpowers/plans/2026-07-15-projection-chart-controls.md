# Interactive Goal Projection Chart Controls Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the M5 goal-projection chart customizable: a projection-horizon selector, band show/hide toggles, live what-if sliders for contribution and expected return, a milestone marker for the year the target is reached, and a subtle draw-in animation.

**Architecture:** All data-shape changes reuse the existing `GET /api/v1/portfolio/projection` query overrides (`years`/`contribution`/`annual_return`) already implemented in `backend/app/domain/projection.py` and `frontend/src/features/portfolio/portfolio-api.ts::getProjection` — no backend changes. `ProjectionPanel` gains override state (debounced for the two sliders) that feeds the query key; `ProjectionChart` gains purely client-side band-visibility state plus two new required props (`onTrack`, `targetReachedYear`) for the milestone marker.

**Tech Stack:** React, TypeScript, TanStack Query, Recharts (`^3.8.1`), Vitest, Testing Library.

## Global Constraints

- No backend changes — `years`/`contribution`/`annual_return` query overrides already exist and are tested (`test_projection_api.py`).
- What-if sliders are purely exploratory/ephemeral — nothing here writes to `PUT /api/v1/profile`.
- No new npm dependencies.
- Debounce window for both sliders: `350` ms.
- Horizon options: exactly `[3, 5, 10, 15, 20, 30]` years.
- Contribution slider range: `0` to `Math.max(Number(currentContribution) * 4, 1000)`.
- Annual return slider range: `-5` to `20` (percent), step `0.5`.
- Band toggles must never allow all three bands to be hidden at once (the last visible band's chip is `disabled`).
- Milestone marker only when `onTrack === true` and `targetReachedYear` matches a year present in the rendered series.
- Animation (`isAnimationActive`) is `false` whenever
  `window.matchMedia("(prefers-reduced-motion: reduce)").matches` is `true`
  — mirror `TrendLoader`'s local `prefersReducedMotion()` helper
  (`frontend/src/components/ui/TrendLoader.tsx:14-17`) rather than sharing a
  hook (this codebase duplicates this exact check per-component).
- All new CSS follows the existing convention: base rule + a
  `.mode-terminal` override block, reusing existing design tokens from
  `frontend/src/index.css`'s `:root` block — no new tokens.
- `frontend/src/test/setup.ts` stubs `window.matchMedia` so
  `prefers-reduced-motion: reduce` reports `true` by default in every test —
  this is why Task 2's reduced-motion test must explicitly override the stub
  to test the "motion allowed" path.

---

## File Structure

```text
frontend/src/
├── components/charts/
│   ├── ProjectionChart.tsx        (modify: band toggles, milestone, animation)
│   └── ProjectionChart.test.tsx   (new)
├── features/portfolio/
│   ├── ProjectionPanel.tsx        (modify: horizon selector, sliders, reset)
│   └── projection.test.tsx        (modify: new test cases appended)
└── index.css                      (modify: new rules appended after the
                                     existing .mode-terminal .projection-tooltip
                                     block)
```

No backend files change in this plan.

---

## Task 1: Band visibility toggles (`ProjectionChart`)

**Files:**
- Modify: `frontend/src/components/charts/ProjectionChart.tsx`
- Create: `frontend/src/components/charts/ProjectionChart.test.tsx`
- Modify: `frontend/src/index.css`

**Interfaces:**
- Consumes: nothing new — `ProjectionChart`'s existing props
  (`currency`, `formatValue`, `series`, `targetAmount`) are unchanged in this
  task.
- Produces: `ProjectionChart` now returns a new outer wrapper
  `<div className="projection-chart-wrap">` containing the existing
  `role="img"` chart div as one child and a new
  `<div className="projection-band-toggles" role="group" aria-label="Toggle projection bands">`
  as a sibling. Task 2 will add more children inside `projection-chart-wrap`
  (the milestone marker lives inside the chart itself, not this wrapper) and
  Task 3+ do not touch this file at all. The three accessible toggle buttons
  are named exactly `"Conservative"`, `"Expected"`, `"Optimistic"` (their
  visible text) — later tasks/tests must use these exact names if they ever
  query this component (none currently do).

This task also fixes a pre-existing accessibility issue: interactive
elements must never live inside a `role="img"` container (assistive tech
treats everything under `role="img"` as a single flattened image, making
nested buttons unreachable). The band-toggle buttons therefore go
**outside** the `role="img"` div, as a sibling under a new wrapper.

- [ ] **Step 1: Read the current file**

Read `frontend/src/components/charts/ProjectionChart.tsx` in full before
editing — you need its exact current content to edit precisely; the plan
below shows targeted diffs, not the whole file.

- [ ] **Step 2: Write the failing tests**

Create `frontend/src/components/charts/ProjectionChart.test.tsx`:

```tsx
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";

import type { ProjectionYearPoint } from "../../features/portfolio/portfolio-api";
import { ProjectionChart } from "./ProjectionChart";

const series: ProjectionYearPoint[] = [
  { year: 0, conservative: "10000", expected: "10000", optimistic: "10000" },
  { year: 1, conservative: "10800", expected: "11000", optimistic: "11200" },
];

function formatValue(value: string, currency: string) {
  return `${currency} ${value}`;
}

function renderChart() {
  return render(
    <ProjectionChart
      currency="USD"
      formatValue={formatValue}
      series={series}
      targetAmount={null}
    />
  );
}

describe("ProjectionChart", () => {
  afterEach(() => {
    cleanup();
  });

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

  it("toggles a band off when its chip is clicked", async () => {
    renderChart();

    await userEvent.click(screen.getByRole("button", { name: "Conservative" }));

    expect(
      screen.getByRole("button", { name: "Conservative" })
    ).toHaveAttribute("aria-pressed", "false");
  });

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

  it("puts the band toggles outside the role=img chart element", () => {
    renderChart();

    const chart = screen.getByRole("img", { name: "Goal projection chart" });
    const toggles = screen.getByRole("group", {
      name: "Toggle projection bands",
    });

    expect(chart.contains(toggles)).toBe(false);
  });
});
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `cd frontend && npm test -- ProjectionChart -v`
Expected: FAIL — `screen.getByRole("button", { name: "Conservative" })` finds
no matching element (no toggle buttons exist yet).

- [ ] **Step 4: Implement band toggles**

In `frontend/src/components/charts/ProjectionChart.tsx`:

Add `useState` to the React import (there is currently no React import at
all in this file — add one):

```tsx
import { useState } from "react";
```

Add two new type/const declarations right after the existing `chartColors`
line:

```tsx
type BandKey = "conservative" | "expected" | "optimistic";

const BAND_KEYS: BandKey[] = ["conservative", "expected", "optimistic"];

const BAND_LABELS: Record<BandKey, string> = {
  conservative: "Conservative",
  expected: "Expected",
  optimistic: "Optimistic",
};
```

`ProjectionChartProps` is unchanged in this task (Task 2 adds the two
milestone-related props) — leave the existing type and function signature
exactly as they are.

Right after the existing `const numericTarget = ...` line, add the toggle
state and a small derived count:

```tsx
  const [hiddenBands, setHiddenBands] = useState<Set<BandKey>>(
    () => new Set()
  );
  const visibleCount = BAND_KEYS.length - hiddenBands.size;

  function toggleBand(band: BandKey) {
    setHiddenBands((current) => {
      if (!current.has(band) && visibleCount <= 1) {
        return current;
      }
      const next = new Set(current);
      if (next.has(band)) {
        next.delete(band);
      } else {
        next.add(band);
      }
      return next;
    });
  }
```

Change the returned JSX. The current return starts with:

```tsx
    <div className="projection-chart" role="img" aria-label="Goal projection chart">
      <ResponsiveContainer width="100%" height={260}>
```

and ends with:

```tsx
      </ResponsiveContainer>
    </div>
  );
}
```

Replace both the opening and closing so the `role="img"` div is nested one
level inside a new wrapper, with the toggle row as its sibling — i.e. the
new structure is:

```tsx
  return (
    <div className="projection-chart-wrap">
      <div className="projection-chart" role="img" aria-label="Goal projection chart">
        <ResponsiveContainer width="100%" height={260}>
```

... (all existing `<AreaChart>` content stays exactly as-is, except each of
the three `<Area>` elements gains a `hide` prop — see below) ...

```tsx
        </ResponsiveContainer>
      </div>

      <div
        className="projection-band-toggles"
        role="group"
        aria-label="Toggle projection bands"
      >
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
      </div>
    </div>
  );
}
```

Add `hide={hiddenBands.has("conservative")}` to the conservative `<Area>`,
`hide={hiddenBands.has("expected")}` to the expected `<Area>`, and
`hide={hiddenBands.has("optimistic")}` to the optimistic `<Area>` (each
`<Area>` already has `dataKey`/`fill`/`fillOpacity`/`stroke`/`type` props —
just add the one new `hide` prop to each, don't reorder the existing ones).

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd frontend && npm test -- ProjectionChart -v`
Expected: PASS (4/4).

- [ ] **Step 6: Add CSS for the band toggles**

In `frontend/src/index.css`, find the existing block:

```css
.mode-terminal .projection-tooltip strong,
.mode-terminal .projection-tooltip dd {
  color: var(--fg-terminal);
}
```

Immediately after it, add:

```css
.projection-chart-wrap {
  display: grid;
  gap: 10px;
}

.projection-band-toggles {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.projection-band-toggle {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 5px 10px;
  border: 1px solid var(--rule);
  border-radius: 999px;
  background: var(--paper-50);
  color: var(--ink-700);
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
}

.projection-band-toggle--muted {
  opacity: 0.5;
}

.projection-band-toggle:disabled {
  cursor: not-allowed;
  opacity: 0.4;
}

.projection-band-swatch {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.mode-terminal .projection-band-toggle {
  border-color: var(--ink-800);
  background: var(--ink-900);
  color: var(--ink-300);
}
```

- [ ] **Step 7: Run lint and the full test file once more**

Run: `cd frontend && npm run lint && npm test -- ProjectionChart -v`
Expected: both clean/passing.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/components/charts/ProjectionChart.tsx frontend/src/components/charts/ProjectionChart.test.tsx frontend/src/index.css
git commit -m "feat: add band visibility toggles to the projection chart"
```

---

## Task 2: Milestone marker + draw-in animation (`ProjectionChart`)

**Files:**
- Modify: `frontend/src/components/charts/ProjectionChart.tsx`
- Modify: `frontend/src/components/charts/ProjectionChart.test.tsx`
- Modify: `frontend/src/features/portfolio/ProjectionPanel.tsx`
- Modify: `frontend/src/index.css`

**Interfaces:**
- Consumes: nothing new from Task 1 — this task adds `onTrack: boolean |
  null` and `targetReachedYear: number | null` to `ProjectionChartProps`
  itself (they weren't added in Task 1, precisely to avoid an unused-prop
  lint error there — this codebase's eslint config makes an unused
  destructured prop a hard `error`, not a warning).
- Produces: a new named export `findMilestonePoint` from
  `ProjectionChart.tsx` (pure function, described below) — exported so it
  can be unit-tested without rendering Recharts' internal SVG (which does
  not reliably render meaningful content in this repo's jsdom test
  environment; every existing chart test in this codebase only asserts on
  elements *outside* Recharts' own rendering, and this task follows that
  same constraint deliberately, not by oversight).

- [ ] **Step 1: Write the failing tests**

In `frontend/src/components/charts/ProjectionChart.test.tsx`:

Add `findMilestonePoint` to the existing import line:

```tsx
import { findMilestonePoint, ProjectionChart } from "./ProjectionChart";
```

Update the existing `renderChart()` helper (added in Task 1) to pass the
two new props — every Task 1 test uses this helper, so this one edit keeps
them all compiling and passing with the milestone marker simply absent
(`onTrack: null` never satisfies `onTrack !== true`):

```tsx
function renderChart() {
  return render(
    <ProjectionChart
      currency="USD"
      formatValue={formatValue}
      series={series}
      targetAmount={null}
      onTrack={null}
      targetReachedYear={null}
    />
  );
}
```

Then append these new tests, inside the existing
`describe("ProjectionChart", ...)` block (add these `it`s after the last one
from Task 1):

```tsx
  it("renders without crashing when motion is allowed (matchMedia reports no reduced-motion preference)", () => {
    const originalMatchMedia = window.matchMedia;
    window.matchMedia = ((query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addEventListener: () => undefined,
      removeEventListener: () => undefined,
      addListener: () => undefined,
      removeListener: () => undefined,
      dispatchEvent: () => false,
    })) as typeof window.matchMedia;

    renderChart();

    expect(
      screen.getByRole("img", { name: "Goal projection chart" })
    ).toBeInTheDocument();

    window.matchMedia = originalMatchMedia;
  });
});

describe("findMilestonePoint", () => {
  const rows = [
    { year: 0, numericExpected: 10000 },
    { year: 1, numericExpected: 11000 },
    { year: 2, numericExpected: 12100 },
  ];

  it("returns the matching row when on track and the year is present", () => {
    expect(findMilestonePoint(rows, true, 1)).toEqual({
      year: 1,
      numericExpected: 11000,
    });
  });

  it("returns undefined when not on track", () => {
    expect(findMilestonePoint(rows, false, 1)).toBeUndefined();
  });

  it("returns undefined when on track but the target year isn't in range", () => {
    expect(findMilestonePoint(rows, true, 10)).toBeUndefined();
  });

  it("returns undefined when targetReachedYear is null", () => {
    expect(findMilestonePoint(rows, true, null)).toBeUndefined();
  });
```

(Note the last `describe` block's closing brace `});` above replaces
whatever currently ends the test file — make sure the file ends with both
`describe` blocks properly closed and nothing duplicated.)

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd frontend && npm test -- ProjectionChart -v`
Expected: FAIL — a compile/type error, since `findMilestonePoint` isn't
exported yet and `ProjectionChartProps` doesn't have `onTrack`/
`targetReachedYear` yet (both fixed together in Step 3 below).

- [ ] **Step 3: Implement the milestone marker and animation**

In `frontend/src/components/charts/ProjectionChart.tsx`:

Add `ReferenceDot` to the existing recharts import:

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

Add the reduced-motion helper right after the `chartColors` line (mirrors
`frontend/src/components/ui/TrendLoader.tsx:14-17` exactly):

```tsx
const prefersReducedMotion = () =>
  typeof window !== "undefined" &&
  typeof window.matchMedia === "function" &&
  window.matchMedia("(prefers-reduced-motion: reduce)").matches;
```

Extend `ProjectionChartProps` with the two new props:

```tsx
type ProjectionChartProps = {
  currency: string;
  formatValue: (value: string, currency: string) => string;
  onTrack: boolean | null;
  series: ProjectionYearPoint[];
  targetAmount: string | null;
  targetReachedYear: number | null;
};
```

Update the function signature to destructure them:

```tsx
export function ProjectionChart({
  currency,
  formatValue,
  onTrack,
  series,
  targetAmount,
  targetReachedYear,
}: ProjectionChartProps) {
```

Add the pure milestone-lookup helper as a new named export, placed after the
`BAND_LABELS` constant:

```tsx
type MilestoneRow = { numericExpected: number; year: number };

export function findMilestonePoint<T extends MilestoneRow>(
  chartRows: T[],
  onTrack: boolean | null,
  targetReachedYear: number | null
): T | undefined {
  if (onTrack !== true || targetReachedYear == null) {
    return undefined;
  }
  return chartRows.find((row) => row.year === targetReachedYear);
}
```

Inside the component, right after the existing `const numericTarget = ...`
line, add:

```tsx
  const animationsEnabled = !prefersReducedMotion();
  const milestonePoint = findMilestonePoint(
    chartRows,
    onTrack,
    targetReachedYear
  );
```

Add these three props to **each** of the three existing `<Area>` elements
(conservative/expected/optimistic — six total prop additions across three
elements, same three values each time):

```tsx
            isAnimationActive={animationsEnabled}
            animationDuration={800}
            animationEasing="ease-out"
```

Right after the existing `{numericTarget != null && (<ReferenceLine ... />)}`
block, and still inside `<AreaChart>`, add:

```tsx
          {milestonePoint && (
            <ReferenceDot
              className="projection-milestone-dot"
              fill={chartColors[0]}
              label={{
                fill: chartColors[0],
                fontSize: 12,
                position: "top",
                value: "Target reached",
              }}
              r={6}
              stroke="#fff"
              strokeWidth={2}
              x={milestonePoint.year}
              y={milestonePoint.numericExpected}
            />
          )}
```

- [ ] **Step 4: Update the `ProjectionPanel` call site**

In `frontend/src/features/portfolio/ProjectionPanel.tsx`, find the existing:

```tsx
          <ProjectionChart
            currency={data.base_currency}
            formatValue={formatMoney}
            series={data.series}
            targetAmount={data.target_amount}
          />
```

Replace with:

```tsx
          <ProjectionChart
            currency={data.base_currency}
            formatValue={formatMoney}
            onTrack={data.on_track}
            series={data.series}
            targetAmount={data.target_amount}
            targetReachedYear={data.target_reached_year}
          />
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd frontend && npm test -- ProjectionChart -v`
Expected: PASS (all tests in both `describe` blocks).

Then run the full projection-related suite to confirm the `ProjectionPanel`
call-site change didn't break anything:

Run: `cd frontend && npm test -- projection`
Expected: PASS (all pre-existing `ProjectionPanel` tests still green).

- [ ] **Step 6: Add CSS for the milestone marker**

In `frontend/src/index.css`, immediately after the `.mode-terminal
.projection-band-toggle { ... }` block added in Task 1, add:

```css
.projection-milestone-dot {
  filter: drop-shadow(0 0 2px rgba(0, 0, 0, 0.25));
}

.mode-terminal .projection-milestone-dot {
  stroke: var(--ink-900);
}
```

- [ ] **Step 7: Run lint and build**

Run: `cd frontend && npm run lint && npm run build`
Expected: both clean.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/components/charts/ProjectionChart.tsx frontend/src/components/charts/ProjectionChart.test.tsx frontend/src/features/portfolio/ProjectionPanel.tsx frontend/src/index.css
git commit -m "feat: add milestone marker and draw-in animation to the projection chart"
```

---

## Task 3: Horizon selector (`ProjectionPanel`)

**Files:**
- Modify: `frontend/src/features/portfolio/ProjectionPanel.tsx`
- Modify: `frontend/src/features/portfolio/projection.test.tsx`

**Interfaces:**
- Consumes: `getProjection(accessToken, overrides?: ProjectionOverrides)` and
  `type ProjectionOverrides = { target?: string; contribution?: string;
  annualReturn?: string; years?: number }`, both already defined in
  `frontend/src/features/portfolio/portfolio-api.ts` (no changes needed to
  that file in this whole plan).
- Produces: `ProjectionPanel` gains a `years` override state variable that
  Task 4 will sit alongside (Task 4 adds `contribution`/`annualReturn`
  override state using the identical pattern established here).

- [ ] **Step 1: Read the current file**

Read `frontend/src/features/portfolio/ProjectionPanel.tsx` in full (it's
short, ~135 lines) — the diffs below are precise but you need the exact
surrounding context to apply them.

- [ ] **Step 2: Write the failing tests**

Append to `frontend/src/features/portfolio/projection.test.tsx`, inside the
existing `describe("ProjectionPanel", ...)` block (after the last existing
`it`), and add `userEvent` and `waitFor` to the existing imports:

```tsx
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
```

(These replace the current `import { cleanup, render, screen } from
"@testing-library/react";` line — add `waitFor` to it and add the new
`userEvent` import line right after.)

```tsx
  it("marks the horizon option matching the initial fetch as active", async () => {
    vi.mocked(getProjection).mockResolvedValue(projectionWithTarget);

    renderPanel();

    const activeButton = await screen.findByRole("button", { name: "10y" });
    expect(activeButton).toHaveAttribute("aria-pressed", "true");
  });

  it("refetches with a years override when a horizon option is clicked", async () => {
    vi.mocked(getProjection).mockResolvedValue(projectionWithTarget);

    renderPanel();
    await screen.findByRole("img", { name: "Goal projection chart" });
    expect(getProjection).toHaveBeenCalledTimes(1);

    await userEvent.click(screen.getByRole("button", { name: "5y" }));

    await waitFor(() => {
      expect(getProjection).toHaveBeenLastCalledWith("access-token", {
        years: 5,
      });
    });
  });
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `cd frontend && npm test -- projection -v`
Expected: FAIL — no button named `"10y"`/`"5y"` exists yet.

- [ ] **Step 4: Implement the horizon selector**

In `frontend/src/features/portfolio/ProjectionPanel.tsx`:

Change the top import line from:

```tsx
import { useQuery } from "@tanstack/react-query";
```

to:

```tsx
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
```

Add a module-level constant right after the `projectionErrorCopy` function,
before `export default function ProjectionPanel`:

```tsx
const HORIZON_OPTIONS = [3, 5, 10, 15, 20, 30];
```

Replace the existing query:

```tsx
  const projectionQuery = useQuery({
    enabled: Boolean(accessToken),
    queryKey: ["portfolio-projection", accessToken],
    queryFn: () => getProjection(accessToken),
  });
```

with:

```tsx
  const [years, setYears] = useState<number | null>(null);

  const projectionQuery = useQuery({
    enabled: Boolean(accessToken),
    queryKey: ["portfolio-projection", accessToken, years],
    queryFn: () =>
      getProjection(accessToken, years !== null ? { years } : {}),
  });
```

Right after the existing `const data = projectionQuery.data;` line, add:

```tsx
  const effectiveYears = years ?? data?.horizon_years ?? null;
```

In the JSX, the current data branch starts with:

```tsx
      {data ? (
        <>
          <ProjectionChart
```

Insert the horizon selector immediately before `<ProjectionChart`, still
inside the `<>` fragment:

```tsx
      {data ? (
        <>
          <div
            aria-label="Projection horizon"
            className="segmented-control projection-horizon-control"
          >
            {HORIZON_OPTIONS.map((option) => (
              <button
                aria-pressed={effectiveYears === option}
                className={
                  effectiveYears === option
                    ? "segmented-button segmented-button--active"
                    : "segmented-button"
                }
                key={option}
                type="button"
                onClick={() => setYears(option)}
              >
                {option}y
              </button>
            ))}
          </div>

          <ProjectionChart
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd frontend && npm test -- projection -v`
Expected: PASS (all tests, including the two new ones and the four
pre-existing ones).

- [ ] **Step 6: Run lint**

Run: `cd frontend && npm run lint`
Expected: clean. (No new CSS class is needed here —
`.segmented-control`/`.segmented-button`/`.segmented-button--active` already
exist in `frontend/src/index.css:1089-1124` and are reused as-is.)

- [ ] **Step 7: Commit**

```bash
git add frontend/src/features/portfolio/ProjectionPanel.tsx frontend/src/features/portfolio/projection.test.tsx
git commit -m "feat: add a projection horizon selector"
```

---

## Task 4: What-if sliders for contribution and annual return (`ProjectionPanel`)

**Files:**
- Modify: `frontend/src/features/portfolio/ProjectionPanel.tsx`
- Modify: `frontend/src/features/portfolio/projection.test.tsx`
- Modify: `frontend/src/index.css`

**Interfaces:**
- Consumes: the `years` state pattern established in Task 3 (this task adds
  two more override dimensions to the same query key/`queryFn` in place).
- Produces: two accessible range inputs labeled exactly `"Contribution
  amount"` and `"Expected annual return"` (Task 5 needs these exact labels
  for nothing itself, but keep them exact since they're part of this
  component's now-established a11y contract).

- [ ] **Step 1: Write the failing test**

Append to `frontend/src/features/portfolio/projection.test.tsx`, inside the
existing `describe("ProjectionPanel", ...)` block:

```tsx
  it("debounces a contribution slider change into a committed override", async () => {
    vi.mocked(getProjection).mockResolvedValue(projectionWithTarget);

    renderPanel();
    await screen.findByRole("img", { name: "Goal projection chart" });
    expect(getProjection).toHaveBeenCalledTimes(1);

    const slider = screen.getByLabelText("Contribution amount");
    fireEvent.change(slider, { target: { value: "800" } });

    // Still debounced immediately after the change.
    expect(getProjection).toHaveBeenCalledTimes(1);

    await new Promise((resolve) => setTimeout(resolve, 400));

    await waitFor(() => {
      expect(getProjection).toHaveBeenLastCalledWith("access-token", {
        contribution: "800",
      });
    });
  });

  it("debounces an annual return slider change into a committed override", async () => {
    vi.mocked(getProjection).mockResolvedValue(projectionWithTarget);

    renderPanel();
    await screen.findByRole("img", { name: "Goal projection chart" });

    const slider = screen.getByLabelText("Expected annual return");
    fireEvent.change(slider, { target: { value: "7.5" } });

    await new Promise((resolve) => setTimeout(resolve, 400));

    await waitFor(() => {
      expect(getProjection).toHaveBeenLastCalledWith("access-token", {
        annualReturn: "7.5",
      });
    });
  });
```

Add `fireEvent` to the existing testing-library import (it currently imports
`cleanup, render, screen, waitFor` after Task 3 — add `fireEvent` to that
same line):

```tsx
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd frontend && npm test -- projection -v`
Expected: FAIL — no element is labeled `"Contribution amount"` or
`"Expected annual return"` yet.

- [ ] **Step 3: Implement the sliders**

In `frontend/src/features/portfolio/ProjectionPanel.tsx`:

Add `useEffect` to the React import:

```tsx
import { useEffect, useState } from "react";
```

Add a debounce constant next to `HORIZON_OPTIONS`:

```tsx
const HORIZON_OPTIONS = [3, 5, 10, 15, 20, 30];
const DEBOUNCE_MS = 350;
```

Replace the `years`-only state block from Task 3:

```tsx
  const [years, setYears] = useState<number | null>(null);
```

with:

```tsx
  const [years, setYears] = useState<number | null>(null);
  const [contributionDraft, setContributionDraft] = useState<string | null>(
    null
  );
  const [contribution, setContribution] = useState<string | null>(null);
  const [annualReturnDraft, setAnnualReturnDraft] = useState<string | null>(
    null
  );
  const [annualReturn, setAnnualReturn] = useState<string | null>(null);

  useEffect(() => {
    const timer = setTimeout(() => {
      setContribution(contributionDraft);
    }, DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [contributionDraft]);

  useEffect(() => {
    const timer = setTimeout(() => {
      setAnnualReturn(annualReturnDraft);
    }, DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [annualReturnDraft]);
```

Replace the `queryFn` from Task 3:

```tsx
    queryFn: () =>
      getProjection(accessToken, years !== null ? { years } : {}),
```

with:

```tsx
    queryFn: () => {
      const overrides: Parameters<typeof getProjection>[1] = {};
      if (years !== null) overrides.years = years;
      if (contribution !== null) overrides.contribution = contribution;
      if (annualReturn !== null) overrides.annualReturn = annualReturn;
      return getProjection(accessToken, overrides);
    },
```

and extend the `queryKey` array from Task 3:

```tsx
    queryKey: ["portfolio-projection", accessToken, years],
```

to:

```tsx
    queryKey: [
      "portfolio-projection",
      accessToken,
      years,
      contribution,
      annualReturn,
    ],
```

Right after the existing `const effectiveYears = ...` line (from Task 3),
add:

```tsx
  const displayedContribution = Number(
    contributionDraft ?? contribution ?? data?.contribution_amount ?? "0"
  );
  const displayedAnnualReturn = Number(
    annualReturnDraft ?? annualReturn ?? data?.annual_return_expected ?? "0"
  );
  const contributionMax = Math.max(
    Number(data?.contribution_amount ?? 0) * 4,
    1000
  );
```

In the JSX, right after the horizon-selector `<div>` added in Task 3 and
before `<ProjectionChart`, add:

```tsx
          <div className="projection-slider-field">
            <div className="projection-slider-heading">
              <label htmlFor="projection-contribution">
                Contribution amount
              </label>
              <span className="num">
                {formatMoney(String(displayedContribution), data.base_currency)}
              </span>
            </div>
            <input
              className="projection-slider"
              id="projection-contribution"
              max={contributionMax}
              min={0}
              step={10}
              type="range"
              value={displayedContribution}
              onChange={(event) =>
                setContributionDraft(event.target.value)
              }
            />
          </div>

          <div className="projection-slider-field">
            <div className="projection-slider-heading">
              <label htmlFor="projection-annual-return">
                Expected annual return
              </label>
              <span className="num">
                {formatPercent(String(displayedAnnualReturn))}
              </span>
            </div>
            <input
              className="projection-slider"
              id="projection-annual-return"
              max={20}
              min={-5}
              step={0.5}
              type="range"
              value={displayedAnnualReturn}
              onChange={(event) =>
                setAnnualReturnDraft(event.target.value)
              }
            />
          </div>

```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd frontend && npm test -- projection -v`
Expected: PASS (all tests, including the two new debounce tests and the
five from Tasks 1-3).

- [ ] **Step 5: Add CSS for the sliders**

In `frontend/src/index.css`, immediately after the `.mode-terminal
.projection-milestone-dot { ... }` block added in Task 2, add:

```css
.projection-slider-field {
  display: grid;
  gap: 6px;
}

.projection-slider-heading {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  font-size: 13px;
  color: var(--ink-600);
}

.projection-slider {
  width: 100%;
  height: 6px;
  border-radius: 999px;
  background: var(--rule);
  appearance: none;
  cursor: pointer;
}

.projection-slider::-webkit-slider-thumb {
  appearance: none;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: var(--accent-500);
  border: 2px solid var(--paper-50);
  box-shadow: 0 0 0 1px var(--rule);
}

.projection-slider::-moz-range-thumb {
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: var(--accent-500);
  border: 2px solid var(--paper-50);
  box-shadow: 0 0 0 1px var(--rule);
}

.mode-terminal .projection-slider {
  background: var(--ink-800);
}

.mode-terminal .projection-slider::-webkit-slider-thumb,
.mode-terminal .projection-slider::-moz-range-thumb {
  background: var(--accent-300);
  border-color: var(--ink-900);
}
```

- [ ] **Step 6: Run lint and build**

Run: `cd frontend && npm run lint && npm run build`
Expected: both clean.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/features/portfolio/ProjectionPanel.tsx frontend/src/features/portfolio/projection.test.tsx frontend/src/index.css
git commit -m "feat: add what-if sliders for contribution and annual return"
```

---

## Task 5: Reset control + "Updating…" indicator (`ProjectionPanel`)

**Files:**
- Modify: `frontend/src/features/portfolio/ProjectionPanel.tsx`
- Modify: `frontend/src/features/portfolio/projection.test.tsx`
- Modify: `frontend/src/index.css`

**Interfaces:**
- Consumes: `years`/`contribution`/`contributionDraft`/`annualReturn`/
  `annualReturnDraft` state from Tasks 3-4, and `projectionQuery.isFetching`/
  `.isLoading` from TanStack Query (already available on the existing
  `projectionQuery` object, no new query needed).
- Produces: nothing consumed by later tasks — this is the last task in the
  plan.

- [ ] **Step 1: Write the failing tests**

Append to `frontend/src/features/portfolio/projection.test.tsx`:

```tsx
  it("hides the reset control until an override is active, then reverts on click", async () => {
    vi.mocked(getProjection).mockResolvedValue(projectionWithTarget);

    renderPanel();
    await screen.findByRole("img", { name: "Goal projection chart" });

    expect(
      screen.queryByRole("button", { name: "Reset to my profile values" })
    ).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "5y" }));

    const resetButton = await screen.findByRole("button", {
      name: "Reset to my profile values",
    });
    await userEvent.click(resetButton);

    await waitFor(() => {
      expect(getProjection).toHaveBeenLastCalledWith("access-token", {});
    });
    expect(
      screen.queryByRole("button", { name: "Reset to my profile values" })
    ).not.toBeInTheDocument();
  });

  it("shows an updating indicator while a background refetch is in flight", async () => {
    vi.mocked(getProjection).mockResolvedValue(projectionWithTarget);

    renderPanel();
    await screen.findByRole("img", { name: "Goal projection chart" });
    expect(screen.queryByText("Updating…")).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "5y" }));

    expect(await screen.findByText("Updating…")).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.queryByText("Updating…")).not.toBeInTheDocument();
    });
  });
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd frontend && npm test -- projection -v`
Expected: FAIL — no "Reset to my profile values" button or "Updating…" text
exists yet.

- [ ] **Step 3: Implement reset and the updating indicator**

In `frontend/src/features/portfolio/ProjectionPanel.tsx`, right after the
`const contributionMax = ...` line from Task 4, add:

```tsx
  const hasOverride = years !== null || contribution !== null || annualReturn !== null;

  function resetOverrides() {
    setYears(null);
    setContributionDraft(null);
    setContribution(null);
    setAnnualReturnDraft(null);
    setAnnualReturn(null);
  }
```

In the JSX, right after the annual-return slider's closing `</div>` (the
last thing Task 4 added, right before `<ProjectionChart`), add:

```tsx
          {projectionQuery.isFetching && !projectionQuery.isLoading ? (
            <span className="projection-updating" role="status">
              Updating…
            </span>
          ) : null}

          {hasOverride ? (
            <button
              className="projection-reset"
              type="button"
              onClick={resetOverrides}
            >
              Reset to my profile values
            </button>
          ) : null}

```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd frontend && npm test -- projection -v`
Expected: PASS (all tests in the file).

- [ ] **Step 5: Add CSS for the reset control and updating indicator**

In `frontend/src/index.css`, immediately after the `.mode-terminal
.projection-slider::-webkit-slider-thumb, .mode-terminal
.projection-slider::-moz-range-thumb { ... }` block added in Task 4, add:

```css
.projection-updating {
  font-size: 12px;
  color: var(--ink-600);
}

.projection-reset {
  justify-self: start;
  padding: 0;
  border: none;
  background: none;
  color: var(--accent-500);
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  text-decoration: underline;
}

.mode-terminal .projection-reset {
  color: var(--accent-300);
}
```

- [ ] **Step 6: Run the full frontend verification suite**

Run: `cd frontend && npm test && npm run lint && npm run build`
Expected: all tests pass (the full suite, not just projection-related
files), lint clean, build clean.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/features/portfolio/ProjectionPanel.tsx frontend/src/features/portfolio/projection.test.tsx frontend/src/index.css
git commit -m "feat: add reset control and updating indicator to projection what-if controls"
```

---

## Final Verification

- [ ] **Run the complete frontend suite one more time**

Run: `cd frontend && npm test && npm run lint && npm run build`
Expected: all green — this plan makes no backend changes, so no backend
verification is needed.

- [ ] **Manual check**

Run the app locally (`npm run dev`), sign in, and on the dashboard's Goal
projection panel: click through a few horizon options, drag both sliders
and confirm the chart updates after a brief "Updating…" pause, hide/show
each band and confirm the last one can't be hidden, click "Reset to my
profile values" and confirm everything reverts, and (if you have a profile
with `on_track: true`) confirm the "Target reached" marker appears at the
right year.
